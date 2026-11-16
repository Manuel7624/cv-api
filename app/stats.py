"""Estadísticas de uso del chat y registro de preguntas.

- Contadores y tiempos, agrupados por día (UTC), para decidir si hay que cambiar
  los límites.
- Registro de preguntas: cada pregunta con su respuesta, la fecha, el proveedor y
  cómo terminó (respondida, rechazada, sin información o error), para ver qué falta
  en los datos. Se conservan QUESTION_DAYS días y después se borran solas.
- Usos de los límites del chat (ver app/rate_limit.py): solo un hash con sal de la
  IP y la hora, para que los límites sobrevivan a los reinicios. Se borran a las
  24 horas.
Nunca se guarda la IP ni ningún dato que identifique a quien escribe.

Si STATS_DATABASE_URL está definida, se guardan también en PostgreSQL (Neon, ver
app/stats_store.py) para que no se pierdan al reiniciar. El chat solo apunta en
memoria; un hilo aparte las envía cada pocos segundos. Si la base de datos falla,
se siguen guardando en memoria y se envían cuando vuelva.
"""
import logging
import threading
import time
from collections import Counter, deque
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta, timezone

from app.llm import PROVIDERS
from app.stats_store import StatsStore

logger = logging.getLogger("uvicorn.error")

# Días que se conservan en memoria; los más antiguos se borran.
DAYS_KEPT = 90
# Cada cuántos segundos se envía lo pendiente a la base de datos.
FLUSH_SECONDS = 5
# Días que se guardan las preguntas; las más antiguas se borran (como mucho, una vez
# por hora, en el mismo hilo que envía lo pendiente).
QUESTION_DAYS = 30
CLEANUP_SECONDS = 60 * 60
# Preguntas que se guardan en memoria (sin base de datos, o mientras falla).
MAX_QUESTIONS_IN_MEMORY = 1000
# Horas que cuenta un uso para los límites (el más largo es el diario).
LIMIT_USES_HOURS = 24

