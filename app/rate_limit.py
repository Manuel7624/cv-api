"""Límites de mensajes del chatbot.

Los contadores se consultan en memoria, así que comprobar un límite nunca espera a
la base de datos. Para que sobrevivan a los reinicios (en Render, el servicio se
duerme a los 15 minutos sin visitas y arranca de cero al despertar), cada mensaje
permitido se apunta también en PostgreSQL (Neon) desde el hilo de las estadísticas
(ver app/stats.py), y al arrancar se vuelven a cargar los de las últimas 24 horas.
Si la base de datos falla, los límites siguen funcionando solo en memoria.

La IP nunca se guarda en claro, ni en memoria ni en la base de datos: se guarda un
hash HMAC-SHA256 con una sal secreta (LIMITS_HASH_SALT). Sin la sal no se puede
saber qué IP es. Los usos de más de 24 horas ya no sirven para ningún límite y se
borran. Solo sirven con un único proceso, que es como se despliega esta aplicación.
"""
import hashlib
import hmac
import logging
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable, Iterable

from fastapi import Request

from app.chat_limits import (
    MESSAGES_PER_DAY_PER_IP,
    MESSAGES_PER_DAY_TOTAL,
    MESSAGES_PER_MINUTE_PER_IP,
)

logger = logging.getLogger("uvicorn.error")

SECONDS_PER_MINUTE = 60
SECONDS_PER_DAY = 24 * 60 * 60


def load_salt() -> bytes:
    """Sal del hash de las IPs. En Render la genera el propio Render (render.yaml).

    Sin ella, se usa una aleatoria hasta el siguiente reinicio: el tope global sigue
    sobreviviendo a los reinicios, pero los límites por IP empiezan de cero.
    """
    salt = os.getenv("LIMITS_HASH_SALT", "").strip()
    if salt:
        return salt.encode()
    return secrets.token_bytes(32)


class SlidingWindowLimiter:
    """Permite `limit` usos por clave en los últimos `window_seconds` segundos.

    Los tiempos son segundos de reloj real (time.time) para poder guardarlos y
    recuperarlos después de un reinicio.
    """

    def __init__(
        self,
        limit: int,
        window_seconds: int,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.clock = clock
        self.uses: dict[str, deque[float]] = defaultdict(deque)
        self.lock = threading.Lock()

    def _forget_old(self, key: str, now: float) -> deque[float]:
        uses = self.uses[key]
        while uses and now - uses[0] >= self.window_seconds:
            uses.popleft()
        if not uses:  # para que la memoria no crezca con claves que ya no sirven
            del self.uses[key]
            return deque()
        return uses

    def is_full(self, key: str, now: float) -> bool:
        with self.lock:
            return len(self._forget_old(key, now)) >= self.limit

    def record(self, key: str, when: float) -> None:
        with self.lock:
            uses = self.uses[key]
            uses.append(when)
            if len(uses) > 1 and uses[-2] > when:  # al cargar, por si llegan desordenados
                self.uses[key] = deque(sorted(uses))

    def allow(self, key: str) -> bool:
        now = self.clock()
        if self.is_full(key, now):
            return False
        self.record(key, now)
        return True

    def remaining(self, key: str) -> int:
        """Usos que le quedan a `key` en la ventana actual."""
        now = self.clock()
        with self.lock:
            recent = sum(1 for use in self.uses.get(key, ()) if now - use < self.window_seconds)
        return max(0, self.limit - recent)

    def reset(self) -> None:
        with self.lock:
            self.uses.clear()


# Motivos por los que se bloquea un mensaje (los usan también las estadísticas).
BLOCKED_PER_MINUTE = "per_minute"
BLOCKED_PER_DAY = "per_day"
BLOCKED_TOTAL = "total"
TOTAL_KEY = "all"


class ChatLimits:
    """Reúne los tres límites. Un mensaje debe pasarlos todos."""

    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        self.clock = clock
        self.salt = load_salt()
        self.per_minute = SlidingWindowLimiter(MESSAGES_PER_MINUTE_PER_IP, SECONDS_PER_MINUTE, clock)
        self.per_day = SlidingWindowLimiter(MESSAGES_PER_DAY_PER_IP, SECONDS_PER_DAY, clock)
        self.total = SlidingWindowLimiter(MESSAGES_PER_DAY_TOTAL, SECONDS_PER_DAY, clock)
        self.lock = threading.Lock()
        # Se llama con (hash de la IP, segundos) por cada mensaje permitido; las
        # estadísticas lo usan para guardarlo en la base de datos.
        self.on_use: Callable[[str, float], None] | None = None

    def ip_key(self, ip: str) -> str:
        """Hash de la IP con sal: identifica al visitante sin guardar su IP."""
        return hmac.new(self.salt, ip.encode(), hashlib.sha256).hexdigest()

    def check(self, ip: str) -> str | None:
        """Devuelve None si el mensaje está permitido (y lo cuenta), o el motivo del
        bloqueo (y no lo cuenta en ningún límite)."""
        key = self.ip_key(ip)
        with self.lock:
            now = self.clock()
            if self.per_minute.is_full(key, now):
                return BLOCKED_PER_MINUTE
            if self.per_day.is_full(key, now):
                return BLOCKED_PER_DAY
            if self.total.is_full(TOTAL_KEY, now):
                return BLOCKED_TOTAL
            self._record(key, now)
        if self.on_use is not None:
            self.on_use(key, now)
        return None

    def _record(self, key: str, when: float) -> None:
        self.per_minute.record(key, when)
        self.per_day.record(key, when)
        self.total.record(TOTAL_KEY, when)

    def restore(self, uses: Iterable[tuple[str, float]]) -> int:
        """Carga usos guardados (hash de la IP, segundos), por ejemplo al arrancar.
        Devuelve cuántos de las últimas 24 horas se han cargado."""
        now = self.clock()
        loaded = 0
        with self.lock:
            for key, when in sorted(uses, key=lambda use: use[1]):
                if now - when < SECONDS_PER_DAY:
                    self._record(key, when)
                    loaded += 1
        return loaded

    def remaining_total(self) -> int:
        """Mensajes que quedan del tope global en las últimas 24 horas."""
        return self.total.remaining(TOTAL_KEY)

    def reset(self) -> None:
        self.per_minute.reset()
        self.per_day.reset()
        self.total.reset()


chat_limits = ChatLimits()


def get_client_ip(request: Request) -> str:
    """Devuelve la IP del visitante.

    Detrás de un proxy, todas las peticiones llegan desde la IP del proxy.
    CLIENT_IP_HEADER indica qué cabecera trae la IP real. Solo debe definirse
    donde el proxy la escribe él mismo, porque si no el visitante podría
    falsificarla.
    """
    header = os.getenv("CLIENT_IP_HEADER")
    if header:
        value = request.headers.get(header)
        if value:
            return value.strip()
    return request.client.host if request.client else "unknown"
