"""Presupuesto de tiempo del chat: el primer texto no tarda más de unos segundos aunque
Gemini falle, y un proveedor que falla varias veces seguidas se salta un rato."""
import dataclasses
import time

import httpx
import pytest
from fakes import failure, ok, use_fake_stream

from app import llm

QUESTION = [{"role": "user", "content": "pregunta"}]


@pytest.fixture
def fast_limits(monkeypatch):
    """Los mismos proveedores, con límites diminutos para que las pruebas sean rápidas."""
    limits = {"gemini": 0.3, "gemini_backup": 0.2, "groq": 0.2}
    monkeypatch.setattr(llm, "PROVIDERS", [
        dataclasses.replace(p, first_text_seconds=limits[p.name]) for p in llm.PROVIDERS
    ])
    monkeypatch.setattr(llm, "FIRST_TEXT_BUDGET_SECONDS", 0.8)
    monkeypatch.setattr(llm, "LAST_RESORT_MIN_SECONDS", 0.2)


def use_slow_providers(monkeypatch, responses, delays):
    """Cada proveedor tarda `delays[nombre]` segundos en empezar a responder."""
    def answer_for(name):
        time.sleep(delays.get(name, 0))
        return responses.get(name, failure())
    return use_fake_stream(monkeypatch, answer_for)


def run(attempts=None, started=None):
    """(respuesta final, segundos hasta el primer texto)."""
    start = time.perf_counter()
    first, answer = None, ""
    for event in llm.ask_providers("reglas", QUESTION, attempts, started=started):
        if first is None and event is not llm.RESTART:
            first = time.perf_counter() - start
        answer = "" if event is llm.RESTART else answer + event
    return answer, first


def test_a_slow_gemini_is_dropped_at_its_deadline(monkeypatch, fast_limits):
    use_slow_providers(
        monkeypatch,
        {"gemini": ok("De Gemini"), "gemini_backup": ok("De la reserva")},
        {"gemini": 1.0},
    )
    attempts = []
    answer, first = run(attempts)
    assert answer == "De la reserva"  # nunca se mezcla con lo que llegue tarde
    assert first < 0.3 + 0.2 + 0.2  # su límite más la reserva, no el segundo entero
    assert "ReadTimeout" in attempts[0].error and "sin texto" in attempts[0].error


def test_worst_case_is_inside_the_budget(monkeypatch, fast_limits):
    """Los dos Gemini lentos: Groq contesta dentro del presupuesto."""
    use_slow_providers(
        monkeypatch,
        {"gemini": ok("G"), "gemini_backup": ok("B"), "groq": ok("De Groq")},
        {"gemini": 1.0, "gemini_backup": 1.0},
    )
    answer, first = run()
    assert answer == "De Groq"
    assert first < llm.FIRST_TEXT_BUDGET_SECONDS


def test_the_last_resort_always_gets_a_minimum_of_time(monkeypatch, fast_limits):
    """Si el presupuesto ya se ha gastado, Groq aun así tiene su mínimo."""
    use_slow_providers(monkeypatch, {"groq": ok("De Groq")}, {"groq": 0.1})
    attempts = []
    answer, _ = run(attempts, started=time.perf_counter() - 5)  # llegó hace 5 s
    assert answer == "De Groq"
    assert [a.provider for a in attempts if a.error is None] == ["groq"]


def test_the_deadline_is_counted_from_when_the_question_arrived(monkeypatch, fast_limits):
    """Si la búsqueda ya gastó tiempo, a Gemini le queda menos."""
    calls = use_slow_providers(
        monkeypatch,
        {"gemini": ok("De Gemini"), "gemini_backup": ok("De la reserva")},
        {"gemini": 0.2},
    )
    attempts = []
    # Presupuesto 0.8 s, llegó hace 0.7 s: a Gemini le quedan 0.1 s y no le da tiempo.
    answer, _ = run(attempts, started=time.perf_counter() - 0.7)
    assert answer == "De la reserva"
    assert attempts[0].provider == "gemini" and attempts[0].error
    assert calls[0]["provider"] == "gemini"


