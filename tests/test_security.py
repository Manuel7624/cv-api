"""Protecciones de la auditoría de seguridad: tamaño de las peticiones, cabeceras,
bloqueo de intentos fallidos en /admin/stats, SSL con Neon y el contenedor."""
from pathlib import Path

import pytest
from sqlalchemy import event

from app import admin, chat
from app.admin import FAILED_LOGINS_BEFORE_LOCK, LOCK_WINDOW_SECONDS, FailedLogins, failed_logins
from app.security import MAX_REQUEST_BYTES
from app.stats_store import make_engine

TOKEN = "token-de-prueba-muy-largo-123"
ROOT = Path(__file__).parent.parent


@pytest.fixture(autouse=True)
def clean_failed_logins():
    failed_logins.reset()
    yield
    failed_logins.reset()


@pytest.fixture
def fake_ai(monkeypatch):
    calls = []

    def fake_ask(*_args):
        calls.append(1)
        yield "Respuesta de prueba"

    monkeypatch.setattr(chat, "ask_providers", fake_ask)
    monkeypatch.setattr(chat.retrieval, "select_extra_info", lambda *_: None)
    return calls


# --- Tamaño de las peticiones ---


def big_body(size):
    return '{"message": "hola", "relleno": "' + "x" * size + '"}'


def test_requests_over_32_kb_are_rejected(client, fake_ai):
    response = client.post("/chat", content=big_body(MAX_REQUEST_BYTES),
                           headers={"Content-Type": "application/json"})
    assert response.status_code == 413
    assert fake_ai == []


def test_requests_without_content_length_are_also_limited(client, fake_ai):
    """Enviada por trozos (sin Content-Length): se corta al pasar del máximo."""
    def chunks():
        yield b'{"message": "hola", "relleno": "'
        for _ in range(10):
            yield b"x" * 8192
        yield b'"}'

    response = client.post("/chat", content=chunks(), headers={"Content-Type": "application/json"})
    assert response.status_code == 413
    assert fake_ai == []


def test_invalid_content_length_is_rejected(client, fake_ai):
    response = client.post("/chat", content=b"{}", headers={
        "Content-Type": "application/json", "Content-Length": "mucho"})
    assert response.status_code in (400, 413)
    assert fake_ai == []


def test_normal_requests_still_work(client, fake_ai):
    history = [{"role": "user", "content": "x" * 500}, {"role": "assistant", "content": "y" * 1200}] * 3
    for path in ("/chat", "/chat/stream"):
        response = client.post(path, json={"message": "z" * 500, "history": history})
        assert response.status_code == 200
    assert len(fake_ai) == 2


def test_rejected_requests_do_not_spend_chat_limits(client, fake_ai):
    from app.rate_limit import chat_limits

    before = chat_limits.remaining_total()
    client.post("/chat", content=big_body(MAX_REQUEST_BYTES), headers={"Content-Type": "application/json"})
    assert chat_limits.remaining_total() == before


# --- Cabeceras ---


def test_permissions_policy_disables_camera_microphone_and_location(client):
    for path in ("/", "/profile", "/docs", "/static/chat.js"):
        assert client.get(path).headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"


def test_hsts_only_over_https(client):
    assert "Strict-Transport-Security" not in client.get("/").headers
    over_https = client.get("/", headers={"X-Forwarded-Proto": "https"}).headers
    assert over_https["Strict-Transport-Security"] == "max-age=31536000"
    assert "Strict-Transport-Security" not in client.get("/", headers={"X-Forwarded-Proto": "http"}).headers


def test_rejected_large_requests_also_have_security_headers(client):
    response = client.post("/chat", content=big_body(MAX_REQUEST_BYTES), headers={"Content-Type": "application/json"})
    assert response.headers["X-Content-Type-Options"] == "nosniff"


# --- Intentos fallidos en /admin/stats ---


def login(client, password, ip="203.0.113.7"):
    return client.get("/admin/stats", auth=("x", password), headers={"CF-Connecting-IP": ip})


