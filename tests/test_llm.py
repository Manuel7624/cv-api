import httpx
import pytest

from app import llm


def fake_response(text="Hola", status_code=200):
    return httpx.Response(
        status_code,
        json={"choices": [{"message": {"content": text}}]},
        request=httpx.Request("POST", "https://example.test"),
    )


def use_fake_post(monkeypatch, responses):
    """Sustituye httpx.post. `responses` asocia cada proveedor con su respuesta."""
    calls = []

    def fake_post(url, **kwargs):
        name = "groq" if "groq" in url else "gemini"
        calls.append({"provider": name, "url": url, **kwargs})
        result = responses[name]
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(httpx, "post", fake_post)
    return calls


def test_groq_is_the_main_provider(monkeypatch):
    calls = use_fake_post(monkeypatch, {"groq": fake_response("De Groq")})
    assert llm.ask_providers("reglas", "pregunta") == "De Groq"
    assert [call["provider"] for call in calls] == ["groq"]


def test_request_format(monkeypatch):
    calls = use_fake_post(monkeypatch, {"groq": fake_response()})
    llm.ask_providers("reglas", "pregunta")
    call = calls[0]
    assert call["headers"]["Authorization"] == "Bearer test-groq-key"
    assert call["json"]["messages"] == [
        {"role": "system", "content": "reglas"},
        {"role": "user", "content": "pregunta"},
    ]
    assert call["json"]["max_tokens"] == llm.MAX_ANSWER_TOKENS
    assert call["timeout"] == llm.REQUEST_TIMEOUT_SECONDS


@pytest.mark.parametrize(
    "failure",
    [
        fake_response(status_code=429),
        fake_response(status_code=500),
        fake_response(text=""),
        fake_response(text=None),
        httpx.Response(200, text="esto no es JSON", request=httpx.Request("POST", "https://x.test")),
        httpx.Response(200, json={}, request=httpx.Request("POST", "https://x.test")),
        httpx.ReadTimeout("tiempo agotado"),
        httpx.ConnectError("sin conexión"),
    ],
)
def test_gemini_answers_when_groq_fails(monkeypatch, failure):
    calls = use_fake_post(monkeypatch, {"groq": failure, "gemini": fake_response("De Gemini")})
    assert llm.ask_providers("reglas", "pregunta") == "De Gemini"
    assert [call["provider"] for call in calls] == ["groq", "gemini"]


def test_gemini_answers_when_groq_has_no_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY")
    calls = use_fake_post(monkeypatch, {"gemini": fake_response("De Gemini")})
    assert llm.ask_providers("reglas", "pregunta") == "De Gemini"
    assert [call["provider"] for call in calls] == ["gemini"]


def test_returns_none_when_all_providers_fail(monkeypatch):
    use_fake_post(
        monkeypatch,
        {"groq": fake_response(status_code=429), "gemini": httpx.ConnectError("sin conexión")},
    )
    assert llm.ask_providers("reglas", "pregunta") is None


def test_changing_providers_only_needs_the_list(monkeypatch):
    provider = llm.Provider("otro", "https://groq.example/chat", "GROQ_API_KEY", "modelo")
    monkeypatch.setattr(llm, "PROVIDERS", [provider])
    calls = use_fake_post(monkeypatch, {"groq": fake_response("Del nuevo")})
    assert llm.ask_providers("reglas", "pregunta") == "Del nuevo"
    assert calls[0]["json"]["model"] == "modelo"


def test_errors_do_not_reveal_the_key(monkeypatch, caplog):
    use_fake_post(monkeypatch, {"groq": httpx.ConnectError("fallo"), "gemini": httpx.ConnectError("fallo")})
    with caplog.at_level("WARNING", logger="uvicorn.error"):
        llm.ask_providers("reglas", "pregunta")
    assert "groq" in caplog.text
    assert "test-groq-key" not in caplog.text
    assert "test-gemini-key" not in caplog.text
