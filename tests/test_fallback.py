"""Orden de respaldo del chat, simulando los fallos de cada proveedor.

1. RAG con Gemini. 2. RAG con Groq. 3. Sin embeddings: Gemini con toda la información.
4. Sin embeddings y Gemini caído: Groq con lo que quepa, elegido por palabras clave.
5. Todo falla: mensaje amable con el correo.
"""
import json

import httpx
import pytest
from fakes import failure, ok, stream_response, use_fake_stream

from app import chat, crud, keywords, llm, retrieval
from app.seed import EXTRA_INFO

EXTRA = [item for item in EXTRA_INFO if not item["fixed_answer"]]
NO_INFO = "No tengo esa información aquí, pero puedes escribirme a mi correo."


def extras_in(prompt):
    return [item for item in EXTRA if json.dumps(item["answer"], ensure_ascii=False)[1:-1] in prompt]


@pytest.fixture
def providers(monkeypatch):
    """Simula Gemini y Groq: cada uno responde con lo que haya en su lista, o falla."""
    script = {"gemini": [], "gemini_backup": [], "groq": []}
    calls = use_fake_stream(
        monkeypatch, lambda name: script[name].pop(0) if script[name] else failure()
    )
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
    assert [c["provider"] for c in calls] == ["gemini", "gemini_backup", "groq"]
    assert calls[0]["prompt"] == calls[1]["prompt"] == calls[2]["prompt"]
    assert len(extras_in(calls[2]["prompt"])) == 3


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
    assert [c["provider"] for c in calls] == ["gemini", "gemini_backup", "groq"]

    prompt = calls[2]["prompt"]
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
    assert [c["provider"] for c in calls] == ["gemini", "gemini_backup", "groq"]


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
    assert [c["provider"] for c in calls] == ["gemini", "gemini", "gemini_backup", "groq"]
    assert "ATENCIÓN: en esta pregunta solo tienes una parte" in calls[3]["prompt"]


def test_no_more_attempts_when_both_providers_fail_with_rag(client, providers, rag_on):
    _script, calls = providers
    assert "manusastrenar@gmail.com" in ask(client)
    assert [c["provider"] for c in calls] == ["gemini", "gemini_backup", "groq"]


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
    included = extras_in(calls[2]["prompt"])
    assert any(item["question"].startswith("¿Qué haces en tu tiempo libre?") for item in included)


def test_keeps_the_rag_answer_if_the_retry_with_everything_fails(client, providers, rag_on):
    """Si el RAG dijo que no lo sabe y el plan B no consigue respuesta, se usa la del RAG."""
    script, calls = providers
    script["gemini"].append(ok(NO_INFO))
    assert ask(client) == NO_INFO
    assert [c["provider"] for c in calls] == ["gemini", "gemini", "gemini_backup", "groq"]


def test_logs_time_and_path_without_the_question(client, providers, rag_on, caplog):
    script, _calls = providers
    script["gemini"] += [ok(NO_INFO), ok("Con toda la información")]
    with caplog.at_level("INFO", logger="uvicorn.error"):
        ask(client, "¿Tienes un perro llamado Toby?")
    line = next(r.message for r in caplog.records if r.message.startswith("Chat:"))
    assert "s en total" in line
    assert "búsqueda RAG" in line and "RAG: | gemini ok" in line
    assert "plan B: | gemini ok" in line
    assert "Toby" not in caplog.text


def stream_events(client, message="¿Tienes carnet de conducir?"):
    """Eventos de POST /chat/stream: textos y "RESTART"."""
    response = client.post("/chat/stream", json={"message": message})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = []
    for block in response.text.split("\n\n"):
        if block.startswith("data: "):
            data = json.loads(block.removeprefix("data: "))
            events.append("RESTART" if data.get("restart") else data["text"])
    return events


def test_stream_sends_the_answer_in_pieces(client, providers):
    script, _calls = providers
    script["gemini"].append(ok("Hola, soy la IA de Manuel"))
    assert stream_events(client) == ["Hola, soy la", " IA de Manuel"]


def test_stream_hides_the_rag_answer_that_has_no_information(client, providers, rag_on):
    script, _calls = providers
    script["gemini"] += [ok(NO_INFO), ok("Con toda la información")]
    assert "".join(stream_events(client)) == "Con toda la información"


def test_stream_restarts_if_the_rag_says_no_information_at_the_end(client, providers, rag_on):
    script, _calls = providers
    late = "Te cuento lo que sí sé de mis prácticas y de mis proyectos personales. " * 2 + NO_INFO
    script["gemini"] += [ok(late), ok("Con toda la información")]
    events = stream_events(client)
    assert "RESTART" in events
    after = events[len(events) - events[::-1].index("RESTART"):]
    assert "".join(after) == "Con toda la información"


def test_stream_restarts_if_gemini_fails_halfway(client, providers, rag_on):
    script, calls = providers
    text = stream_response("x" * 200, done=False).text + "\n\ndata: roto"
    script["gemini"].append(
        httpx.Response(200, content=text.encode(), request=httpx.Request("POST", "https://x.test"))
    )
    script["groq"].append(ok("Respuesta de Groq"))
    events = stream_events(client)
    assert events[0] == "x" * 200
    assert events[1] == "RESTART"
    assert "".join(events[2:]) == "Respuesta de Groq"
    assert [c["provider"] for c in calls] == ["gemini", "gemini_backup", "groq"]


def test_stream_has_the_same_limits_as_chat(client, providers, monkeypatch):
    from app import rate_limit
    monkeypatch.setattr(rate_limit.chat_limits, "check", lambda _ip: "per_minute")
    response = client.post("/chat/stream", json={"message": "Hola"})
    assert response.status_code == 429
    assert client.post("/chat/stream", json={"message": ""}).status_code == 422