def test_ten_failed_logins_lock_the_ip_even_with_the_right_password(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)
    monkeypatch.setenv("CLIENT_IP_HEADER", "CF-Connecting-IP")
    for _ in range(FAILED_LOGINS_BEFORE_LOCK - 1):
        assert login(client, "contrasena-equivocada-12345").status_code == 401
    assert login(client, TOKEN).status_code == 200  # aún no está bloqueada
    for _ in range(FAILED_LOGINS_BEFORE_LOCK):
        login(client, "contrasena-equivocada-12345")
    response = login(client, TOKEN)
    assert response.status_code == 429
    assert response.headers["Retry-After"] == str(LOCK_WINDOW_SECONDS)
    # Otra IP no se ve afectada.
    assert login(client, TOKEN, ip="198.51.100.1").status_code == 200


def test_a_successful_login_resets_the_failures(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)
    for _ in range(FAILED_LOGINS_BEFORE_LOCK - 1):
        login(client, "contrasena-equivocada-12345")
    assert login(client, TOKEN).status_code == 200
    for _ in range(FAILED_LOGINS_BEFORE_LOCK - 1):
        login(client, "contrasena-equivocada-12345")
    assert login(client, TOKEN).status_code == 200


def test_the_browser_asking_for_the_password_does_not_count(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)
    for _ in range(FAILED_LOGINS_BEFORE_LOCK + 5):
        assert client.get("/admin/stats").status_code == 401
    assert login(client, TOKEN).status_code == 200


def test_the_lock_ends_after_15_minutes():
    now = [1000.0]
    logins = FailedLogins(clock=lambda: now[0])
    for _ in range(FAILED_LOGINS_BEFORE_LOCK):
        logins.record_failure("hash")
    assert logins.is_locked("hash")
    now[0] += LOCK_WINDOW_SECONDS - 1
    assert logins.is_locked("hash")
    now[0] += 1
    assert not logins.is_locked("hash")


def test_old_failures_do_not_count():
    now = [1000.0]
    logins = FailedLogins(clock=lambda: now[0])
    for _ in range(FAILED_LOGINS_BEFORE_LOCK - 1):
        logins.record_failure("hash")
    now[0] += LOCK_WINDOW_SECONDS
    logins.record_failure("hash")
    assert not logins.is_locked("hash")


def test_failed_logins_never_keep_the_ip(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)
    monkeypatch.setenv("CLIENT_IP_HEADER", "CF-Connecting-IP")
    for _ in range(FAILED_LOGINS_BEFORE_LOCK):
        login(client, "contrasena-equivocada-12345")
    stored = str(admin.failed_logins.failures) + str(admin.failed_logins.locked_until)
    assert "203.0.113.7" not in stored
    assert len(next(iter(admin.failed_logins.locked_until))) == 64


def test_without_token_the_page_still_does_not_exist(client):
    for _ in range(FAILED_LOGINS_BEFORE_LOCK + 1):
        assert login(client, "lo-que-sea-muy-largo-12345").status_code == 404


# --- SSL con Neon ---


def connect_params(url):
    """Parámetros con los que se conectaría (sin conectar de verdad)."""
    engine = make_engine(url)
    captured = {}

    @event.listens_for(engine, "do_connect")
    def capture(_dialect, _record, _args, params):
        captured.update(params)
        raise ConnectionAbortedError("solo se quería ver los parámetros")

    with pytest.raises(Exception):
        engine.connect()
    return captured


@pytest.mark.parametrize(
    ("query", "expected"),
    [("", "require"), ("?sslmode=disable", "require"), ("?sslmode=prefer", "require"),
     ("?sslmode=require", "require"), ("?sslmode=verify-full", "verify-full")],
)
def test_postgres_connections_always_use_ssl(query, expected):
    assert connect_params(f"postgresql://u:p@ejemplo.neon.tech/db{query}")["sslmode"] == expected


# --- Contenedor ---


def test_container_runs_without_root_and_without_access_log():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "\nUSER app\n" in dockerfile
    assert "--no-access-log" in dockerfile
    assert "--reload" not in dockerfile
    assert "pip install --no-cache-dir --upgrade pip==" in dockerfile


def test_requirements_are_pinned():
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            assert "==" in line and ">" not in line and "<" not in line, line
