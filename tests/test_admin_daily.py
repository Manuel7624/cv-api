"""Tabla de mensajes por día, indicador del tope global y aviso de UTC en el panel."""
import re
from datetime import datetime, timedelta, timezone

import pytest

from app import chat
from app.admin import DAILY_DAYS, SUMMARY_DAYS, daily_row, daily_table
from app.stats import COUNTERS, ChatStats, chat_stats
from fakes import failure, ok, use_fake_stream

TOKEN = "token-de-prueba-muy-largo-123"
NOW = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def clock(monkeypatch):
    """Reloj fijo para las estadísticas (y así, un "hoy" conocido)."""
    now = [NOW]
    monkeypatch.setattr(chat_stats, "clock", lambda: now[0])
    return now


def page(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)
    return client.get("/admin/stats", auth=("x", TOKEN)).text


def table_rows(html):
    """{etiqueta: [valores]} de la tabla por días."""
    table = html.split("<table class='daily'>")[1].split("</table>")[0]
    result = {}
    for label, cells in re.findall(r"<tr[^>]*><th scope='row'>([^<]*)</th>(.*?)</tr>", table):
        result[label] = [int(v) for v in re.findall(r"<td>(\d+)</td>", cells)]
    return result


def fill(day_offset, **counts):
    """Apunta contadores en el día NOW + day_offset y devuelve el reloj a NOW."""
    original = chat_stats.clock
    chat_stats.clock = lambda: NOW + timedelta(days=day_offset)
    try:
        for name, value in counts.items():
            chat_stats.count(name, value)
    finally:
        chat_stats.clock = original


def test_table_shows_30_days_with_today_first(client, monkeypatch, clock):
    rows = table_rows(page(client, monkeypatch))
    labels = [label for label in rows if label.startswith("2026")]
    assert len(labels) == DAILY_DAYS
    assert labels[0] == "2026-11-17 (hoy)"
    assert labels[1] == "2026-11-16"
    assert labels[-1] == "2026-10-19"


def test_columns_per_day(client, monkeypatch, clock):
    fill(0, messages=10, no_information=2, unanswered=1, internal_errors=1,
         answered_gemini=4, answered_gemini_backup=1, answered_groq=3, answered_groq_keywords=1)
    rows = table_rows(page(client, monkeypatch))
    # mensajes, sin información, errores, Gemini, Gemini reserva, Groq, Groq palabras clave
    assert rows["2026-11-17 (hoy)"] == [10, 2, 2, 4, 1, 2, 1]


def test_summaries_add_up_the_last_7_and_30_days(client, monkeypatch, clock):
    fill(0, messages=5, answered_gemini=5)
    fill(-3, messages=4, no_information=1, answered_gemini=3, answered_groq=1)
    fill(-10, messages=7, answered_gemini_backup=7)  # fuera de los 7 días, dentro de los 30
    fill(-40, messages=100)  # fuera de los 30 días
    rows = table_rows(page(client, monkeypatch))
    assert rows[f"Últimos {SUMMARY_DAYS} días"][0] == 9
    assert rows[f"Últimos {DAILY_DAYS} días"][0] == 16
    assert rows[f"Últimos {SUMMARY_DAYS} días"][1] == 1
    assert rows[f"Últimos {DAILY_DAYS} días"][4] == 7
    assert 100 not in rows[f"Últimos {DAILY_DAYS} días"]


def test_daily_table_uses_the_snapshot_without_more_queries(monkeypatch):
    """Todo sale del snapshot que ya se pide: la tabla no consulta nada más."""
    stats_ = ChatStats(clock=lambda: NOW)
    stats_.count("messages", 3)
    snapshot = stats_.snapshot()

    class NoStore:
        def __getattr__(self, name):
            raise AssertionError("la tabla no debe consultar la base de datos")

    monkeypatch.setattr(chat_stats, "store", NoStore())
    html = daily_table(snapshot, NOW.date())
    assert "<td>3</td>" in html


def test_page_makes_one_stats_query(client, monkeypatch, tmp_path, clock):
    from app.stats_store import StatsStore

    store = StatsStore(f"sqlite:///{tmp_path / 'stats.db'}")
    monkeypatch.setattr(chat_stats, "store", store)
    calls = []
    real = store.load
    monkeypatch.setattr(store, "load", lambda: calls.append(1) or real())
    page(client, monkeypatch)
    assert calls == [1]


def test_page_says_everything_is_utc(client, monkeypatch, clock):
    chat_stats.log_question("¿Pregunta?", "Respuesta", "gemini", "answered")
    html = page(client, monkeypatch)
    assert "Todas las horas y los días de este panel están en UTC" in html
    assert "Día (UTC)" in html
    assert "Fecha (UTC)" in html  # ya lo decían las tablas de preguntas


def test_global_cap_indicator_says_used_of_total(client, monkeypatch, clock):
    from app.rate_limit import chat_limits

    for index in range(3):
        chat_limits.check(f"203.0.113.{index}")
    html = page(client, monkeypatch)
    assert f'<strong>3 de {chat_limits.total.limit}</strong>' in html
    assert "usados en las últimas 24 horas" in html


def test_daily_table_is_protected(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)
    body = client.get("/admin/stats").text
    assert "Mensajes por día" not in body
    assert client.get("/admin/stats").status_code == 401


def test_columns_never_go_negative():
    values = {name: 0 for name in COUNTERS}
    values.update(answered_groq=1, answered_groq_keywords=2)
    assert daily_row(values)[5] == 0


# --- Los contadores nuevos que se apuntan al responder ---


@pytest.fixture
def providers(monkeypatch):
    script = {"gemini": [], "gemini_backup": [], "groq": []}
    use_fake_stream(monkeypatch, lambda name: script[name].pop(0) if script[name] else failure())
    return script


def test_no_information_answers_are_counted_per_day(client, providers, monkeypatch):
    monkeypatch.setattr(chat.retrieval, "select_extra_info", lambda *_: None)
    answer = "Sobre eso no tengo información aquí. Puedo contarte sobre mi experiencia."
    providers["gemini"].append(ok(answer))
    client.post("/chat", json={"message": "¿Color favorito?"})
    providers["gemini"].append(ok("Respuesta normal"))
    client.post("/chat", json={"message": "¿Qué es Balancea?"})
    total = chat_stats.snapshot()["total"]
    assert total["messages"] == 2 and total["no_information"] == 1


def test_groq_with_keywords_is_counted_apart(client, providers, monkeypatch):
    monkeypatch.setattr(chat.retrieval, "select_extra_info", lambda *_: None)
    providers["groq"].append(ok("Respuesta de Groq"))
    client.post("/chat", json={"message": "¿Qué sabes de Docker?"})
    total = chat_stats.snapshot()["total"]
    assert total["answered_groq"] == 1 and total["answered_groq_keywords"] == 1
    assert daily_row(total)[5:] == [0, 1]
