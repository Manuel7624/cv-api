import httpx
import pytest
from fakes import failure, ok, stream_response, use_fake_stream

from app import llm

QUESTION = [{"role": "user", "content": "pregunta"}]


def use_providers(monkeypatch, responses):
    """`responses` asocia cada proveedor con su respuesta (o una excepción)."""
    return use_fake_stream(monkeypatch, lambda name: responses[name])


def ask(*args):
    """Respuesta final: une los trozos y, con RESTART, descarta lo anterior."""
    answer = ""
    for event in llm.ask_providers(*args):
        answer = "" if event is llm.RESTART else answer + event
    return answer


def test_gemini_is_the_main_provider(monkeypatch):
    calls = use_providers(monkeypatch, {"gemini": ok("De Gemini")})
    assert ask("reglas", QUESTION) == "De Gemini"
    assert [call["provider"] for call in calls] == ["gemini"]


def test_answer_arrives_in_pieces(monkeypatch):
    use_providers(monkeypatch, {"gemini": stream_response("  Ho", "la", " mundo")})
    assert list(llm.ask_providers("reglas", QUESTION)) == ["Ho", "la", " mundo"]


def test_request_format(monkeypatch):
    calls = use_providers(monkeypatch, {"gemini": ok("Hola")})
    history = [
        {"role": "user", "content": "¿Sabe Python?"},
        {"role": "assistant", "content": "Sí, de las prácticas."},
    ]
    ask("reglas", [*history, *QUESTION])
    call = calls[0]
    assert call["headers"]["Authorization"] == "Bearer test-gemini-key"
    assert call["json"]["messages"] == [
        {"role": "system", "content": "reglas"},
        *history,
        {"role": "user", "content": "pregunta"},
    ]
    assert call["json"]["max_tokens"] == llm.MAX_ANSWER_TOKENS
    assert call["json"]["stream"] is True


def chunks(*items):
    """Respuesta con trozos arbitrarios (para probar formatos inesperados)."""
    return httpx.Response(
        200,
        content="\n\n".join(f"data: {item}" for item in items).encode(),
        request=httpx.Request("POST", "https://x.test"),
    )


@pytest.mark.parametrize(
    "failure_response",
    [
        failure(429),
        failure(413),
        failure(500),
        stream_response(""),
        stream_response(),
        chunks("esto no es JSON"),
        chunks("{}"),
        chunks('{"error": {"message": "fallo"}}'),
        httpx.ReadTimeout("tiempo agotado"),
        httpx.ConnectError("sin conexión"),
    ],
)
def test_groq_answers_when_gemini_fails(monkeypatch, failure_response):
    calls = use_providers(monkeypatch, {"gemini": failure_response, "groq": ok("De Groq")})
    assert ask("reglas", QUESTION) == "De Groq"
    assert [call["provider"] for call in calls] == ["gemini", "groq"]


def test_restart_when_a_provider_fails_halfway(monkeypatch):
    halfway = chunks(
        '{"choices": [{"delta": {"content": "Empiezo a responder"}}]}', "roto"
    )
    use_providers(monkeypatch, {"gemini": halfway, "groq": ok("De Groq")})
    events = list(llm.ask_providers("reglas", QUESTION))
    assert events[0] == "Empiezo a responder"
    assert events[1] is llm.RESTART
    assert "".join(events[2:]) == "De Groq"


def test_groq_answers_when_gemini_has_no_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY")
    calls = use_providers(monkeypatch, {"groq": ok("De Groq")})
    assert ask("reglas", QUESTION) == "De Groq"
    assert [call["provider"] for call in calls] == ["groq"]


def test_no_text_when_all_providers_fail(monkeypatch):
    use_providers(monkeypatch, {"gemini": failure(429), "groq": httpx.ConnectError("sin conexión")})
    assert list(llm.ask_providers("reglas", QUESTION)) == []


def test_changing_providers_only_needs_the_list(monkeypatch):
    provider = llm.Provider("otro", "https://groq.example/chat", "GROQ_API_KEY", "modelo")
    monkeypatch.setattr(llm, "PROVIDERS", [provider])
    calls = use_providers(monkeypatch, {"groq": ok("Del nuevo")})
    assert ask("reglas", QUESTION) == "Del nuevo"
    assert calls[0]["json"]["model"] == "modelo"
    assert calls[0]["timeout"] == llm.REQUEST_TIMEOUT_SECONDS


def test_errors_do_not_reveal_the_key(monkeypatch, caplog):
    error = httpx.ConnectError("fallo")
    use_providers(monkeypatch, {"groq": error, "gemini": error})
    with caplog.at_level("WARNING", logger="uvicorn.error"):
        ask("reglas", QUESTION)
    assert "gemini" in caplog.text
    assert "test-groq-key" not in caplog.text
    assert "test-gemini-key" not in caplog.text


def test_timeouts_per_provider(monkeypatch):
    calls = use_providers(monkeypatch, {"gemini": failure(429), "groq": ok("Hola")})
    ask("reglas", QUESTION)
    assert calls[0]["timeout"] == 10
    assert calls[1]["timeout"] == llm.REQUEST_TIMEOUT_SECONDS
    assert [c["provider"] for c in calls] == ["gemini", "groq"]


def test_each_attempt_is_recorded(monkeypatch):
    use_providers(monkeypatch, {"gemini": failure(429), "groq": ok("Hola")})
    attempts = []
    ask("reglas", QUESTION, attempts)
    assert [(a.provider, a.error) for a in attempts] == [("gemini", "respuesta 429"), ("groq", None)]
    assert attempts[0].describe().startswith("gemini falla (respuesta 429)")
    assert attempts[1].describe().startswith("groq ok (primer texto")
