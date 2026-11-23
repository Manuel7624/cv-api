"""Los límites del chat sobreviven a los reinicios guardando en la base de datos
solo un hash con sal de la IP, y siguen funcionando en memoria si la base falla."""
from datetime import datetime, timedelta, timezone

import pytest

from app.rate_limit import BLOCKED_PER_DAY, BLOCKED_PER_MINUTE, BLOCKED_TOTAL, ChatLimits, chat_limits
from app.stats import ChatStats, chat_stats
from app.stats_store import StatsStore, limit_uses_table

IP = "203.0.113.7"
TOKEN = "token-de-prueba-muy-largo-123"


class Clock:
    def __init__(self, start=datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)):
        self.now = start

    def seconds(self) -> float:
        return self.now.timestamp()

    def datetime(self) -> datetime:
        return self.now


@pytest.fixture
def url(tmp_path):
    return f"sqlite:///{tmp_path / 'stats.db'}"


@pytest.fixture
def salt(monkeypatch):
    monkeypatch.setenv("LIMITS_HASH_SALT", "sal-de-prueba")


def service(url, clock):
    """Un arranque del servicio: estadísticas con base de datos y límites recuperados."""
    stats_ = ChatStats(clock=clock.datetime)
    stats_.store = StatsStore(url)
    limits = ChatLimits(clock=clock.seconds)
    limits.on_use = stats_.log_limit_use
    limits.restore(stats_.load_limit_uses())
    return stats_, limits


def saved_rows(url):
    store = StatsStore(url)
    store._ensure_table()
    with store.engine.begin() as connection:
        return [dict(row._mapping) for row in connection.execute(limit_uses_table.select())]


def test_daily_limits_survive_a_restart(url, salt):
    clock = Clock()
    stats_, limits = service(url, clock)
    limits.per_day.limit = 3
    for _ in range(3):
        assert limits.check(IP) is None
        clock.now += timedelta(minutes=1)
    assert stats_.flush()
    stats_.close()

    # Render duerme el servicio y lo arranca de cero al volver una visita.
    clock.now += timedelta(hours=2)
    stats_, limits = service(url, clock)
    limits.per_day.limit = 3
    assert limits.check(IP) == BLOCKED_PER_DAY
    assert limits.check("198.51.100.1") is None  # otra IP sí puede
    assert limits.remaining_total() == limits.total.limit - 4


def test_global_limit_survives_a_restart(url, salt):
    clock = Clock()
    stats_, limits = service(url, clock)
    limits.total.limit = 2
    assert limits.check("198.51.100.1") is None
    assert limits.check("198.51.100.2") is None
    stats_.close()

    stats_, limits = service(url, clock)
    limits.total.limit = 2
    assert limits.check("198.51.100.3") == BLOCKED_TOTAL


def test_per_minute_limit_survives_a_quick_restart(url, salt):
    clock = Clock()
    stats_, limits = service(url, clock)
    for _ in range(limits.per_minute.limit):
        assert limits.check(IP) is None
    stats_.close()
    clock.now += timedelta(seconds=10)
    _, limits = service(url, clock)
    assert limits.check(IP) == BLOCKED_PER_MINUTE


def test_the_ip_is_never_saved_only_a_salted_hash(url, salt):
    clock = Clock()
    stats_, limits = service(url, clock)
    limits.check(IP)
    stats_.flush()
    rows = saved_rows(url)
    assert len(rows) == 1
    assert IP not in str(rows)
    assert len(rows[0]["key"]) == 64
    # Con otra sal, la misma IP da otro hash: sin la sal no se puede comprobar.
    assert ChatLimits().ip_key(IP) == rows[0]["key"]
    other = ChatLimits()
    other.salt = b"otra-sal"
    assert other.ip_key(IP) != rows[0]["key"]
    # En memoria tampoco se guarda la IP.
    assert IP not in str(limits.per_day.uses)


def test_blocked_messages_are_not_counted_or_saved(url, salt):
    clock = Clock()
    stats_, limits = service(url, clock)
    for _ in range(limits.per_minute.limit + 3):
        limits.check(IP)
    stats_.flush()
    assert len(saved_rows(url)) == limits.per_minute.limit
    assert limits.remaining_total() == limits.total.limit - limits.per_minute.limit


def test_uses_older_than_24_hours_are_deleted_and_not_loaded(url, salt):
    clock = Clock()
    stats_, limits = service(url, clock)
    limits.check(IP)
    assert stats_.flush()
    clock.now += timedelta(hours=25)
    limits.check("198.51.100.9")  # guardar otro uso borra los que ya no cuentan
    assert stats_.flush()
    keys = [row["key"] for row in saved_rows(url)]
    assert keys == [limits.ip_key("198.51.100.9")]
    assert stats_.load_limit_uses() == [(limits.ip_key("198.51.100.9"), clock.seconds())]


def test_restore_ignores_old_uses():
    clock = Clock()
    limits = ChatLimits(clock=clock.seconds)
    old = clock.seconds() - 25 * 60 * 60
    assert limits.restore([("a", old), ("b", clock.seconds() - 60)]) == 1
    assert limits.remaining_total() == limits.total.limit - 1


def test_limits_keep_working_in_memory_if_the_database_fails(tmp_path, salt):
    clock = Clock()
    broken = f"sqlite:///{tmp_path / 'no-existe' / 'stats.db'}"
    stats_, limits = service(broken, clock)  # al arrancar no puede cargar nada
    for _ in range(limits.per_minute.limit):
        assert limits.check(IP) is None
    assert not stats_.flush()
    assert limits.check(IP) == BLOCKED_PER_MINUTE


def test_checking_a_limit_never_touches_the_database(url, salt, monkeypatch):
    clock = Clock()
    stats_, limits = service(url, clock)

    def fail(*_args, **_kwargs):
        raise AssertionError("el chat no debe esperar a la base de datos")

    monkeypatch.setattr(stats_.store, "add", fail)
    monkeypatch.setattr(stats_.store, "limit_uses", fail)
    assert limits.check(IP) is None
    assert stats_.pending_limit_uses


def test_without_salt_a_random_one_is_used(monkeypatch):
    monkeypatch.delenv("LIMITS_HASH_SALT", raising=False)
    assert ChatLimits().ip_key(IP) != ChatLimits().ip_key(IP)


def test_the_app_saves_limit_uses_through_the_stats(client, url, monkeypatch):
    """La app real: cada mensaje permitido del chat se apunta para la base de datos."""
    from app import chat

    monkeypatch.setattr(chat, "ask_providers", lambda *_, **__: iter(["Respuesta"]))
    monkeypatch.setattr(chat_stats, "store", StatsStore(url))
    client.post("/chat", json={"message": "¿Hola?"})
    assert chat_stats.flush()
    rows = saved_rows(url)
    assert len(rows) == 1
    assert "testclient" not in str(rows)


def test_admin_page_explains_what_is_saved(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)
    page = client.get("/admin/stats", auth=("x", TOKEN)).text
    assert "Sin preguntas" not in page
    assert "Las preguntas se guardan de forma anónima, sin IPs" in page
    assert "se borran a los\n    30 días" in page
