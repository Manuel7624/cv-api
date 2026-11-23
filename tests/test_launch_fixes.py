"""Correcciones tras la batería de calidad: menos RAG para Groq, cupo diario de Groq,
tiempos hasta el primer texto visible y respuestas nuevas. Nunca llaman a Gemini ni a
Groq de verdad."""
import json
import re
import time

import httpx
import pytest
from fakes import failure, ok, use_fake_stream

from app import chat, llm, retrieval
from app.seed import EXTRA_INFO

QUESTION = [{"role": "user", "content": "pregunta"}]


# --- Groq: solo 6 trozos del RAG ---------------------------------------------------


def test_selection_keeps_the_most_similar_in_original_order():
    selection = retrieval.Selection(["a", "b", "c", "d"])
    selection.ranked = ["c", "a", "d", "b"]  # de más a menos parecida
    assert selection.top(2) == ["a", "c"]
    assert selection.top(10) == ["a", "b", "c", "d"]


def test_groq_gets_6_rag_answers_and_gemini_12(client, db_session, monkeypatch):
    def embed(texts, timeout=None):
        return [retrieval.normalize([1.0 + (hash(text) % 7), 0.5, 0.2]) for text in texts]

    monkeypatch.setattr(retrieval, "embed", embed)
    monkeypatch.setattr(retrieval, "MIN_SIMILARITY", -1)
    from app import crud

    retrieval.build_index(crud.get_extra_info(db_session, fixed_answer=False))
    prompts = {}

    def fake_ask(system_prompt, conversation, _steps=None, **_):
        for provider in llm.PROVIDERS:
            prompts[provider.name] = system_prompt(provider)
        yield "Respuesta de prueba"

    monkeypatch.setattr(chat, "ask_providers", fake_ask)
    assert client.post("/chat", json={"message": "¿Sabe Python?"}).status_code == 200

    def extra_in(prompt):
        return [item for item in EXTRA_INFO if not item["fixed_answer"]
                and json.dumps(item["answer"], ensure_ascii=False)[1:-1] in prompt]

    assert len(extra_in(prompts["gemini"])) == retrieval.TOP_K == 12
    assert len(extra_in(prompts["gemini_backup"])) == 12
    groq_items = extra_in(prompts["groq"])
    assert len(groq_items) == chat.GROQ_RAG_ITEMS == 6
    # Son 6 de las 12 de Gemini, y el prompt de Groq es más corto.
    assert all(item in extra_in(prompts["gemini"]) for item in groq_items)
    assert len(prompts["groq"]) < len(prompts["gemini"])


# --- Groq: cupo diario -------------------------------------------------------------

TPD_MESSAGE = (
    "Rate limit reached for model `openai/gpt-oss-120b` on tokens per day (TPD): Limit 200000, "
    "Used 199360, Requested 5980. Please try again in 38m26.88s."
)


def daily_429(retry_after=None):
    headers = {"retry-after": retry_after} if retry_after else {}
    return httpx.Response(
        429, headers=headers, request=httpx.Request("POST", "https://x.test"),
        json={"error": {"message": TPD_MESSAGE, "type": "tokens", "code": "rate_limit_exceeded"}},
    )


