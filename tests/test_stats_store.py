"""Estadísticas guardadas en base de datos (en los tests, SQLite en un archivo)."""
import pytest

from app import stats
from app.stats import ChatStats, chat_stats
from app.stats_store import StatsStore, make_engine

TOKEN = "token-de-prueba-muy-largo-123"
SECRET_URL = "postgresql://usuario:clave-secreta@ejemplo.neon.tech/estadisticas"


@pytest.fixture
def url(tmp_path):
    return f"sqlite:///{tmp_path / 'stats.db'}"


@pytest.fixture
def broken_url(tmp_path):
    """Base de datos que falla al momento (una carpeta que no existe)."""
    return f"sqlite:///{tmp_path / 'no-existe' / 'stats.db'}"


def connected_stats(url):
    """ChatStats con base de datos, sin el hilo (se envía a mano con flush)."""
    stats_ = ChatStats()
    stats_.store = StatsStore(url)
    return stats_


def test_stats_survive_a_restart(url):
    first = connected_stats(url)
    first.count("messages", 3)
    first.add_time("total", 2.0)
    assert first.flush()
    first.close()

    second = connected_stats(url)  # como si el servicio se hubiera reiniciado
    second.count("messages")
    second.add_time("total", 4.0)
    snapshot = second.snapshot()
    assert snapshot["source"] == "database"
    assert snapshot["total"]["messages"] == 4  # 3 guardados + 1 pendiente
    assert snapshot["total"]["average_total"] == 3.0


def test_flush_adds_to_what_is_saved_and_empties_pending(url):
    stats_ = connected_stats(url)
    stats_.count("messages")
    assert stats_.flush()
    stats_.count("messages")
    assert stats_.flush()
    assert not stats_.pending
    assert StatsStore(url).load()[next(iter(stats_.memory))]["messages"] == 2


def test_without_database_everything_keeps_working_in_memory(broken_url):
    stats_ = connected_stats(broken_url)
    stats_.count("messages")
    assert not stats_.flush()
    assert stats_.pending  # se conserva para el siguiente intento
    snapshot = stats_.snapshot()
    assert snapshot["source"] == "memory"
    assert snapshot["database_configured"]
    assert snapshot["total"]["messages"] == 1


def test_pending_is_sent_when_the_database_comes_back(url, monkeypatch):
    stats_ = connected_stats(url)
    real_add = stats_.store.add
    monkeypatch.setattr(stats_.store, "add", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("caída")))
    stats_.count("messages", 2)
    assert not stats_.flush()
    monkeypatch.setattr(stats_.store, "add", real_add)
    assert stats_.flush()
    assert stats_.snapshot()["total"]["messages"] == 2


def test_counting_never_touches_the_database(url, monkeypatch):
    stats_ = connected_stats(url)

    def fail(*_args, **_kwargs):
        raise AssertionError("el chat no debe esperar a la base de datos")

    monkeypatch.setattr(stats_.store, "add", fail)
    monkeypatch.setattr(stats_.store, "load", fail)
    stats_.count("messages")
    stats_.add_time("first_text", 1.0)


def test_close_sends_what_is_pending(url):
    stats_ = ChatStats()
    stats_.connect(url, flush_seconds=3600)  # el hilo no llega a enviar nada
    stats_.count("messages")
    stats_.close()
    assert sum(day["messages"] for day in StatsStore(url).load().values()) == 1


def test_invalid_url_means_memory_only(caplog):
    stats_ = ChatStats()
    with caplog.at_level("WARNING", logger="uvicorn.error"):
        stats_.connect("esto no es una cadena de conexión")
    assert stats_.store is None
    stats_.count("messages")
    assert stats_.snapshot()["total"]["messages"] == 1


def test_errors_never_show_the_connection_string(caplog, monkeypatch):
    stats_ = connected_stats(SECRET_URL)

    def fail(*_args, **_kwargs):  # como los errores de psycopg, que pueden incluir la cadena
        raise OSError(f"no se pudo conectar a {SECRET_URL}")

    monkeypatch.setattr(stats_.store, "add", fail)
    monkeypatch.setattr(stats_.store, "load", fail)
    stats_.count("messages")
    with caplog.at_level("WARNING", logger="uvicorn.error"):
        stats_.flush()
        stats_.snapshot()
    assert "sin conexión" in caplog.text
    assert "clave-secreta" not in caplog.text
    assert "ejemplo.neon.tech" not in caplog.text


def test_neon_urls_use_the_psycopg_driver_with_short_timeouts():
    engine = make_engine("postgresql://u:p@ejemplo.neon.tech/db?sslmode=require")
    assert engine.url.drivername == "postgresql+psycopg"
    assert engine.url.query["sslmode"] == "require"


def test_admin_page_says_where_the_data_comes_from(client, monkeypatch, url, broken_url):
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)
    page = client.get("/admin/stats", auth=("x", TOKEN)).text
    assert "solo en memoria" in page

    monkeypatch.setattr(chat_stats, "store", StatsStore(broken_url))
    page = client.get("/admin/stats", auth=("x", TOKEN)).text
    assert "Sin conexión con la base de datos" in page

    monkeypatch.setattr(chat_stats, "store", StatsStore(url))
    page = client.get("/admin/stats", auth=("x", TOKEN)).text
    assert "Datos guardados en PostgreSQL" in page


def test_flush_interval_is_short():
    assert stats.FLUSH_SECONDS <= 10
