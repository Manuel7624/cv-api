"""Estadísticas del chat, página privada /admin/stats y límites configurables."""
from datetime import datetime, timedelta, timezone

import pytest
from fakes import failure, ok, use_fake_stream

from app import chat_limits, crud, retrieval
from app.rate_limit import chat_limits as limits
from app.stats import COUNTERS, ChatStats, chat_stats

TOKEN = "token-de-prueba-muy-largo-123"
QUESTION = "¿Tienes una pregunta muy personal llamada Toby?"


@pytest.fixture
def providers(monkeypatch):
    script = {"gemini": [], "gemini_backup": [], "groq": []}
    use_fake_stream(monkeypatch, lambda name: script[name].pop(0) if script[name] else failure())
    return script


@pytest.fixture
def rag_on(monkeypatch, db_session):
    selected = crud.get_extra_info(db_session, fixed_answer=False)[:3]
    monkeypatch.setattr(retrieval, "select_extra_info", lambda _m, _p: selected)


def ask(client, message=QUESTION):
    return client.post("/chat", json={"message": message})


def total():
    return chat_stats.snapshot()["total"]


def test_counts_a_rag_answer_from_gemini(client, providers, rag_on):
    providers["gemini"].append(ok("Respuesta de Gemini"))
    ask(client)
    stats = total()
    assert stats["messages"] == 1
    assert stats["answered_gemini"] == 1
    assert stats["rag"] == 1
    assert stats["plan_b"] == 0
    assert stats["average_total"] is not None
    assert stats["average_first_text"] is not None


def test_counts_errors_plan_b_and_keywords(client, providers):
    providers["gemini"].append(failure(429))
    providers["groq"].append(ok("Respuesta de Groq"))
    ask(client)
    stats = total()
    assert stats["plan_b"] == 1
    assert stats["keywords"] == 1
    assert stats["errors_gemini"] == 1
    assert stats["errors_429"] == 1
    assert stats["answered_groq"] == 1


def test_counts_unanswered_questions(client, providers):
    ask(client)
    assert total()["unanswered"] == 1
    assert total()["errors_gemini"] == total()["errors_groq"] == 1


def test_counts_blocked_messages(client, providers, monkeypatch):
    monkeypatch.setattr(limits.per_minute, "limit", 1)
    providers["gemini"].append(ok("Hola"))
    ask(client)
    assert ask(client).status_code == 429
    assert total()["blocked_per_minute"] == 1
    assert total()["messages"] == 1


def test_stats_are_grouped_by_day_and_old_days_are_removed():
    now = [datetime(2026, 11, 1, tzinfo=timezone.utc)]
    stats = ChatStats(clock=lambda: now[0])
    stats.count("messages")
    now[0] += timedelta(days=1)
    stats.count("messages", 2)
    snapshot = stats.snapshot()
    assert list(snapshot["days"]) == ["2026-11-02", "2026-11-01"]
    assert snapshot["days"]["2026-11-02"]["messages"] == 2
    assert snapshot["total"]["messages"] == 3
    now[0] += timedelta(days=200)
    stats.count("messages")
    assert len(stats.snapshot()["days"]) <= 90


def test_unknown_counter_is_an_error():
    with pytest.raises(KeyError):
        chat_stats.count("preguntas")


def test_admin_page_does_not_exist_without_a_token(client):
    assert client.get("/admin/stats").status_code == 404


def test_admin_page_does_not_exist_with_a_short_token(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "corto")
    assert client.get("/admin/stats", auth=("admin", "corto")).status_code == 404


def test_admin_page_asks_for_the_token(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)
    response = client.get("/admin/stats")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"].startswith("Basic")
    assert client.get("/admin/stats", auth=("admin", "otro-token-cualquiera-123")).status_code == 401


def test_admin_page_shows_stats_and_questions_without_the_ip(client, providers, rag_on, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)
    monkeypatch.setenv("CLIENT_IP_HEADER", "CF-Connecting-IP")
    providers["gemini"].append(ok("Respuesta de Gemini"))
    client.post("/chat", json={"message": QUESTION}, headers={"CF-Connecting-IP": "203.0.113.7"})

    response = client.get("/admin/stats", auth=("cualquiera", TOKEN))
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    page = response.text
    for label in COUNTERS.values():
        assert label in page
    assert "Mensajes que quedan del tope global" in page
    assert f"{limits.remaining_total()} de {chat_limits.MESSAGES_PER_DAY_TOTAL}" in page
    # La pregunta y su respuesta salen en el registro; la IP, nunca.
    assert "Toby" in page
    assert "Respuesta de Gemini" in page
    assert "203.0.113.7" not in page


def test_admin_page_is_not_in_the_docs(client):
    assert "/admin" not in client.get("/openapi.json").text


def test_remaining_total_counts_down(client, providers):
    before = limits.remaining_total()
    providers["gemini"].append(ok("Hola"))
    ask(client)
    assert limits.remaining_total() == before - 1


@pytest.mark.parametrize(("value", "expected"), [(None, 7), ("", 7), (" 12 ", 12)])
def test_limits_come_from_the_environment(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("CHAT_TEST_LIMIT", raising=False)
    else:
        monkeypatch.setenv("CHAT_TEST_LIMIT", value)
    assert chat_limits.positive_int_from_env("CHAT_TEST_LIMIT", 7) == expected


@pytest.mark.parametrize("value", ["cinco", "0", "-3", "2.5"])
def test_invalid_limits_stop_the_start(monkeypatch, value):
    monkeypatch.setenv("CHAT_TEST_LIMIT", value)
    with pytest.raises(ValueError, match="CHAT_TEST_LIMIT"):
        chat_limits.positive_int_from_env("CHAT_TEST_LIMIT", 7)


def test_index_uses_the_configured_message_length(client):
    page = client.get("/").text
    assert f'maxlength="{chat_limits.MAX_MESSAGE_LENGTH}"' in page
    assert "{{" not in page


def test_counts_skipped_providers(client, providers, monkeypatch):
    from app import llm

    for _ in range(llm.TIMEOUTS_BEFORE_SKIPPING):
        llm.provider_health.record("gemini", "ReadTimeout")
    providers["gemini_backup"].append(ok("De la reserva"))
    ask(client)
    stats = total()
    assert stats["skipped_gemini"] == 1
    assert stats["errors_gemini"] == 0
    assert stats["answered_gemini_backup"] == 1
