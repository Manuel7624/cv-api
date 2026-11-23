"""La aplicación deja dormir a Neon: solo se conecta cuando hay algo que guardar o
cuando hace falta leer (el primer mensaje del chat o /admin/stats)."""
import pytest
from sqlalchemy import event

from app import chat, stats
from app.rate_limit import ChatLimits, chat_limits
from app.stats import ChatStats, chat_stats
from app.stats_store import StatsStore


class CountingStore(StatsStore):
    """Base SQLite de prueba que cuenta cada vez que se usa una conexión."""

    def __init__(self, url: str) -> None:
        super().__init__(url)
        self.connections = 0

        @event.listens_for(self.engine, "checkout")
        def count(*_args):
            self.connections += 1


@pytest.fixture
def store(tmp_path, monkeypatch):
    counting = CountingStore(f"sqlite:///{tmp_path / 'stats.db'}")
    monkeypatch.setattr(chat_stats, "store", counting)
    monkeypatch.setattr(chat_limits, "loader", chat_stats.load_limit_uses)
    monkeypatch.setattr(chat_limits, "restored", False)
    yield counting
    counting.close()


def test_idle_flushes_never_connect_even_when_cleanup_is_due(tmp_path, monkeypatch):
    store = CountingStore(f"sqlite:///{tmp_path / 'stats.db'}")
    stats_ = ChatStats()
    stats_.store = store
    clock = [1000.0]
    monkeypatch.setattr(stats.time, "monotonic", lambda: clock[0])
    for _ in range(24):  # un día entero sin mensajes, comprobando cada hora
        assert stats_.flush()
        clock[0] += stats.CLEANUP_SECONDS + 1
    assert store.connections == 0


def test_cleanup_goes_with_the_next_write(tmp_path, monkeypatch):
    store = CountingStore(f"sqlite:///{tmp_path / 'stats.db'}")
    stats_ = ChatStats()
    stats_.store = store
    calls = []
    real_add = store.add
    monkeypatch.setattr(store, "add", lambda *a, **k: calls.append(k) or real_add(*a, **k))
    stats_.count("messages")
    assert stats_.flush()
    assert calls[0]["delete_before"] is not None  # primera escritura: también limpia
    stats_.count("messages")
    assert stats_.flush()
    assert calls[1]["delete_before"] is None  # no ha pasado una hora


@pytest.mark.parametrize("path", ["/health", "/", "/profile", "/skills", "/static/chat.js", "/docs", "/openapi.json"])
def test_visits_that_do_not_use_the_chat_never_touch_neon(client, store, path):
    """Por ejemplo, un servicio que visita /health cada pocos minutos."""
    for _ in range(5):
        assert client.get(path).status_code == 200
    assert chat_stats.flush()
    assert store.connections == 0
    assert not chat_limits.restored


def test_limits_are_loaded_with_the_first_chat_message_only(client, store, monkeypatch):
    monkeypatch.setattr(chat, "ask_providers", lambda *_, **__: iter(["Respuesta"]))
    monkeypatch.setattr(chat.retrieval, "select_extra_info", lambda *_: None)
    loads = []
    monkeypatch.setattr(chat_limits, "loader", lambda: loads.append(1) or [])
    client.get("/health")
    assert loads == []
    for _ in range(3):
        client.post("/chat", json={"message": "hola"})
    assert loads == [1]


def test_restored_limits_still_apply_after_a_lazy_load():
    clock = [10_000.0]
    limits = ChatLimits(clock=lambda: clock[0])
    key = limits.ip_key("203.0.113.7")
    limits.loader = lambda: [(key, clock[0] - 10)] * limits.per_minute.limit
    assert limits.check("203.0.113.7") == "per_minute"
    assert limits.check("198.51.100.1") is None
