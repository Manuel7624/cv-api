"""Límites de mensajes del chatbot.

Los contadores viven en memoria: se pierden al reiniciar el servicio y solo
sirven con un único proceso, que es como se despliega esta aplicación.
"""
import os
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import Request

SECONDS_PER_MINUTE = 60
SECONDS_PER_DAY = 24 * 60 * 60

MESSAGES_PER_MINUTE_PER_IP = 5
MESSAGES_PER_DAY_PER_IP = 30
# Tope global: protege el cupo de los proveedores aunque lleguen muchas IP.
MESSAGES_PER_DAY_TOTAL = 300


class SlidingWindowLimiter:
    """Permite `limit` usos por clave en los últimos `window_seconds` segundos."""

    def __init__(
        self,
        limit: int,
        window_seconds: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.clock = clock
        self.uses: dict[str, deque[float]] = defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = self.clock()
        with self.lock:
            uses = self.uses[key]
            while uses and now - uses[0] >= self.window_seconds:
                uses.popleft()
            if len(uses) >= self.limit:
                return False
            uses.append(now)
            return True

    def reset(self) -> None:
        with self.lock:
            self.uses.clear()


class ChatLimits:
    """Reúne los tres límites. Un mensaje debe pasarlos todos."""

    def __init__(self) -> None:
        self.per_minute = SlidingWindowLimiter(MESSAGES_PER_MINUTE_PER_IP, SECONDS_PER_MINUTE)
        self.per_day = SlidingWindowLimiter(MESSAGES_PER_DAY_PER_IP, SECONDS_PER_DAY)
        self.total = SlidingWindowLimiter(MESSAGES_PER_DAY_TOTAL, SECONDS_PER_DAY)

    def allow(self, ip: str) -> bool:
        return self.per_minute.allow(ip) and self.per_day.allow(ip) and self.total.allow("all")

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
