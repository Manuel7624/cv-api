"""Registro de preguntas: se guardan con su respuesta 30 días, sin la IP, y solo se
ven en la página privada /admin/stats."""
from datetime import datetime, timedelta, timezone

import pytest
from fakes import failure, ok, use_fake_stream

from app import chat, crud, retrieval
from app.stats import QUESTION_DAYS, ChatStats, chat_stats
from app.stats_store import StatsStore

TOKEN = "token-de-prueba-muy-largo-123"
IP = "203.0.113.7"


@pytest.fixture
def providers(monkeypatch):
    script = {"gemini": [], "gemini_backup": [], "groq": []}
    calls = use_fake_stream(
        monkeypatch, lambda name: script[name].pop(0) if script[name] else failure()
    )
    script["calls"] = calls
    return script


@pytest.fixture
def rag_on(monkeypatch, db_session):
    selected = crud.get_extra_info(db_session, fixed_answer=False)[:3]
    monkeypatch.setattr(retrieval, "select_extra_info", lambda _m, _p: selected)


@pytest.fixture
def database(monkeypatch, tmp_path):
    """El registro global del chat, guardando en una base SQLite de prueba."""
    store = StatsStore(f"sqlite:///{tmp_path / 'stats.db'}")
    monkeypatch.setattr(chat_stats, "store", store)
    yield store
    store.close()


def ask(client, message):
    return client.post("/chat", json={"message": message}, headers={"CF-Connecting-IP": IP})


def logged():
    return chat_stats.questions()["rows"]


def test_answered_question_is_logged_with_its_answer_and_provider(client, providers, rag_on):
    providers["gemini"].append(ok("Juego al fútbol y soy portero de fútbol sala."))
    ask(client, "¿Cuáles son tus hobbies?")
    [row] = logged()
    assert row["question"] == "¿Cuáles son tus hobbies?"
    assert row["answer"] == "Juego al fútbol y soy portero de fútbol sala."
    assert row["provider"] == "gemini"
    assert row["status"] == "answered"
    assert set(row) == {"asked_at", "question", "answer", "provider", "status"}


def test_rejected_question_with_rag_is_repeated_with_all_the_information(
    client, providers, rag_on
):
    """Puede que el dato estuviera en la información que el RAG no envió."""
    providers["gemini"].append(ok(chat.OFF_TOPIC_ANSWER))
    providers["gemini"].append(ok("Juego al fútbol y soy portero de fútbol sala."))
    answer = ask(client, "¿Cuáles son tus hobbies?").json()["answer"]
    assert answer == "Juego al fútbol y soy portero de fútbol sala."
    assert len(providers["calls"]) == 2
    assert logged()[0]["status"] == "answered"


def test_rejection_is_never_shown_before_plan_b(client, providers, rag_on):
    providers["gemini"].append(ok(chat.OFF_TOPIC_ANSWER))
    providers["gemini"].append(ok("Respuesta buena con toda la información."))
    with client.stream("POST", "/chat/stream", json={"message": "¿Hobbies?"}) as response:
        body = "".join(response.iter_text())
    assert "Solo puedo responder" not in body
    assert "restart" not in body


@pytest.mark.parametrize(
    ("answers", "status"),
    [
        ([chat.OFF_TOPIC_ANSWER, chat.OFF_TOPIC_ANSWER], "rejected"),
        (
            ["Eso no lo tengo por aquí, pero escríbeme a mi correo y te lo cuento encantado."] * 2,
            "no_information",
        ),
        ([], "error"),
    ],
)
def test_status_of_each_question(client, providers, rag_on, answers, status):
    providers["gemini"].extend(ok(answer) for answer in answers)
    ask(client, "¿Cuál es la capital de Francia?")
    assert logged()[0]["status"] == status


def test_questions_are_saved_in_the_database_without_the_ip(
    client, providers, rag_on, database, monkeypatch
):
    monkeypatch.setenv("CLIENT_IP_HEADER", "CF-Connecting-IP")
    providers["gemini"].append(ok("Respuesta de prueba"))
    ask(client, "¿Qué hace Balancea?")
    assert chat_stats.flush()
    rows, total = database.questions(chat_stats.questions_since(), None, 50, 0)
    assert total == 1
    assert rows[0]["question"] == "¿Qué hace Balancea?"
    assert IP not in str(rows)


def test_questions_survive_a_restart(tmp_path):
    url = f"sqlite:///{tmp_path / 'stats.db'}"
    first = ChatStats()
    first.store = StatsStore(url)
    first.log_question("¿Pregunta?", "Respuesta", "groq", "answered")
    assert first.flush()
    first.close()

    second = ChatStats()
    second.store = StatsStore(url)
    result = second.questions()
    assert result["source"] == "database"
    assert [row["question"] for row in result["rows"]] == ["¿Pregunta?"]


