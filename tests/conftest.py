"""Configuración común de los tests.

Cada test usa su propia base SQLite en memoria, ya cargada con los datos
iniciales, así que no depende de cv.db ni lo modifica.
"""
from collections.abc import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app import retrieval
from app.rate_limit import chat_limits
from app.seed import seed


@pytest.fixture
def db_session() -> Iterator[Session]:
    # StaticPool mantiene una sola conexión: al cerrarla, la base en memoria
    # desaparecería. FastAPI puede usarla desde otro hilo, de ahí check_same_thread.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed(session)
        yield session
    engine.dispose()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db_session
    # Sin "with", TestClient no ejecuta el arranque de la app y no toca cv.db.
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def isolate_chat(monkeypatch, tmp_path) -> Iterator[None]:
    """Ningún test debe llamar a las APIs reales ni depender de otro test."""

    def blocked_post(*_args, **_kwargs):
        raise AssertionError("Un test ha intentado llamar a una API real")

    monkeypatch.setattr(httpx, "post", blocked_post)
    monkeypatch.setattr(httpx, "stream", blocked_post)
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.delenv("CLIENT_IP_HEADER", raising=False)
    monkeypatch.setattr(retrieval, "index", None)
    # Los tests nunca escriben en app/embeddings.json.
    monkeypatch.setattr(retrieval, "CACHE_PATH", tmp_path / "embeddings.json")
    chat_limits.reset()
    yield
    chat_limits.reset()