def test_daily_429_marks_the_provider_exhausted_until_the_time_it_says(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(llm, "provider_health", llm.ProviderHealth(clock=lambda: now[0]))
    calls = use_fake_stream(monkeypatch, lambda name: daily_429("2307") if name == "groq" else failure(503))
    attempts = []
    assert list(llm.ask_providers("reglas", QUESTION, attempts)) == []
    assert attempts[-1].provider == "groq" and "429" in attempts[-1].error
    assert llm.provider_health.is_exhausted("groq")

    # Hasta la hora que indica (38 min), Groq ni se intenta.
    calls.clear()
    now[0] += 2000
    attempts.clear()
    list(llm.ask_providers("reglas", QUESTION, attempts))
    assert "groq" not in [c["provider"] for c in calls]
    assert attempts[-1].provider == "groq" and attempts[-1].skipped and "sin cupo" in attempts[-1].describe()

    # Pasado el tiempo, vuelve a probarse.
    now[0] += 400
    calls.clear()
    list(llm.ask_providers("reglas", QUESTION))
    assert "groq" in [c["provider"] for c in calls]


def test_the_wait_comes_from_the_message_when_there_is_no_retry_after():
    assert llm.daily_limit_wait(daily_429()) == pytest.approx(38 * 60 + 26.88)
    assert llm.daily_limit_wait(daily_429("120")) == 120


def test_a_per_minute_429_does_not_exhaust_the_provider(monkeypatch):
    per_minute = httpx.Response(
        429, request=httpx.Request("POST", "https://x.test"),
        json={"error": {"message": "Rate limit reached on tokens per minute (TPM): Limit 8000"}},
    )
    assert llm.daily_limit_wait(per_minute) is None
    assert llm.daily_limit_wait(failure(429)) is None  # sin cuerpo
    monkeypatch.setattr(llm, "provider_health", llm.ProviderHealth())
    use_fake_stream(monkeypatch, lambda name: per_minute if name == "groq" else failure(503))
    list(llm.ask_providers("reglas", QUESTION))
    assert not llm.provider_health.is_exhausted("groq")


# --- Cortacircuitos: Gemini 3.5 se intenta si los demás no están disponibles ---------------


def trip(health, name, errors=None):
    for _ in range(llm.FAILURES_BEFORE_SKIPPING):
        health.record(name, "respuesta 503")


def test_gemini_is_tried_even_if_skipped_when_the_backup_and_groq_are_unavailable(monkeypatch):
    health = llm.ProviderHealth()
    monkeypatch.setattr(llm, "provider_health", health)
    trip(health, "gemini")
    trip(health, "gemini_backup")
    health.mark_exhausted("groq", 3600)
    calls = use_fake_stream(monkeypatch, lambda name: ok("De Gemini") if name == "gemini" else failure())
    assert "".join(llm.ask_providers("reglas", QUESTION)) == "De Gemini"
    assert [c["provider"] for c in calls] == ["gemini"]


def test_gemini_is_still_skipped_if_the_backup_is_available(monkeypatch):
    health = llm.ProviderHealth()
    monkeypatch.setattr(llm, "provider_health", health)
    trip(health, "gemini")
    calls = use_fake_stream(monkeypatch, lambda name: ok("De la reserva"))
    assert "".join(llm.ask_providers("reglas", QUESTION)) == "De la reserva"
    assert [c["provider"] for c in calls] == ["gemini_backup"]


def test_gemini_is_tried_if_the_backup_is_skipped_and_groq_has_no_quota(monkeypatch):
    health = llm.ProviderHealth()
    monkeypatch.setattr(llm, "provider_health", health)
    trip(health, "gemini")
    trip(health, "gemini_backup")
    health.mark_exhausted("groq", 60)
    attempts = []
    calls = use_fake_stream(monkeypatch, lambda name: failure(503))
    list(llm.ask_providers("reglas", QUESTION, attempts))
    assert [c["provider"] for c in calls] == ["gemini", "gemini_backup"]  # ni lo intenta con Groq
    assert [a.provider for a in attempts] == ["gemini", "gemini_backup", "groq"]


# --- Tiempos: parada a mitad antes de enseñar nada ---------------------------------------------


class StallingStream(httpx.SyncByteStream):
    """Envía el primer trozo y se queda parado, como Gemini cuando se cuelga a mitad."""

    def __init__(self, stall_seconds):
        self.stall_seconds = stall_seconds

    def __iter__(self):
        first = {"choices": [{"delta": {"content": "Empiezo y me"}}]}
        yield ("data: " + json.dumps(first) + "\n\n").encode()
        time.sleep(self.stall_seconds)
        rest = {"choices": [{"delta": {"content": " paro."}, "finish_reason": "stop"}]}
        yield ("data: " + json.dumps(rest) + "\n\ndata: [DONE]\n\n").encode()


def stalling_response(stall_seconds):
    return httpx.Response(200, stream=StallingStream(stall_seconds), request=httpx.Request("POST", "https://x.test"))


def test_a_stall_before_the_user_sees_anything_moves_on_to_the_next_provider(monkeypatch):
    monkeypatch.setattr(llm, "STALL_BEFORE_SHOWN_SECONDS", 0.3)
    use_fake_stream(monkeypatch, lambda name: stalling_response(2.0) if name == "gemini" else ok("De la reserva"))
    attempts = []
    start = time.perf_counter()
    events = list(llm.ask_providers("reglas", QUESTION, attempts, hold_chars=80))
    elapsed = time.perf_counter() - start
    assert elapsed < 1.5  # no espera los 10 s de siempre ni los 2 s de la parada
    assert events[-1] != llm.RESTART and "".join(e for e in events if isinstance(e, str)).endswith("De la reserva")
    assert llm.RESTART in events  # el chat ignora el RESTART si no había enseñado nada
    assert "a mitad de respuesta" in attempts[0].error


def test_without_a_hold_the_usual_wait_between_chunks_applies(monkeypatch):
    """Si el texto ya se ha enseñado (sin retención), una pausa corta no es un fallo."""
    monkeypatch.setattr(llm, "STALL_BEFORE_SHOWN_SECONDS", 0.2)
    use_fake_stream(monkeypatch, lambda name: stalling_response(0.6))
    assert "".join(llm.ask_providers("reglas", QUESTION)) == "Empiezo y me paro."


def test_the_hard_cap_includes_the_held_characters(monkeypatch):
    """Una respuesta tardía que no llega a mostrarse antes del tope no se espera."""
    monkeypatch.setattr(llm, "FIRST_TEXT_BUDGET_SECONDS", 0.5)
    monkeypatch.setattr(llm, "HARD_CAP_SECONDS", 0.8)
    monkeypatch.setattr(llm, "STALL_BEFORE_SHOWN_SECONDS", 5)
    monkeypatch.setattr(llm, "PROVIDERS", [llm.PROVIDERS[0]])

    def late_then_stalled(name):
        time.sleep(0.6)  # primer texto después del presupuesto, antes del tope
        return stalling_response(5.0)

    use_fake_stream(monkeypatch, late_then_stalled)
    start = time.perf_counter()
    events = list(llm.ask_providers("reglas", QUESTION, hold_chars=80))
    assert time.perf_counter() - start < 1.5  # no espera a que se muestre: el tope manda
    assert not [e for e in events if isinstance(e, str) and e.endswith("paro.")]


# --- Plan B comparte el presupuesto --------------------------------------------------------------


@pytest.fixture
def rag_with_fake_ai(client, db_session, monkeypatch):
    from app import crud

    def embed(texts, timeout=None):
        return [retrieval.normalize([1.0, 0.5, 0.2]) for _ in texts]

    monkeypatch.setattr(retrieval, "embed", embed)
    monkeypatch.setattr(retrieval, "MIN_SIMILARITY", -1)
    retrieval.build_index(crud.get_extra_info(db_session, fixed_answer=False))
    calls = []

    def fake_ask(system_prompt, conversation, _steps=None, **kwargs):
        calls.append(kwargs)
        yield "No tengo esa información, pero puedes escribirle." if len(calls) == 1 else "Respuesta con todo"

    monkeypatch.setattr(chat, "ask_providers", fake_ask)
    return client, calls


def test_plan_b_runs_with_the_same_start_time_as_the_question(rag_with_fake_ai):
    client, calls = rag_with_fake_ai
    answer = client.post("/chat", json={"message": "¿Sabe Python?"}).json()["answer"]
    assert answer == "Respuesta con todo"
    assert len(calls) == 2
    assert calls[0]["started"] == calls[1]["started"]  # el mismo reloj: un solo presupuesto
    assert calls[0]["hold_chars"] == chat.RAG_HOLD_CHARS and "hold_chars" not in calls[1]


def test_plan_b_is_not_repeated_when_the_budget_is_spent(rag_with_fake_ai, monkeypatch):
    client, calls = rag_with_fake_ai
    monkeypatch.setattr(chat, "FIRST_TEXT_BUDGET_SECONDS", 1.0)  # menos que PLAN_B_MIN_LEFT_SECONDS
    answer = client.post("/chat", json={"message": "¿Sabe Python?"}).json()["answer"]
    assert len(calls) == 1  # sin segunda ronda
    assert answer == "No tengo esa información, pero puedes escribirle."


# --- Respuestas nuevas ----------------------------------------------------------------


def entry(fragment):
    matches = [item for item in EXTRA_INFO if fragment in item["question"]]
    assert len(matches) == 1, fragment
    return matches[0]["answer"]


def sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+", text) if s]


def test_differentiator_has_its_own_answer_that_does_not_repeat_hiring_one():
    answer = entry("¿Qué te diferencia")
    hiring = entry("¿Por qué deberían contratarte?")
    assert answer.startswith("Lo que me diferencia es")
    assert not any(s in hiring for s in sentences(answer))
    # Codex solo en las prácticas y Claude Code solo en este proyecto.
    assert "con Claude Code" in answer and "con Codex, refactoricé" in answer


def test_github_answer_links_this_project_and_balancea():
    answer = entry("¿Dónde está el código de este proyecto?")
    assert "github.com/Manuel7624/cv-api" in answer
    assert "github.com/Manuel7624/TFG_ManuelSastre" in answer
    assert "este proyecto" in answer


def test_workers_answer_is_honest_about_the_count():
    answer = entry("¿Cuántos workers dockerizaste?")
    assert "desde cero uno" in answer and "no tengo una cifra exacta" in answer
    assert "el único" not in answer


def test_start_date_and_motivation_are_a_bit_longer():
    assert "disponibilidad inmediata" in entry("¿Cuándo puedes incorporarte?")
    motivation = entry("¿Qué te motiva?")
    assert 2 <= len(sentences(motivation)) <= 3
    assert "Balancea" in motivation and "aprender" in motivation