def test_questions_older_than_30_days_are_deleted(tmp_path):
    now = [datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)]
    stats_ = ChatStats(clock=lambda: now[0])
    stats_.store = StatsStore(f"sqlite:///{tmp_path / 'stats.db'}")
    stats_.log_question("Antigua", "R", "gemini", "answered")
    stats_.log_question("Reciente", "R", "gemini", "answered")
    assert stats_.flush()
    # La "Reciente" se hace 1 día después que la antigua.
    with stats_.store.engine.begin() as connection:
        from app.stats_store import questions_table

        connection.execute(
            questions_table.update()
            .where(questions_table.c.question == "Reciente")
            .values(asked_at=now[0] + timedelta(days=1))
        )

    now[0] += timedelta(days=QUESTION_DAYS, hours=1)
    stats_.last_cleanup = None  # toca borrar ya, sin esperar una hora
    assert stats_.flush()
    rows, total = stats_.store.questions(datetime(2000, 1, 1, tzinfo=timezone.utc), None, 50, 0)
    assert [row["question"] for row in rows] == ["Reciente"]
    assert total == 1


def test_old_questions_are_not_shown_even_before_they_are_deleted():
    now = [datetime(2026, 11, 16, tzinfo=timezone.utc)]
    stats_ = ChatStats(clock=lambda: now[0])
    stats_.log_question("Antigua", "R", "gemini", "answered")
    now[0] += timedelta(days=QUESTION_DAYS + 1)
    assert stats_.questions()["total"] == 0


def test_chat_keeps_working_if_the_database_fails(client, providers, rag_on, tmp_path, monkeypatch):
    broken = StatsStore(f"sqlite:///{tmp_path / 'no-existe' / 'stats.db'}")
    monkeypatch.setattr(chat_stats, "store", broken)
    providers["gemini"].append(ok("Respuesta de prueba"))
    assert ask(client, "¿Qué hace Balancea?").json()["answer"] == "Respuesta de prueba"
    assert not chat_stats.flush()
    result = chat_stats.questions()
    assert result["source"] == "memory"
    assert result["rows"][0]["question"] == "¿Qué hace Balancea?"


def test_logging_a_question_never_touches_the_database(tmp_path, monkeypatch):
    stats_ = ChatStats()
    stats_.store = StatsStore(f"sqlite:///{tmp_path / 'stats.db'}")

    def fail(*_args, **_kwargs):
        raise AssertionError("el chat no debe esperar a la base de datos")

    monkeypatch.setattr(stats_.store, "add", fail)
    stats_.log_question("¿Pregunta?", "Respuesta", "gemini", "answered")


# --- Página privada ---


def admin_page(client, **params):
    return client.get("/admin/stats", params=params, auth=("x", TOKEN))


def test_admin_page_lists_missing_and_latest_questions(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)
    chat_stats.log_question("¿Respondida?", "Sí", "gemini", "answered")
    chat_stats.log_question("¿Capital de Francia?", chat.OFF_TOPIC_ANSWER, "gemini", "rejected")
    chat_stats.log_question("¿Color favorito?", "Eso no lo tengo por aquí", "groq", "no_information")
    page = admin_page(client).text
    missing = page.split("Preguntas sin respuesta o rechazadas</h2>")[1].split("Últimas preguntas</h2>")[0]
    latest = page.split("Últimas preguntas</h2>")[1]
    assert "¿Capital de Francia?" in missing and "¿Color favorito?" in missing
    assert "¿Respondida?" not in missing
    for question in ("¿Respondida?", "¿Capital de Francia?", "¿Color favorito?"):
        assert question in latest
    # La más reciente primero.
    assert latest.index("¿Color favorito?") < latest.index("¿Respondida?")


def test_admin_page_escapes_questions(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)
    chat_stats.log_question("<script>alert(1)</script>", "<b>x</b>", "gemini", "answered")
    page = admin_page(client).text
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page


def test_admin_page_shows_50_questions_per_page(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)
    for number in range(120):
        chat_stats.log_question(f"Pregunta número {number:03d}", "R", "gemini", "answered")
    first = admin_page(client).text.split("Últimas preguntas</h2>")[1]
    assert "Pregunta número 119" in first and "Pregunta número 070" in first
    assert "Pregunta número 069" not in first
    assert "Página 1 de 3 · 120 preguntas" in first
    assert "latest_page=2" in first
    third = admin_page(client, latest_page=3).text.split("Últimas preguntas</h2>")[1]
    assert "Pregunta número 019" in third and "Pregunta número 020" not in third
    assert admin_page(client, latest_page=0).status_code == 422


def test_admin_questions_need_the_password(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)
    chat_stats.log_question("¿Pregunta secreta?", "R", "gemini", "answered")
    for params in ({}, {"latest_page": 2}, {"missing_page": 1}):
        response = client.get("/admin/stats", params=params)
        assert response.status_code == 401
        assert "¿Pregunta secreta?" not in response.text
    assert client.get("/admin/stats", auth=("x", "otro-token-muy-largo-12345")).status_code == 401


def test_admin_questions_do_not_exist_without_token(client):
    chat_stats.log_question("¿Pregunta secreta?", "R", "gemini", "answered")
    assert client.get("/admin/stats", auth=("x", "")).status_code == 404


def test_questions_are_not_in_swagger_or_public_routes(client):
    chat_stats.log_question("¿Pregunta secreta?", "Respuesta secreta", "gemini", "answered")
    schema = client.get("/openapi.json").text
    assert "/admin" not in schema
    assert "missing_page" not in schema and "latest_page" not in schema
    for path in [route.path for route in client.app.routes if hasattr(route, "path")]:
        if path.startswith("/admin") or "{" in path:
            continue
        response = client.get(path)
        assert "¿Pregunta secreta?" not in response.text
        assert "Respuesta secreta" not in response.text
