import httpx
import pytest
from fakes import failure, ok, stream_response, use_fake_stream

from app import llm

QUESTION = [{"role": "user", "content": "pregunta"}]


def use_providers(monkeypatch, responses):
    """`responses` asocia cada proveedor con su respuesta (o una excepción).
    Los que no aparecen fallan con un error 500."""
    return use_fake_stream(monkeypatch, lambda name: responses.get(name, failure()))


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
    assert [call["provider"] for call in calls] == ["gemini", "gemini_backup", "groq"]


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
    calls = use_providers(monkeypatch, {"otro": ok("Del nuevo")})
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
    assert calls[0]["timeout"] == calls[1]["timeout"] == 10
    assert calls[2]["timeout"] == llm.REQUEST_TIMEOUT_SECONDS
    assert [c["provider"] for c in calls] == ["gemini", "gemini_backup", "groq"]


def test_each_attempt_is_recorded(monkeypatch):
    use_providers(monkeypatch, {"gemini": failure(429), "groq": ok("Hola")})
    attempts = []
    ask("reglas", QUESTION, attempts)
    assert [(a.provider, a.error) for a in attempts] == [
        ("gemini", "respuesta 429"),
        ("gemini_backup", "respuesta 500"),
        ("groq", None),
    ]
    assert attempts[0].describe().startswith("gemini falla (respuesta 429)")
    assert attempts[2].describe().startswith("groq ok (primer texto")


def test_gemini_backup_answers_before_groq(monkeypatch):
    calls = use_providers(
        monkeypatch,
        {"gemini": httpx.ReadTimeout("lento"), "gemini_backup": ok("De la reserva"), "groq": ok("De Groq")},
    )
    assert ask("reglas", QUESTION) == "De la reserva"
    assert [c["provider"] for c in calls] == ["gemini", "gemini_backup"]
    assert calls[0]["json"]["model"] != calls[1]["json"]["model"]
    assert calls[1]["headers"]["Authorization"] == "Bearer test-gemini-key"


def test_provider_is_skipped_after_repeated_timeouts(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(llm, "provider_health", llm.ProviderHealth(clock=lambda: now[0]))
    responses = {"gemini": httpx.ReadTimeout("lento"), "gemini_backup": ok("De la reserva")}
    calls = use_providers(monkeypatch, responses)
    for _ in range(llm.TIMEOUTS_BEFORE_SKIPPING):
        ask("reglas", QUESTION)
    calls.clear()

    attempts = []
    assert ask("reglas", QUESTION, attempts) == "De la reserva"
    assert [c["provider"] for c in calls] == ["gemini_backup"]  # ni lo intenta
    assert attempts[0].skipped and "saltado" in attempts[0].describe()

    # Pasado el tiempo se vuelve a probar; si responde, se olvidan los timeouts.
    now[0] += llm.SKIP_SECONDS
    responses["gemini"] = ok("De Gemini")
    calls.clear()
    assert ask("reglas", QUESTION) == "De Gemini"
    assert not llm.provider_health.should_skip("gemini")


def test_other_errors_do_not_skip_a_provider(monkeypatch):
    calls = use_providers(monkeypatch, {"gemini": failure(429), "gemini_backup": ok("Hola")})
    for _ in range(llm.TIMEOUTS_BEFORE_SKIPPING + 1):
        ask("reglas", QUESTION)
    calls.clear()
    ask("reglas", QUESTION)
    assert calls[0]["provider"] == "gemini"


def test_if_all_providers_are_skipped_all_are_tried(monkeypatch):
    """Mejor una respuesta lenta que ninguna."""
    for provider in llm.PROVIDERS:
        for _ in range(llm.TIMEOUTS_BEFORE_SKIPPING):
            llm.provider_health.record(provider.name, "ReadTimeout")
    calls = use_providers(monkeypatch, {"groq": ok("De Groq")})
    assert ask("reglas", QUESTION) == "De Groq"
    assert [c["provider"] for c in calls] == ["gemini", "gemini_backup", "groq"]


def test_a_skipped_provider_is_tried_if_all_later_ones_are_skipped(monkeypatch):
    for name in ("gemini_backup", "groq"):
        for _ in range(llm.TIMEOUTS_BEFORE_SKIPPING):
            llm.provider_health.record(name, "ReadTimeout")
    calls = use_providers(monkeypatch, {"gemini": ok("De Gemini")})
    assert ask("reglas", QUESTION) == "De Gemini"
    assert [c["provider"] for c in calls] == ["gemini"]


def test_a_stream_closed_without_a_finish_reason_is_an_incomplete_answer(monkeypatch):
    """Si el proveedor cierra el flujo sin avisar de que ha terminado, la respuesta puede
    estar cortada a mitad de frase: se descarta y responde el siguiente proveedor."""
    cut = stream_response("Porque aporto las ganas de aprender y la base técnica de", finish=False)
    use_providers(monkeypatch, {"gemini": cut, "gemini_backup": ok("Respuesta completa"), "groq": ok("De Groq")})
    events = list(llm.ask_providers("reglas", QUESTION))
    assert events[0].startswith("Porque aporto")
    assert events[1] is llm.RESTART
    assert "".join(events[2:]) == "Respuesta completa"


def test_incomplete_answer_error_is_named_and_does_not_count_as_a_timeout(monkeypatch):
    cut = stream_response("Texto cortado", finish=False)
    use_providers(monkeypatch, {"gemini": cut, "gemini_backup": cut, "groq": cut})
    attempts = []
    list(llm.ask_providers("reglas", QUESTION, attempts))
    assert [a.error for a in attempts] == ["respuesta incompleta"] * 3
    assert not llm.provider_health.should_skip("gemini")


def test_a_complete_stream_with_a_finish_reason_is_accepted(monkeypatch):
    use_providers(monkeypatch, {"gemini": ok("Respuesta entera")})
    assert ask("reglas", QUESTION) == "Respuesta entera"
