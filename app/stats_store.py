"""Guardado de las estadísticas del chat en PostgreSQL (Neon), para que no se
pierdan cuando Render reinicia o duerme el servicio.

Solo se guardan contadores por día: una fila por día y nombre (por ejemplo,
"2026-11-16" y "messages") con su valor. Nada de preguntas, IPs ni datos
personales. Los datos del CV y del chat siguen en SQLite (app/database.py).

La cadena de conexión se lee de STATS_DATABASE_URL y no se muestra nunca: los
errores se registran solo con su tipo.
"""
from sqlalchemy import Column, Float, MetaData, String, Table, create_engine, select, text
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.engine import Connection, Engine

# Segundos máximos para conectar y para cada consulta: si Neon no responde, se
# abandona pronto (las estadísticas siguen en memoria mientras tanto).
CONNECT_TIMEOUT_SECONDS = 5
STATEMENT_TIMEOUT_MS = 5000

metadata = MetaData()

stats_table = Table(
    "chat_stats",
    metadata,
    Column("day", String(10), primary_key=True),  # AAAA-MM-DD, en UTC
    Column("name", String(64), primary_key=True),
    Column("value", Float, nullable=False),
)


def make_engine(url: str) -> Engine:
    """Engine de SQLAlchemy con tiempos de espera cortos.

    Neon da cadenas "postgresql://...": se indica el driver psycopg (versión 3).
    También admite SQLite, que usan los tests.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
        connect_args = {"connect_timeout": CONNECT_TIMEOUT_SECONDS}
    else:
        connect_args = {}
    # pool_pre_ping: comprueba la conexión antes de usarla, porque Neon cierra las
    # conexiones cuando se duerme.
    return create_engine(
        url, connect_args=connect_args, pool_pre_ping=True, pool_size=1, max_overflow=1
    )


class StatsStore:
    """Suma contadores en la base de datos y los lee."""

    def __init__(self, url: str) -> None:
        self.engine = make_engine(url)
        self.table_ready = False

    def _limit_time(self, connection: Connection) -> None:
        """Tiempo máximo de las consultas de esta transacción. Se pone así, y no al
        conectar, porque el pooler de Neon no admite ese parámetro al conectar."""
        if self.engine.dialect.name == "postgresql":
            connection.execute(text(f"SET LOCAL statement_timeout = {STATEMENT_TIMEOUT_MS}"))

    def _ensure_table(self) -> None:
        if not self.table_ready:
            metadata.create_all(self.engine)
            self.table_ready = True

    def add(self, deltas: dict[tuple[str, str], float]) -> None:
        """Suma los valores a los que ya hay, en una sola transacción.

        `deltas` asocia (día, nombre) con lo que hay que sumar. Si falla, no se
        guarda nada y se puede repetir más tarde con los mismos valores.
        """
        if not deltas:
            return
        self._ensure_table()
        rows = [{"day": day, "name": name, "value": value} for (day, name), value in deltas.items()]
        dialect = postgresql if self.engine.dialect.name == "postgresql" else sqlite
        insert = dialect.insert(stats_table).values(rows)
        # Si la fila ya existe, se suma el valor nuevo al guardado.
        upsert = insert.on_conflict_do_update(
            index_elements=["day", "name"],
            set_={"value": stats_table.c.value + insert.excluded.value},
        )
        with self.engine.begin() as connection:
            self._limit_time(connection)
            connection.execute(upsert)

    def load(self) -> dict[str, dict[str, float]]:
        """Todos los valores guardados, por día."""
        self._ensure_table()
        days: dict[str, dict[str, float]] = {}
        with self.engine.begin() as connection:
            self._limit_time(connection)
            for day, name, value in connection.execute(select(stats_table)):
                days.setdefault(day, {})[name] = value
        return days

    def close(self) -> None:
        self.engine.dispose()