def test_a_stall_after_the_first_text_is_not_cut_by_the_first_text_deadline(monkeypatch, fast_limits):
    """El límite corto es solo hasta el primer texto: respondiendo, manda el de siempre."""
    use_providers = use_fake_stream(monkeypatch, lambda name: ok("Respuesta completa"))
    answer, first = run()
    assert answer == "Respuesta completa" and first < 0.2
    assert [c["provider"] for c in use_providers] == ["gemini"]


@pytest.mark.parametrize("error", [httpx.ReadTimeout("lento"), failure(429), failure(503)])
def test_any_failure_twice_in_a_row_skips_gemini(monkeypatch, error):
    """Error, 429 o timeout: a la segunda, se salta Gemini y se va directo a la reserva."""
    monkeypatch.setattr(llm, "provider_health", llm.ProviderHealth())
    calls = use_fake_stream(
        monkeypatch, lambda name: error if name == "gemini" else ok("De la reserva")
    )
    for _ in range(llm.FAILURES_BEFORE_SKIPPING):
        run()
    calls.clear()
    attempts = []
    answer, _ = run(attempts)
    assert answer == "De la reserva"
    assert [c["provider"] for c in calls] == ["gemini_backup"]
    assert attempts[0].skipped


def test_one_failure_is_not_enough_and_a_success_resets_the_count(monkeypatch):
    health = llm.ProviderHealth()
    monkeypatch.setattr(llm, "provider_health", health)
    health.record("gemini", "respuesta 429")
    assert not health.should_skip("gemini")
    health.record("gemini", None)  # ha respondido: se olvida el fallo
    health.record("gemini", "ReadTimeout")
    assert not health.should_skip("gemini")
    health.record("gemini", "respuesta 503")
    assert health.should_skip("gemini")


def test_after_the_pause_one_failure_skips_again_at_once():
    now = [0.0]
    health = llm.ProviderHealth(clock=lambda: now[0])
    for _ in range(llm.FAILURES_BEFORE_SKIPPING):
        health.record("gemini", "respuesta 429")
    assert health.should_skip("gemini")
    now[0] += llm.SKIP_SECONDS
    assert not health.should_skip("gemini")  # se prueba con la siguiente pregunta
    health.record("gemini", "respuesta 429")
    assert health.should_skip("gemini")  # y si falla, otra vez a la reserva


def test_default_provider_limits_fit_the_eight_second_budget():
    first_text = {p.name: p.first_text_seconds for p in llm.PROVIDERS}
    assert first_text["gemini"] == 4 and first_text["gemini_backup"] == 2
    worst_case = first_text["gemini"] + first_text["gemini_backup"] + llm.LAST_RESORT_MIN_SECONDS
    assert worst_case <= llm.FIRST_TEXT_BUDGET_SECONDS + 0.5
    assert llm.FIRST_TEXT_BUDGET_SECONDS <= 8
    assert llm.SKIP_SECONDS >= 120


def test_if_everyone_fails_a_slow_gemini_still_gets_until_the_hard_cap(monkeypatch, fast_limits):
    """Gemini tarda más que su límite (0.3 s), la reserva y Groq fallan: en vez de dar el
    mensaje de error, se aprovecha la respuesta de Gemini si llega antes del tope."""
    monkeypatch.setattr(llm, "HARD_CAP_SECONDS", 1.5)
    use_slow_providers(monkeypatch, {"gemini": ok("Tarde pero bien")}, {"gemini": 0.7})
    attempts = []
    answer, first = run(attempts)
    assert answer == "Tarde pero bien"
    assert 0.6 < first < 1.5
    assert attempts[-1].provider == "gemini" and attempts[-1].error is None  # quien respondió


def test_a_slow_gemini_that_misses_the_hard_cap_gives_no_answer(monkeypatch, fast_limits):
    monkeypatch.setattr(llm, "HARD_CAP_SECONDS", 0.8)
    use_slow_providers(monkeypatch, {"gemini": ok("Demasiado tarde")}, {"gemini": 1.5})
    answer, first = run()
    assert answer == "" and first is None


def test_a_slow_gemini_is_not_used_when_a_later_provider_answers(monkeypatch, fast_limits):
    use_slow_providers(
        monkeypatch, {"gemini": ok("De Gemini"), "groq": ok("De Groq")}, {"gemini": 0.8}
    )
    answer, _ = run()
    assert answer == "De Groq"
