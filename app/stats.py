"""Estadísticas de uso del chat, para decidir si hay que cambiar los límites.

Solo se guardan contadores y tiempos, agrupados por día (UTC). Nunca se guarda
la pregunta, la respuesta, la IP ni ningún dato de quien escribe.

Si STATS_DATABASE_URL está definida, se guardan también en PostgreSQL (Neon, ver
app/stats_store.py) para que no se pierdan al reiniciar. El chat solo apunta en
memoria; un hilo aparte las envía cada pocos segundos. Si la base de datos falla,
se siguen guardando en memoria y se envían cuando vuelva.
"""
import logging
import threading
from collections import Counter
from collections.abc import Callable
from datetime import datetime, timezone

from app.llm import PROVIDERS
from app.stats_store import StatsStore

logger = logging.getLogger("uvicorn.error")

# Días que se conservan en memoria; los más antiguos se borran.
DAYS_KEPT = 90
# Cada cuántos segundos se envía lo pendiente a la base de datos.
FLUSH_SECONDS = 5

# Nombre de cada contador y cómo se muestra en la página de estadísticas. Los de
# cada proveedor salen de la lista PROVIDERS, así que se ajustan si cambia.
COUNTERS = {
    "messages": "Mensajes respondidos",
    "blocked_per_minute": "Bloqueados por el límite por minuto (por IP)",
    "blocked_per_day": "Bloqueados por el límite diario (por IP)",
    "blocked_total": "Bloqueados por el tope global",
    **{f"answered_{p.name}": f"Respondidos por {p.label}" for p in PROVIDERS},
    "unanswered": "Sin respuesta de ningún proveedor (mensaje con el correo)",
    "rag": "Con búsqueda RAG",
    "plan_b": "Con plan B (toda la información)",
    "plan_b_no_information": "Plan B porque el RAG no tenía el dato",
    "keywords": "Con búsqueda por palabras clave (Groq)",
    "restarts": "Respuestas reiniciadas a mitad",
    **{f"errors_{p.name}": f"Errores de {p.label}" for p in PROVIDERS},
    "errors_429": "Errores por límite del proveedor (429)",
    "errors_timeout": "Errores por tiempo de espera agotado",
    **{f"skipped_{p.name}": f"Veces que se saltó {p.label} por timeouts seguidos" for p in PROVIDERS},
    "internal_errors": "Errores internos del servidor",
}

