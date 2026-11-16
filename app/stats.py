"""Estadísticas de uso del chat, para decidir si hay que cambiar los límites.

Solo se guardan contadores y tiempos, agrupados por día (UTC). Nunca se guarda
la pregunta, la respuesta, la IP ni ningún dato de quien escribe.

Viven en memoria, como los límites: se pierden si el servicio se reinicia.
"""
import threading
from collections import Counter
from collections.abc import Callable
from datetime import datetime, timezone

# Días que se conservan; los más antiguos se borran para no ocupar memoria.
DAYS_KEPT = 90

# Nombre de cada contador y cómo se muestra en la página de estadísticas.
COUNTERS = {
    "messages": "Mensajes respondidos",
    "blocked_per_minute": "Bloqueados por el límite por minuto (por IP)",
    "blocked_per_day": "Bloqueados por el límite diario (por IP)",
    "blocked_total": "Bloqueados por el tope global",
    "answered_gemini": "Respondidos por Gemini",
    "answered_groq": "Respondidos por Groq",
    "unanswered": "Sin respuesta de ningún proveedor (mensaje con el correo)",
    "rag": "Con búsqueda RAG",
    "plan_b": "Con plan B (toda la información)",
    "plan_b_no_information": "Plan B porque el RAG no tenía el dato",
    "keywords": "Con búsqueda por palabras clave (Groq)",
    "restarts": "Respuestas reiniciadas a mitad",
    "errors_gemini": "Errores de Gemini",
    "errors_groq": "Errores de Groq",
    "errors_429": "Errores por límite del proveedor (429)",
    "errors_timeout": "Errores por tiempo de espera agotado",
    "internal_errors": "Errores internos del servidor",
}

# Tiempos de los que se calcula la media.
TIMINGS = {
    "total": "Tiempo medio total",
    "first_text": "Tiempo medio hasta el primer texto",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ChatStats:
    def __init__(self, clock: Callable[[], datetime] = utc_now) -> None:
        self.clock = clock
        self.lock = threading.Lock()
        self.started_at = clock()
        self.counters: dict[str, Counter] = {}
        # Por día y tiempo: [suma de segundos, número de medidas].
        self.timings: dict[str, dict[str, list[float]]] = {}

    def _today(self) -> str:
        day = self.clock().date().isoformat()
        if day not in self.counters:
            self.counters[day] = Counter()
            self.timings[day] = {name: [0.0, 0] for name in TIMINGS}
            for old_day in sorted(self.counters)[:-DAYS_KEPT]:
                del self.counters[old_day]
                del self.timings[old_day]
        return day

    def count(self, name: str, amount: int = 1) -> None:
        if name not in COUNTERS:
            raise KeyError(name)
        with self.lock:
            self.counters[self._today()][name] += amount

    def add_time(self, name: str, seconds: float) -> None:
        if name not in TIMINGS:
            raise KeyError(name)
        with self.lock:
            timing = self.timings[self._today()][name]
            timing[0] += seconds
            timing[1] += 1

    def snapshot(self) -> dict:
        """Copia de los datos: por día (del más reciente al más antiguo) y en total."""
        with self.lock:
            days = {}
            total = Counter()
            total_timings = {name: [0.0, 0] for name in TIMINGS}
            for day in sorted(self.counters, reverse=True):
                counters = self.counters[day]
                total.update(counters)
                for name, (seconds, measures) in self.timings[day].items():
                    total_timings[name][0] += seconds
                    total_timings[name][1] += measures
                days[day] = summary(counters, self.timings[day])
            return {
                "started_at": self.started_at,
                "days": days,
                "total": summary(total, total_timings),
            }

    def reset(self) -> None:
        with self.lock:
            self.started_at = self.clock()
            self.counters.clear()
            self.timings.clear()


def summary(counters: Counter, timings: dict[str, list[float]]) -> dict:
    """Todos los contadores (también los que están a 0) y la media de cada tiempo."""
    result = {name: counters.get(name, 0) for name in COUNTERS}
    for name, (seconds, measures) in timings.items():
        result[f"average_{name}"] = round(seconds / measures, 2) if measures else None
    return result


chat_stats = ChatStats()
