"""Conexión con la base de datos.

La dirección de la base se lee de la variable de entorno DATABASE_URL. Si no
existe, se usa un archivo SQLite local. Para pasar a PostgreSQL bastará con
cambiar esa variable e instalar su driver.
"""
import os
import sqlite3
from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./cv.db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    """Clase base de la que heredan todas las tablas (ver app/models.py)."""


@event.listens_for(Engine, "connect")
def enable_sqlite_foreign_keys(connection, _record) -> None:
    """SQLite no aplica las claves foráneas salvo que se le pida en cada conexión."""
    if isinstance(connection, sqlite3.Connection):
        connection.execute("PRAGMA foreign_keys=ON")


def get_db() -> Iterator[Session]:
    """Abre una sesión para cada petición y la cierra al terminar."""
    with SessionLocal() as session:
        yield session