# Tiempos de los que se calcula la media.
TIMINGS = {
    "total": "Tiempo medio total",
    "first_text": "Tiempo medio hasta el primer texto",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def timing_names(name: str) -> tuple[str, str]:
    """Cada tiempo se guarda como suma de segundos y número de medidas."""
    return f"time_{name}_seconds", f"time_{name}_count"


class ChatStats:
    """Contadores por día. Sin base de datos, solo en memoria; con ella (ver
    connect), se guardan además en PostgreSQL cada pocos segundos, en un hilo
    aparte, para que el chat nunca espere a la base de datos."""

    def __init__(self, clock: Callable[[], datetime] = utc_now) -> None:
        self.clock = clock
        self.lock = threading.Lock()
        self.started_at = clock()
        # Datos desde el arranque, en memoria: {día: {nombre: valor}}.
        self.memory: dict[str, Counter] = {}
        # Lo que falta por guardar en la base de datos: {(día, nombre): valor}.
        self.pending: Counter = Counter()
        self.store: StatsStore | None = None
        self.connected: bool | None = None  # None: aún no se ha probado
        self.flusher: threading.Thread | None = None
        self.stopping = threading.Event()

    # --- Registrar (lo usa el chat: solo toca la memoria, nunca espera) ---

    def _add(self, name: str, value: float) -> None:
        day = self.clock().date().isoformat()
        with self.lock:
            if day not in self.memory:
                self.memory[day] = Counter()
                for old_day in sorted(self.memory)[:-DAYS_KEPT]:
                    del self.memory[old_day]
            self.memory[day][name] += value
            if self.store is not None:
                self.pending[(day, name)] += value

    def count(self, name: str, amount: int = 1) -> None:
        if name not in COUNTERS:
            raise KeyError(name)
        self._add(name, amount)

    def add_time(self, name: str, seconds: float) -> None:
        if name not in TIMINGS:
            raise KeyError(name)
        seconds_name, count_name = timing_names(name)
        self._add(seconds_name, seconds)
        self._add(count_name, 1)

    # --- Base de datos ---

    def connect(self, url: str | None, flush_seconds: float = FLUSH_SECONDS) -> None:
        """Guarda las estadísticas en esa base de datos y empieza a enviarlas."""
        if not url:
            logger.info("Estadísticas solo en memoria: STATS_DATABASE_URL no está definida")
            return
        try:
            self.store = StatsStore(url)
        except Exception as error:  # cadena mal escrita: se sigue solo en memoria
            logger.warning("Estadísticas solo en memoria: STATS_DATABASE_URL no es válida (%s)",
                           type(error).__name__)
            return
        self.stopping.clear()
        self.flusher = threading.Thread(
            target=self._flush_loop, args=(flush_seconds,), name="stats-flush", daemon=True
        )
        self.flusher.start()

    def _flush_loop(self, flush_seconds: float) -> None:
        while not self.stopping.wait(flush_seconds):
            self.flush()

    def flush(self) -> bool:
        """Envía a la base de datos lo pendiente. Devuelve si ha ido bien.

        Si falla, lo pendiente se conserva y se vuelve a intentar en el siguiente
        envío: no se pierde nada mientras el servicio siga en marcha.
        """
        if self.store is None:
            return False
        with self.lock:
            batch = dict(self.pending)
        if not batch:
            return True
        try:
            self.store.add(batch)
        except Exception as error:  # cualquier fallo de red o de la base de datos
            self._set_connected(False, error)
            return False
        with self.lock:
            self.pending.subtract(batch)
            self.pending = Counter({key: value for key, value in self.pending.items() if value})
        self._set_connected(True)
        return True

    def _set_connected(self, connected: bool, error: Exception | None = None) -> None:
        # Solo se registra el cambio de estado, y el error solo por su tipo: así
        # nunca aparece la cadena de conexión en los logs.
        if connected != self.connected:
            if connected:
                logger.info("Estadísticas: conectado con la base de datos")
            else:
                logger.warning(
                    "Estadísticas: sin conexión con la base de datos (%s); se guardan "
                    "en memoria", type(error).__name__,
                )
        self.connected = connected

    def close(self) -> None:
        """Al apagar: para el hilo y envía lo que quede pendiente."""
        if self.store is None:
            return
        self.stopping.set()
        if self.flusher is not None:
            self.flusher.join(timeout=FLUSH_SECONDS + 1)
        self.flush()
        self.store.close()
        self.store = None

    # --- Leer (lo usa la página de estadísticas) ---

    def snapshot(self) -> dict:
        """Datos por día (del más reciente al más antiguo) y en total.

        Con base de datos: lo guardado más lo pendiente. Si la base de datos no
        responde, los datos en memoria desde el arranque.
        """
        days = None
        if self.store is not None:
            try:
                days = self.store.load()
            except Exception as error:
                self._set_connected(False, error)
            else:
                self._set_connected(True)
                with self.lock:
                    for (day, name), value in self.pending.items():
                        values = days.setdefault(day, {})
                        values[name] = values.get(name, 0) + value
        if days is None:
            source = "memory"
            with self.lock:
                days = {day: dict(values) for day, values in self.memory.items()}
                since = self.started_at.strftime("%d/%m/%Y %H:%M UTC")
        else:
            source = "database"
            since = min(days) if days else self.clock().date().isoformat()
        total: Counter = Counter()
        for values in days.values():
            total.update(values)
        return {
            "source": source,
            "database_configured": self.store is not None,
            "since": since,
            "days": {day: summary(days[day]) for day in sorted(days, reverse=True)},
            "total": summary(total),
        }

    def reset(self) -> None:
        with self.lock:
            self.started_at = self.clock()
            self.memory.clear()
            self.pending.clear()


def summary(values: dict[str, float]) -> dict:
    """Todos los contadores (también los que están a 0) y la media de cada tiempo."""
    result = {name: int(values.get(name, 0)) for name in COUNTERS}
    for name in TIMINGS:
        seconds_name, count_name = timing_names(name)
        measures = values.get(count_name, 0)
        seconds = values.get(seconds_name, 0)
        result[f"average_{name}"] = round(seconds / measures, 2) if measures else None
    return result


chat_stats = ChatStats()
