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
import queue
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
    # Tiempo máximo hasta el primer texto. Si no llega, se pasa al siguiente proveedor
    # sin esperar más (ver ask_providers). Es distinto de timeout_seconds, que es la
    # espera máxima entre un trozo y el siguiente una vez que ya está respondiendo.
    first_text_seconds: float = 4.0
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
        finished = False  # el proveedor ha enviado el motivo de fin ("stop"...)
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
                    chunk = json.loads(data)
                    text = chunk_text(chunk)
                    finished = finished or has_finish_reason(chunk)
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
        if not finished:
            # El flujo se cerró sin avisar de que la respuesta había terminado: puede
            # estar cortada a mitad de frase. Se trata como un fallo y entra el siguiente.
            raise ProviderError("respuesta incompleta")


def has_finish_reason(chunk: dict) -> bool:
    """Si el trozo trae el motivo de fin de la respuesta ("stop", "length"...)."""
    return any(choice.get("finish_reason") for choice in chunk.get("choices") or [])


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
        # Con el primer texto en menos de 4 s (lo normal es 1-2 s), se queda; si no,
        # pasa al siguiente. Una vez respondiendo, tolera 10 s entre trozos.
        timeout_seconds=10,
        first_text_seconds=4,
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
        first_text_seconds=2,
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
        first_text_seconds=3,
    ),
]

# Presupuesto para que el chat empiece a contestar: desde que llega la pregunta hasta
# el primer texto, en el peor caso, unos 8 s (Gemini 3.5 hasta 4 s, la reserva de Gemini
# hasta 2 s y Groq con el resto). Cada proveedor tiene además su propio límite
# (Provider.first_text_seconds), y al último siempre le quedan al menos
# LAST_RESORT_MIN_SECONDS.
FIRST_TEXT_BUDGET_SECONDS = 8.0
LAST_RESORT_MIN_SECONDS = 1.5
# Tope absoluto: si todos los proveedores han fallado, se espera como mucho hasta aquí
# a que conteste alguno de los que se abandonaron por lentos (ver ask_providers).
HARD_CAP_SECONDS = 10.0

# Cortacircuitos: si un proveedor falla (error, 429, timeout...) varias veces seguidas,
# se salta durante un rato: así no se paga su espera en cada pregunta mientras está mal.
# Es memoria de cada instancia (en Vercel, cada una tiene la suya): lo que protege en
# cualquier caso son los límites de tiempo por proveedor de arriba.
FAILURES_BEFORE_SKIPPING = 2
SKIP_SECONDS = 3 * 60


