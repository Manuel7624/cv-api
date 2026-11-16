"""Proveedores de IA del chatbot.

Gemini y Groq aceptan el mismo formato de petición (el de OpenAI), así que una
sola clase sirve para los dos. Para cambiar de proveedor o de modelo basta con
editar la lista PROVIDERS: se prueban en orden hasta que uno responde.
Las respuestas llegan a trozos (streaming), para mostrarlas según se generan.

Las claves se leen de variables de entorno y solo se usan aquí, en el backend.
"""
import json
import logging
import os
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger("uvicorn.error")

REQUEST_TIMEOUT_SECONDS = 15
MAX_ANSWER_TOKENS = 400


class ProviderError(Exception):
    """Un proveedor no ha dado una respuesta válida."""


@dataclass(frozen=True)
class Provider:
    name: str
    url: str
    api_key_env: str
    model: str
    extra_params: dict = field(default_factory=dict)
    timeout_seconds: float = REQUEST_TIMEOUT_SECONDS
    # Tokens máximos por petición (instrucciones + conversación + respuesta).
    # None: sin un límite que nos afecte, admite toda la información.
    max_request_tokens: int | None = None
    # Nombre para mostrar en la página de estadísticas.
    label: str = ""

    def stream(self, system_prompt: str, conversation: list[dict[str, str]]) -> Iterator[str]:
        """Envía la conversación al proveedor y devuelve su respuesta a trozos, según
        la va generando (streaming).

        `conversation` son los mensajes anteriores más la pregunta nueva, al final.
        El proveedor envía líneas "data: {json}" con cada trozo y "data: [DONE]" al final.
        Si falla, lanza ProviderError, también después de haber enviado algún trozo.
        """
        api_key = os.getenv(self.api_key_env)
        if not api_key:
            raise ProviderError("falta la clave")

        sent_text = False
        try:
            with httpx.stream(
                "POST",
                self.url,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": self.model,
                    "messages": [{"role": "system", "content": system_prompt}, *conversation],
                    "max_tokens": MAX_ANSWER_TOKENS,
                    "temperature": 0.2,
                    "stream": True,
                    **self.extra_params,
                },
                # Tiempo máximo para conectar y entre un trozo y el siguiente.
                timeout=self.timeout_seconds,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line.removeprefix("data:").strip()
                    if data == "[DONE]":
                        break
                    text = chunk_text(json.loads(data))
                    if not sent_text:
                        text = text.lstrip()
                    if text:
                        sent_text = True
                        yield text
        except httpx.HTTPStatusError as error:
            raise ProviderError(f"respuesta {error.response.status_code}") from None
        except httpx.HTTPError as error:
            raise ProviderError(type(error).__name__) from None
        except (KeyError, IndexError, TypeError, ValueError):
            raise ProviderError("respuesta con formato inesperado") from None

        if not sent_text:
            raise ProviderError("respuesta vacía")


def chunk_text(chunk: dict) -> str:
    """Texto de un trozo de la respuesta (puede no traer texto, por ejemplo el último)."""
    if "error" in chunk:
        raise ValueError("el proveedor ha enviado un error")
    if not chunk["choices"]:
        return ""
    text = chunk["choices"][0]["delta"].get("content") or ""
    if not isinstance(text, str):
        raise TypeError("texto con formato inesperado")
    return text


GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

PROVIDERS = [
    Provider(
        name="gemini",
        label="Gemini 3.5 Flash-Lite",
        url=GEMINI_URL,
        api_key_env="GEMINI_API_KEY",
        model="gemini-3.5-flash-lite",
        extra_params={"reasoning_effort": "minimal"},
        # Si tarda más de 10 segundos, es mejor pasar al siguiente proveedor.
        timeout_seconds=10,
    ),
    # Reserva de Gemini: otra versión, estable, con la misma clave y el mismo cupo
    # gratuito. Si el modelo principal va lento o se cae, responde con la misma
    # información (sin el límite de tokens de Groq).
    Provider(
        name="gemini_backup",
        label="Gemini 3.1 Flash-Lite (reserva)",
        url=GEMINI_URL,
        api_key_env="GEMINI_API_KEY",
        model="gemini-3.1-flash-lite",
        extra_params={"reasoning_effort": "minimal"},
        timeout_seconds=10,
    ),
    Provider(
        name="groq",
        label="Groq",
        url="https://api.groq.com/openai/v1/chat/completions",
        api_key_env="GROQ_API_KEY",
        model="openai/gpt-oss-120b",
        extra_params={"reasoning_effort": "low"},
        # El plan gratuito rechaza peticiones de más de 8.000 tokens.
        max_request_tokens=8000,
    ),
]

