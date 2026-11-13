"""Orden de respaldo del chat, simulando los fallos de cada proveedor.

1. RAG con Gemini. 2. RAG con Groq. 3. Sin embeddings: Gemini con toda la información.
4. Sin embeddings y Gemini caído: Groq con lo que quepa, elegido por palabras clave.
5. Todo falla: mensaje amable con el correo.
"""
import json

import httpx
import pytest

from app import chat, crud, keywords, llm, retrieval
from app.seed import EXTRA_INFO

EXTRA = [item for item in EXTRA_INFO if not item["fixed_answer"]]
NO_INFO = "No tengo esa información aquí, pero puedes escribirme a mi correo."


def ok(text):
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": text}}]},
        request=httpx.Request("POST", "https://x.test"),
    )


def failure(status=500):
    return httpx.Response(status, request=httpx.Request("POST", "https://x.test"))


def extras_in(prompt):
    return [item for item in EXTRA if json.dumps(item["answer"], ensure_ascii=False)[1:-1] in prompt]


@pytest.fixture
def providers(monkeypatch):
    """Simula Gemini y Groq: cada uno responde con lo que haya en su lista, o falla."""
    script = {"gemini": [], "groq": []}
    calls = []

    def fake_post(url, **kwargs):
        name = "groq" if "groq" in url else "gemini"
        calls.append({"provider": name, "prompt": kwargs["json"]["messages"][0]["content"]})
        result = script[name].pop(0) if script[name] else failure()
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(httpx, "post", fake_post)
    return script, calls


@pytest.fixture
def rag_on(monkeypatch, db_session):
    """Simula que el RAG está disponible y elige 3 respuestas."""
    selected = crud.get_extra_info(db_session, fixed_answer=False)[:3]
    monkeypatch.setattr(retrieval, "select_extra_info", lambda _message, _previous: selected)
    return selected


def ask(client, message="¿Tienes carnet de conducir?", history=None):
    body = {"message": message}
    if history:
        body["history"] = history
    return client.post("/chat", json=body).json()["answer"]


def test_case_1_rag_with_gemini(client, providers, rag_on):
    script, calls = providers
    script["gemini"].append(ok("Respuesta de Gemini"))
    assert ask(client) == "Respuesta de Gemini"
    assert [c["provider"] for c in calls] == ["gemini"]
    assert len(extras_in(calls[0]["prompt"])) == 3


def test_case_2_rag_with_groq(client, providers, rag_on):
    script, calls = providers
    script["groq"].append(ok("Respuesta de Groq"))
    assert ask(client) == "Respuesta de Groq"
    assert [c["provider"] for c in calls] == ["gemini", "groq"]
    assert calls[0]["prompt"] == calls[1]["prompt"]
    assert len(extras_in(calls[1]["prompt"])) == 3


def test_case_3_without_embeddings_gemini_gets_everything(client, providers):
    script, calls = providers
    script["gemini"].append(ok("Con todo"))
    assert ask(client) == "Con todo"
    assert [c["provider"] for c in calls] == ["gemini"]
    assert len(extras_in(calls[0]["prompt"])) == len(EXTRA)
    assert "ATENCIÓN: en esta pregunta solo tienes una parte" not in calls[0]["prompt"]


def test_case_4_groq_gets_what_fits_chosen_by_keywords(client, providers):
    script, calls = providers
    script["groq"].append(ok("Por palabras clave"))
    assert ask(client, "¿Tienes carnet de conducir?") == "Por palabras clave"
    assert [c["provider"] for c in calls] == ["gemini", "groq"]

    prompt = calls[1]["prompt"]
    groq = next(p for p in llm.PROVIDERS if p.name == "groq")
    budget = groq.max_request_tokens * chat.TOKEN_SAFETY_MARGIN - llm.MAX_ANSWER_TOKENS
    assert chat.estimate_tokens(prompt) <= budget
    included = extras_in(prompt)
    assert 0 < len(included) < len(EXTRA)
    assert any(item["question"] == "¿Carnet de conducir?" for item in included)
    assert "ATENCIÓN: en esta pregunta solo tienes una parte" in prompt
    # El CV, las reglas y las respuestas fijas van siempre.
    assert "Brainy Inteligencia Semántica" in prompt
    assert "Expectativas salariales" in prompt
    assert "NO INVENTES NADA" in prompt


def test_case_4_includes_as_many_answers_as_fit(client, providers, monkeypatch):
    script, calls = providers
    groq = next(p for p in llm.PROVIDERS if p.name == "groq")
    big_groq = llm.Provider(**{**groq.__dict__, "max_request_tokens": 10**6})
    monkeypatch.setattr(llm, "PROVIDERS", [llm.PROVIDERS[0], big_groq])
    script["groq"].append(ok("Todo cabe"))
    ask(client)
    assert len(extras_in(calls[1]["prompt"])) == len(EXTRA)


def test_case_5_everything_fails(client, providers):
    _script, calls = providers
    assert "manusastrenar@gmail.com" in ask(client)
    assert [c["provider"] for c in calls] == ["gemini", "groq"]


def test_rag_without_the_answer_goes_to_case_3(client, providers, rag_on):
    script, calls = providers
    script["gemini"] += [ok(NO_INFO), ok("Con toda la información")]
    assert ask(client) == "Con toda la información"
    assert [c["provider"] for c in calls] == ["gemini", "gemini"]
    assert len(extras_in(calls[1]["prompt"])) == len(EXTRA)


def test_rag_without_the_answer_and_gemini_down_goes_to_case_4(client, providers, rag_on):
    script, calls = providers
    script["gemini"] += [ok(NO_INFO), failure()]
    script["groq"].append(ok("Por palabras clave"))
    assert ask(client) == "Por palabras clave"
    assert [c["provider"] for c in calls] == ["gemini", "gemini", "groq"]
    assert "ATENCIÓN: en esta pregunta solo tienes una parte" in calls[2]["prompt"]


def test_no_more_attempts_when_both_providers_fail_with_rag(client, providers, rag_on):
    _script, calls = providers
    assert "manusastrenar@gmail.com" in ask(client)
    assert [c["provider"] for c in calls] == ["gemini", "groq"]


def test_keywords_are_only_used_in_case_4(client, providers, rag_on, monkeypatch):
    used = []
    real_rank = keywords.rank
    monkeypatch.setattr(keywords, "rank", lambda *args: used.append(1) or real_rank(*args))
    script, _calls = providers
    script["gemini"].append(ok("RAG con Gemini"))
    ask(client)
    script["gemini"].append(failure())
    script["groq"].append(ok("RAG con Groq"))
    ask(client)
    assert used == []


def test_case_4_uses_the_previous_question(client, providers):
    script, calls = providers
    script["groq"].append(ok("Seguimiento"))
    history = [
        {"role": "user", "content": "¿Qué haces en tu tiempo libre?"},
        {"role": "assistant", "content": "Juego al fútbol."},
    ]
    ask(client, "¿Y desde hace cuánto?", history)
    included = extras_in(calls[1]["prompt"])
    assert any(item["question"] == "¿Qué haces en tu tiempo libre?" for item in included)


def test_keeps_the_rag_answer_if_the_retry_with_everything_fails(client, providers, rag_on):
    """Si el RAG dijo que no lo sabe y el plan B no consigue respuesta, se usa la del RAG."""
    script, calls = providers
    script["gemini"].append(ok(NO_INFO))
    assert ask(client) == NO_INFO
    assert [c["provider"] for c in calls] == ["gemini", "gemini", "groq"]