class ProviderHealth:
    """Cuenta los fallos seguidos de cada proveedor y dice si hay que saltarlo.

    Pasados SKIP_SECONDS se vuelve a probar con una sola pregunta: si responde, se
    olvidan los fallos; si falla otra vez, se salta de nuevo al momento.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self.clock = clock
        self.lock = threading.Lock()
        self.failures: dict[str, int] = {}
        self.skip_until: dict[str, float] = {}

    def should_skip(self, name: str) -> bool:
        with self.lock:
            return self.clock() < self.skip_until.get(name, 0.0)

    def record(self, name: str, error: str | None) -> None:
        """Apunta el resultado de un intento (error None: ha respondido)."""
        with self.lock:
            if error is None:
                self.failures.pop(name, None)
                self.skip_until.pop(name, None)
                return
            self.failures[name] = self.failures.get(name, 0) + 1
            if self.failures[name] >= FAILURES_BEFORE_SKIPPING:
                self.skip_until[name] = self.clock() + SKIP_SECONDS
                logger.warning(
                    "El proveedor %s se salta %d s por fallos seguidos (%s)", name, SKIP_SECONDS, error
                )

    def reset(self) -> None:
        with self.lock:
            self.failures.clear()
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


class FirstTextTimeout(ProviderError):
    """El proveedor no ha dado el primer texto a tiempo (puede darlo más tarde)."""


class Run:
    """Una petición a un proveedor, en un hilo, para poder dejar de esperarla sin
    quedarse bloqueado. Si se abandona, el hilo termina solo cuando el proveedor
    conteste o agote su espera (o en cuanto se cancele, en el siguiente trozo)."""

    def __init__(self, provider: Provider, system_prompt: str, conversation: list[dict[str, str]]) -> None:
        self.provider = provider
        self.started_at = time.perf_counter()
        self.items: queue.Queue = queue.Queue()
        self.cancelled = threading.Event()
        self.got_text = False
        threading.Thread(
            target=self._work, args=(system_prompt, conversation), name=f"llm-{provider.name}", daemon=True
        ).start()

    def _work(self, system_prompt: str, conversation: list[dict[str, str]]) -> None:
        try:
            for text in self.provider.stream(system_prompt, conversation):
                if self.cancelled.is_set():
                    return
                self.items.put(("text", text))
            self.items.put(("end", None))
        except BaseException as error:  # se reenvía a quien espera
            self.items.put(("error", error))

    def cancel(self) -> None:
        self.cancelled.set()

    def texts(self, first_text_seconds: float) -> Iterator[str]:
        """Los trozos de la respuesta. Si el primero no llega en `first_text_seconds`,
        lanza FirstTextTimeout (la petición sigue viva y se puede volver a esperar)."""
        deadline = time.monotonic() + first_text_seconds
        while True:
            # Antes del primer texto manda el límite; después, la espera entre trozos
            # (que ya aplica httpx dentro del hilo; este margen es una red de seguridad).
            wait = self.provider.timeout_seconds + 5 if self.got_text else max(deadline - time.monotonic(), 0.0)
            try:
                kind, value = self.items.get(timeout=wait)
            except queue.Empty:
                if self.got_text:
                    raise ProviderError("ReadTimeout (a mitad de respuesta)") from None
                raise FirstTextTimeout(f"ReadTimeout (sin texto en {first_text_seconds:.1f} s)") from None
            if kind == "text":
                self.got_text = True
                yield value
            elif kind == "error":
                raise value
            else:
                return


def ask_providers(
    system_prompt: str | Callable[[Provider], str],
    conversation: list[dict[str, str]],
    attempts: list[Attempt] | None = None,
    started: float | None = None,
) -> Iterator[str | object]:
    """Prueba los proveedores en orden y devuelve a trozos la respuesta del primero
    que responde. Si ninguno responde, no devuelve ningún texto.

    `system_prompt` puede ser el mismo texto para todos o una función que prepara
    las instrucciones de cada proveedor (por ejemplo, según su límite de tokens).
    Si un proveedor falla, se pasa al siguiente al momento, sin reintentos: también
    con un 429 (límite superado) o un 413 (petición demasiado grande).
    Un proveedor que falla varias veces seguidas se salta un rato (ver ProviderHealth),
    salvo que todos los siguientes también se estén saltando.

    Tiempos: cada proveedor tiene un límite hasta el primer texto (Provider.first_text_seconds,
    dentro de FIRST_TEXT_BUDGET_SECONDS desde que llegó la pregunta); si no llega, se pasa al
    siguiente sin cancelar al lento. Si al final todos han fallado, se da una última
    oportunidad a los lentos hasta HARD_CAP_SECONDS: mejor una respuesta tardía que ninguna.
    `started` es el momento (time.perf_counter()) en que llegó la pregunta; sin él, se
    cuenta desde ahora. En `attempts` se apunta cada intento con su resultado y su duración.
    """
    started = time.perf_counter() if started is None else started
    runs: list[Run] = []
    slow: list[Run] = []  # abandonados por no dar el primer texto a tiempo
    try:
        for index, provider in enumerate(PROVIDERS):
            later = PROVIDERS[index + 1:]
            if provider_health.should_skip(provider.name) and any(
                not provider_health.should_skip(other.name) for other in later
            ):
                if attempts is not None:
                    attempts.append(Attempt(provider.name, 0.0, None, SKIPPED))
                continue

            prompt = system_prompt(provider) if callable(system_prompt) else system_prompt
            run = Run(provider, prompt, conversation)
            runs.append(run)
            allowed = min(provider.first_text_seconds, FIRST_TEXT_BUDGET_SECONDS - (run.started_at - started))
            if not later:  # el último recurso siempre tiene un mínimo de tiempo
                allowed = max(allowed, LAST_RESORT_MIN_SECONDS)
            first_text = None
            try:
                for text in run.texts(max(allowed, 0.1)):
                    if first_text is None:
                        first_text = time.perf_counter() - run.started_at
                    yield text
            except ProviderError as error:
                logger.warning("El proveedor %s ha fallado: %s", provider.name, error)
                provider_health.record(provider.name, str(error))
                if isinstance(error, FirstTextTimeout):
                    slow.append(run)  # sigue esperando su respuesta por si hace falta
                if attempts is not None:
                    attempts.append(
                        Attempt(provider.name, time.perf_counter() - run.started_at, first_text, str(error))
                    )
                if first_text is not None:
                    yield RESTART
                continue
            provider_health.record(provider.name, None)
            if attempts is not None:
                attempts.append(Attempt(provider.name, time.perf_counter() - run.started_at, first_text))
            return

        # Nadie ha respondido a tiempo: se espera a los lentos hasta el tope.
        for run in slow:
            left = HARD_CAP_SECONDS - (time.perf_counter() - started)
            if left <= 0:
                break
            first_text = None
            try:
                for text in run.texts(left):
                    if first_text is None:
                        first_text = time.perf_counter() - run.started_at
                        logger.info("Responde tarde %s (a los %.1f s)", run.provider.name, first_text)
                    yield text
            except ProviderError as error:
                provider_health.record(run.provider.name, str(error))
                if first_text is not None:
                    yield RESTART
                continue
            provider_health.record(run.provider.name, None)
            if attempts is not None:
                attempts.append(Attempt(run.provider.name, time.perf_counter() - run.started_at, first_text))
            return
    finally:
        for run in runs:
            run.cancel()