# Si un proveedor agota el tiempo de espera varias veces seguidas, se salta durante
# un rato: así no se esperan 10 segundos en cada pregunta mientras va lento.
TIMEOUTS_BEFORE_SKIPPING = 2
SKIP_SECONDS = 5 * 60


class ProviderHealth:
    """Cuenta los timeouts seguidos de cada proveedor y dice si hay que saltarlo.

    Pasados SKIP_SECONDS se vuelve a probar: si responde, se olvidan sus timeouts;
    si vuelve a agotar el tiempo, se salta otra vez.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self.clock = clock
        self.lock = threading.Lock()
        self.timeouts: dict[str, int] = {}
        self.skip_until: dict[str, float] = {}

    def should_skip(self, name: str) -> bool:
        with self.lock:
            return self.clock() < self.skip_until.get(name, 0.0)

    def record(self, name: str, error: str | None) -> None:
        """Apunta el resultado de un intento (error None: ha respondido)."""
        with self.lock:
            if error is None or "Timeout" not in error:
                # Otros errores (429, 500...) no hacen esperar: no cuentan.
                if error is None:
                    self.timeouts.pop(name, None)
                    self.skip_until.pop(name, None)
                return
            self.timeouts[name] = self.timeouts.get(name, 0) + 1
            if self.timeouts[name] >= TIMEOUTS_BEFORE_SKIPPING:
                self.skip_until[name] = self.clock() + SKIP_SECONDS
                logger.warning(
                    "El proveedor %s se salta %d s por timeouts seguidos", name, SKIP_SECONDS
                )

    def reset(self) -> None:
        with self.lock:
            self.timeouts.clear()
            self.skip_until.clear()


provider_health = ProviderHealth()

# Señal que envía ask_providers cuando un proveedor falla a mitad de respuesta: lo
# recibido hasta entonces se descarta y la respuesta empieza de nuevo con el siguiente.
RESTART = object()

SKIPPED = "saltado por timeouts seguidos"


@dataclass
class Attempt:
    """Un intento con un proveedor, para los logs y las estadísticas."""

    provider: str
    seconds: float
    first_text_seconds: float | None  # None si no llegó a enviar texto
    error: str | None = None  # None si respondió bien

    @property
    def skipped(self) -> bool:
        return self.error == SKIPPED

    def describe(self) -> str:
        if self.error is None:
            return f"{self.provider} ok (primer texto {self.first_text_seconds:.2f} s) {self.seconds:.2f} s"
        if self.skipped:
            return f"{self.provider} {SKIPPED}"
        return f"{self.provider} falla ({self.error}) {self.seconds:.2f} s"


def ask_providers(
    system_prompt: str | Callable[[Provider], str],
    conversation: list[dict[str, str]],
    attempts: list[Attempt] | None = None,
) -> Iterator[str | object]:
    """Prueba los proveedores en orden y devuelve a trozos la respuesta del primero
    que responde. Si ninguno responde, no devuelve ningún texto.

    `system_prompt` puede ser el mismo texto para todos o una función que prepara
    las instrucciones de cada proveedor (por ejemplo, según su límite de tokens).
    Si un proveedor falla, se pasa al siguiente al momento, sin reintentos: también
    con un 429 (límite superado) o un 413 (petición demasiado grande).
    Un proveedor con varios timeouts seguidos se salta un rato (ver ProviderHealth),
    salvo que todos los siguientes también se estén saltando.
    En `attempts` se apunta cada intento con su resultado y su duración.
    """
    for index, provider in enumerate(PROVIDERS):
        later = PROVIDERS[index + 1:]
        if provider_health.should_skip(provider.name) and any(
            not provider_health.should_skip(other.name) for other in later
        ):
            if attempts is not None:
                attempts.append(Attempt(provider.name, 0.0, None, SKIPPED))
            continue

        prompt = system_prompt(provider) if callable(system_prompt) else system_prompt
        start = time.perf_counter()
        first_text = None
        try:
            for text in provider.stream(prompt, conversation):
                if first_text is None:
                    first_text = time.perf_counter() - start
                yield text
        except ProviderError as error:
            logger.warning("El proveedor %s ha fallado: %s", provider.name, error)
            provider_health.record(provider.name, str(error))
            if attempts is not None:
                attempts.append(
                    Attempt(provider.name, time.perf_counter() - start, first_text, str(error))
                )
            if first_text is not None:
                yield RESTART
            continue
        provider_health.record(provider.name, None)
        if attempts is not None:
            attempts.append(Attempt(provider.name, time.perf_counter() - start, first_text))
        return
