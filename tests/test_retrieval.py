"""Tests del RAG con embeddings simulados: nunca se llama a Gemini de verdad."""
import json
import math
import re

import httpx
import pytest

from app import chat, retrieval
from app.seed import EXTRA_INFO

WORDS = ["python", "java", "docker", "carnet", "inglés", "balancea", "remoto", "sql"]


def fake_vector(text):
    """Vector que cuenta palabras clave: dos textos se parecen si comparten palabras."""
    words = re.findall(r"\w+", text.lower())
    return [words.count(word) + 0.01 for word in WORDS]


@pytest.fixture
def fake_embed(monkeypatch):
    calls = []

    def embed(texts):
        calls.append(texts)
        return [retrieval.normalize(fake_vector(text)) for text in texts]

    monkeypatch.setattr(retrieval, "embed", embed)
    return calls


def in_prompt(item, prompt):
    """Las respuestas van en JSON dentro del prompt, con comillas y saltos escapados."""
    return json.dumps(item["answer"], ensure_ascii=False)[1:-1] in prompt


def items(*answers):
    return [{"tema": "T", "pregunta": f"Pregunta {i}", "respuesta": a} for i, a in enumerate(answers)]


def test_index_is_built_once_and_not_per_question(fake_embed):
    retrieval.build_index(items("Sé Python", "Sé Java"))
    assert len(fake_embed) == 1
    retrieval.select_extra_info("¿Sabe Python?", [])
    retrieval.select_extra_info("¿Sabe Java?", [])
    # Una llamada al arrancar y una por pregunta (solo para la pregunta).
    assert [len(texts) for texts in fake_embed] == [2, 1, 1]


def test_returns_the_most_similar_answers_in_original_order(fake_embed, monkeypatch):
    monkeypatch.setattr(retrieval, "TOP_K", 2)
    retrieval.build_index(items("Python y Docker", "Java", "Docker con Python", "Carnet"))
    selected = retrieval.select_extra_info("¿Docker y Python?", [])
    assert [item["respuesta"] for item in selected] == ["Python y Docker", "Docker con Python"]


def test_follow_up_questions_use_the_previous_question(fake_embed):
    retrieval.build_index(items("Inglés B2", "Java en el grado"))
    retrieval.select_extra_info("¿y qué tal?", ["¿Habla inglés?"])
    assert "¿Habla inglés? ¿y qué tal?" in fake_embed[-1][0]


def test_low_similarity_means_plan_b(fake_embed, monkeypatch):
    monkeypatch.setattr(retrieval, "MIN_SIMILARITY", 0.9)
    retrieval.build_index(items("Python", "Java"))
    assert retrieval.select_extra_info("¿Cuál es la capital de Francia?", []) is None


def test_search_errors_mean_plan_b(fake_embed, monkeypatch):
    retrieval.build_index(items("Python"))

    def broken(_texts):
        raise retrieval.RetrievalError("respuesta 429")

    monkeypatch.setattr(retrieval, "embed", broken)
    assert retrieval.select_extra_info("¿Sabe Python?", []) is None


def test_index_errors_disable_rag(monkeypatch):
    def broken(_texts):
        raise retrieval.RetrievalError("falta la clave")

    monkeypatch.setattr(retrieval, "embed", broken)
    retrieval.build_index(items("Python"))
    assert retrieval.index is None
    assert retrieval.select_extra_info("¿Sabe Python?", []) is None


def test_rag_can_be_switched_off(fake_embed, monkeypatch):
    monkeypatch.setattr(retrieval, "ENABLED", False)
    retrieval.build_index(items("Python"))
    assert retrieval.index is None
    assert fake_embed == []