# Cómo terminó cada pregunta y cómo se muestra en la página privada.
QUESTION_STATUSES = {
    "answered": "Respondida",
    "rejected": "Rechazada (fuera de tema)",
    "no_information": "Sin información",
    "error": "Sin respuesta (fallaron los proveedores)",
}

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
    "plan_b_no_information": "Plan B porque el RAG no tenía el dato o rechazó la pregunta",
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
        # Preguntas: las últimas en memoria y las que faltan por guardar.
        self.recent_questions: deque[dict] = deque(maxlen=MAX_QUESTIONS_IN_MEMORY)
        self.pending_questions: deque[dict] = deque(maxlen=MAX_QUESTIONS_IN_MEMORY)
        # Usos de los límites que faltan por guardar: {"key", "used_at"}.
        self.pending_limit_uses: deque[dict] = deque(maxlen=MAX_QUESTIONS_IN_MEMORY)
        self.last_cleanup: float | None = None  # time.monotonic() del último borrado
        # Para que el hilo y la página privada no envíen lo mismo a la vez.
        self.flush_lock = threading.Lock()
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

    def log_question(self, question: str, answer: str, provider: str | None, status: str) -> None:
        """Apunta una pregunta con su respuesta (sin nada de quien la hace)."""
        if status not in QUESTION_STATUSES:
            raise KeyError(status)
        row = {
            "asked_at": self.clock(),
            "question": question,
            "answer": answer,
            "provider": provider,
            "status": status,
        }
        with self.lock:
            self.recent_questions.append(row)
            if self.store is not None:
                self.pending_questions.append(row)

    def log_limit_use(self, key: str, when: float) -> None:
        """Apunta un uso de los límites (hash de la IP, segundos) para guardarlo."""
        with self.lock:
            if self.store is not None:
                self.pending_limit_uses.append(
                    {"key": key, "used_at": datetime.fromtimestamp(when, timezone.utc)}
                )

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
        with self.flush_lock:
            with self.lock:
                batch = dict(self.pending)
                questions = list(self.pending_questions)
                limit_uses = list(self.pending_limit_uses)
            cleanup = (
                self.last_cleanup is None
                or time.monotonic() - self.last_cleanup >= CLEANUP_SECONDS
            )
            if not batch and not questions and not limit_uses and not cleanup:
                return True
            try:
                self.store.add(
                    batch,
                    questions,
                    delete_before=self.questions_since() if cleanup else None,
                    limit_uses=limit_uses,
                    # Los usos que ya no cuentan se borran cada vez que se guardan
                    # otros nuevos (y en la limpieza de cada hora).
                    delete_limit_uses_before=(
                        self.limit_uses_since() if cleanup or limit_uses else None
                    ),
                )
            except Exception as error:  # cualquier fallo de red o de la base de datos
                self._set_connected(False, error)
                return False
            with self.lock:
                self.pending.subtract(batch)
                self.pending = Counter({key: value for key, value in self.pending.items() if value})
                # Las guardadas son las primeras; detrás puede haber otras nuevas.
                for _ in questions:
                    self.pending_questions.popleft()
                for _ in limit_uses:
                    self.pending_limit_uses.popleft()
            if cleanup:
                self.last_cleanup = time.monotonic()
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

    def limit_uses_since(self) -> datetime:
        """Fecha a partir de la cual un uso todavía cuenta para algún límite."""
        return self.clock() - timedelta(hours=LIMIT_USES_HOURS)

    def load_limit_uses(self) -> list[tuple[str, float]]:
        """Usos de los límites guardados en las últimas 24 horas, como (clave,
        segundos). Se usa al arrancar; si la base de datos falla, ninguno."""
        if self.store is None:
            return []
        try:
            rows = self.store.limit_uses(self.limit_uses_since())
        except Exception as error:
            self._set_connected(False, error)
            return []
        self._set_connected(True)
        uses = []
        for key, used_at in rows:
            if used_at.tzinfo is None:  # SQLite devuelve las fechas sin zona horaria
                used_at = used_at.replace(tzinfo=timezone.utc)
            uses.append((key, used_at.timestamp()))
        return uses

    def questions_since(self) -> datetime:
        """Fecha a partir de la cual se conservan las preguntas."""
        return self.clock() - timedelta(days=QUESTION_DAYS)

    def questions(
        self, statuses: Iterable[str] | None = None, page: int = 1, per_page: int = 50
    ) -> dict:
        """Una página de preguntas, de la más reciente a la más antigua.

        Con base de datos, primero se envía lo pendiente para que salga todo. Si la
        base de datos no responde, las que hay en memoria desde el arranque.
        """
        since = self.questions_since()
        offset = (page - 1) * per_page
        statuses = None if statuses is None else set(statuses)
        if self.store is not None:
            self.flush()
            try:
                rows, total = self.store.questions(since, statuses, per_page, offset)
            except Exception as error:
                self._set_connected(False, error)
            else:
                self._set_connected(True)
                for row in rows:  # SQLite devuelve las fechas sin zona horaria
                    if row["asked_at"].tzinfo is None:
                        row["asked_at"] = row["asked_at"].replace(tzinfo=timezone.utc)
                return {"source": "database", "rows": rows, "total": total}
        with self.lock:
            matching = [
                row for row in reversed(self.recent_questions)
                if row["asked_at"] >= since and (statuses is None or row["status"] in statuses)
            ]
        return {
            "source": "memory",
            "rows": matching[offset:offset + per_page],
            "total": len(matching),
        }

    def reset(self) -> None:
        with self.lock:
            self.started_at = self.clock()
            self.memory.clear()
            self.pending.clear()
            self.recent_questions.clear()
            self.pending_questions.clear()
            self.pending_limit_uses.clear()
            self.last_cleanup = None


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