def test_embed_request_format(monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        calls.append({"url": url, **kwargs})
        body = {"embeddings": [{"values": [3.0, 4.0]} for _ in kwargs["json"]["requests"]]}
        return httpx.Response(200, json=body, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    vectors = retrieval.embed(["uno", "dos"])
    assert vectors == [[0.6, 0.8], [0.6, 0.8]]
    call = calls[0]
    assert retrieval.EMBEDDING_MODEL in call["url"]
    assert call["headers"] == {"x-goog-api-key": "test-gemini-key"}
    request = call["json"]["requests"][0]
    assert request["content"]["parts"][0]["text"] == "uno"
    assert request["outputDimensionality"] == retrieval.DIMENSIONS


@pytest.mark.parametrize(
    "failure",
    [
        httpx.Response(429, request=httpx.Request("POST", "https://x.test")),
        httpx.Response(200, json={}, request=httpx.Request("POST", "https://x.test")),
        httpx.ConnectError("sin conexión"),
    ],
)
def test_embed_errors_become_retrieval_errors(monkeypatch, failure):
    def fake_post(*_args, **_kwargs):
        if isinstance(failure, Exception):
            raise failure
        return failure

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(retrieval.RetrievalError):
        retrieval.embed(["uno"])


def test_embed_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY")
    with pytest.raises(retrieval.RetrievalError):
        retrieval.embed(["uno"])


def test_normalize():
    assert retrieval.normalize([3.0, 4.0]) == [0.6, 0.8]
    assert math.isclose(retrieval.similarity([0.6, 0.8], [0.6, 0.8]), 1.0)


# --- El chat con RAG -------------------------------------------------------------


@pytest.fixture
def fake_ai(monkeypatch):
    calls = []
    answers = []

    def fake_ask(system_prompt, conversation):
        calls.append(system_prompt)
        return answers.pop(0) if answers else "Respuesta de prueba"

    monkeypatch.setattr(chat, "ask_providers", fake_ask)
    return calls, answers


def chat_with_rag(client, db_session, fake_embed, message="¿Sabe Python?"):
    from app import crud

    retrieval.build_index(crud.get_extra_info(db_session, fixed_answer=False))
    return client.post("/chat", json={"message": message})


def test_rag_sends_only_some_extra_info_but_always_cv_and_fixed_answers(
    client, db_session, fake_embed, fake_ai, monkeypatch,
):
    monkeypatch.setattr(retrieval, "MIN_SIMILARITY", -1)
    chat_with_rag(client, db_session, fake_embed)
    prompts, _ = fake_ai
    assert len(prompts) == 1
    prompt = prompts[0]
    extra = [item for item in EXTRA_INFO if not item["fixed_answer"]]
    included = [item for item in extra if in_prompt(item, prompt)]
    assert len(included) == retrieval.TOP_K
    assert "Brainy Inteligencia Semántica" in prompt
    assert "Expectativas salariales" in prompt
    assert "Nota media" in prompt
    assert "NO INVENTES NADA" in prompt


def test_plan_b_when_the_ai_has_no_information(client, db_session, fake_embed, fake_ai, monkeypatch):
    monkeypatch.setattr(retrieval, "MIN_SIMILARITY", -1)
    prompts, answers = fake_ai
    answers += ["No tengo esa información, pero puedes escribirle.", "Respuesta con todo"]
    response = chat_with_rag(client, db_session, fake_embed)
    assert response.json()["answer"] == "Respuesta con todo"
    assert len(prompts) == 2
    extra = [item for item in EXTRA_INFO if not item["fixed_answer"]]
    assert all(in_prompt(item, prompts[1]) for item in extra)


def test_plan_b_when_similarity_is_low(client, db_session, fake_embed, fake_ai, monkeypatch):
    monkeypatch.setattr(retrieval, "MIN_SIMILARITY", 2)
    chat_with_rag(client, db_session, fake_embed)
    prompts, _ = fake_ai
    assert len(prompts) == 1
    extra = [item for item in EXTRA_INFO if not item["fixed_answer"]]
    assert all(in_prompt(item, prompts[0]) for item in extra)


def test_no_retry_when_providers_are_down(client, db_session, fake_embed, monkeypatch):
    monkeypatch.setattr(retrieval, "MIN_SIMILARITY", -1)
    calls = []
    monkeypatch.setattr(chat, "ask_providers", lambda *args: calls.append(args))
    response = chat_with_rag(client, db_session, fake_embed)
    assert "Ahora mismo no puedo responder" in response.json()["answer"]
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("No tengo esa información, pero puedes escribirle.", True),
        ("Lo siento, no lo sé.", True),
        ("I don't have that information.", True),
        ("Todavía no tengo experiencia con esa tecnología.", False),
        ("No tengo esa información aquí, pero puedes escribirme a mi correo.", True),
        ("Solo puedo responder preguntas sobre el perfil profesional de Manuel.", False),
        ("Sabe Python de sus prácticas.", False),
    ],
)
def test_detects_answers_without_information(answer, expected):
    assert chat.says_no_information(answer) is expected
