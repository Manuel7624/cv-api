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
import re
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger("uvicorn.error")

REQUEST_TIMEOUT_SECONDS = 15
MAX_ANSWER_TOKENS = 400


class ProviderError(Exception):
    """Un proveedor no ha dado una respuesta válida.

    `unavailable_seconds`: si el proveedor ha agotado su cupo del día (429 por tokens por
    día), cuánto falta para que vuelva a admitir peticiones (lo que dice su respuesta).
    """

    def __init__(self, message: str = "", unavailable_seconds: float | None = None) -> None:
        super().__init__(message)
        self.unavailable_seconds = unavailable_seconds


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
                if response.status_code == 429:
                    response.read()  # para poder leer qué límite se ha superado
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
            raise ProviderError(
                f"respuesta {error.response.status_code}", daily_limit_wait(error.response)
            ) from None
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


DEFAULT_DAILY_WAIT_SECONDS = 60 * 60
MAX_DAILY_WAIT_SECONDS = 24 * 60 * 60


def daily_limit_wait(response: httpx.Response) -> float | None:
    """Si un 429 es por el límite de tokens por día, los segundos que faltan para poder
    volver a pedir (Retry-After o, si no, el "try again in 38m26.88s" del mensaje).
    Para cualquier otro 429 (por minuto...), None: esos se resuelven solos enseguida."""
    try:
        message = str(response.json()["error"]["message"])
    except (KeyError, TypeError, ValueError, httpx.ResponseNotRead):
        return None
    if "per day" not in message and "(TPD)" not in message:
        return None
    wait = None
    try:
        wait = float(response.headers["retry-after"])
    except (KeyError, ValueError):
        found = re.search(r"try again in (?:(\d+)h)?(?:(\d+)m)?(?:([\d.]+)s)?", message)
        if found and any(found.groups()):
            hours, minutes, seconds = (float(part or 0) for part in found.groups())
            wait = hours * 3600 + minutes * 60 + seconds
    return min(max(wait if wait else DEFAULT_DAILY_WAIT_SECONDS, 60.0), MAX_DAILY_WAIT_SECONDS)


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
# Mientras al usuario no se le ha mostrado texto (el chat guarda los primeros caracteres
# para comprobar que la respuesta es válida), un proveedor que deja de enviar trozos más
# de esto se abandona: no hace falta esperar los 10 s de siempre.
STALL_BEFORE_SHOWN_SECONDS = 3.5

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
        self.exhausted_until: dict[str, float] = {}

    def is_exhausted(self, name: str) -> bool:
        """Si ha agotado su cupo del día: no se le pide nada hasta la hora que indicó."""
        with self.lock:
            return self.clock() < self.exhausted_until.get(name, 0.0)

    def mark_exhausted(self, name: str, seconds: float) -> None:
        with self.lock:
            self.exhausted_until[name] = self.clock() + seconds
        logger.warning("El proveedor %s ha agotado su cupo del día: no se usa durante %d s", name, seconds)

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
            self.exhausted_until.clear()


provider_health = ProviderHealth()

# Señal que envía ask_providers cuando un proveedor falla a mitad de respuesta: lo
# recibido hasta entonces se descarta y la respuesta empieza de nuevo con el siguiente.
RESTART = object()

SKIPPED = "saltado por fallos seguidos"
EXHAUSTED = "sin cupo del día"


@dataclass
class Attempt:
    """Un intento con un proveedor, para los logs y las estadísticas."""

    provider: str
    seconds: float
    first_text_seconds: float | None  # None si no llegó a enviar texto
    error: str | None = None  # None si respondió bien

    @property
    def skipped(self) -> bool:
        return self.error in (SKIPPED, EXHAUSTED)

    def describe(self) -> str:
        if self.error is None:
            return f"{self.provider} ok (primer texto {self.first_text_seconds:.2f} s) {self.seconds:.2f} s"
        if self.skipped:
            return f"{self.provider} {self.error}"
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

    def texts(
        self, first_text_seconds: float, hold_chars: int = 0, shown_by: float | None = None
    ) -> Iterator[str]:
        """Los trozos de la respuesta.

        Si el primero no llega en `first_text_seconds`, lanza FirstTextTimeout (la petición
        sigue viva y se puede volver a esperar). `hold_chars`: caracteres que el chat guarda
        antes de enseñar nada; hasta que se llega a ellos, si el proveedor se para más de
        STALL_BEFORE_SHOWN_SECONDS (o pasa `shown_by`, un time.perf_counter()) se abandona.
        """
        first_deadline = time.perf_counter() + first_text_seconds
        chars = 0
        while True:
            now = time.perf_counter()
            if not self.got_text:
                wait = first_deadline - now
            elif chars < hold_chars:  # al usuario aún no se le ha enseñado nada
                wait = STALL_BEFORE_SHOWN_SECONDS
                if shown_by is not None:
                    wait = min(wait, shown_by - now)
            else:
                # Ya está respondiendo: manda la espera entre trozos de siempre (la aplica
                # httpx dentro del hilo; este margen es una red de seguridad).
                wait = self.provider.timeout_seconds + 5
            try:
                kind, value = self.items.get(timeout=max(wait, 0.0))
            except queue.Empty:
                if self.got_text:
                    raise ProviderError("ReadTimeout (a mitad de respuesta)") from None
                raise FirstTextTimeout(f"ReadTimeout (sin texto en {first_text_seconds:.1f} s)") from None
            if kind == "text":
                self.got_text = True
                chars += len(value)
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
    hold_chars: int = 0,
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
    cuenta desde ahora. `hold_chars`: los primeros caracteres que el chat guarda antes de
    enseñarlos: el tope de HARD_CAP_SECONDS cuenta hasta que se llega a ellos.
    Un proveedor que ha agotado su cupo del día no se usa hasta la hora que indicó.
    En `attempts` se apunta cada intento con su resultado y su duración.
    """
    started = time.perf_counter() if started is None else started
    shown_by = started + HARD_CAP_SECONDS

    def available(other: Provider) -> bool:
        return not provider_health.should_skip(other.name) and not provider_health.is_exhausted(other.name)

    runs: list[Run] = []
    slow: list[Run] = []  # abandonados por no dar el primer texto a tiempo
    try:
        for index, provider in enumerate(PROVIDERS):
            later = PROVIDERS[index + 1:]
            if provider_health.is_exhausted(provider.name):
                if attempts is not None:
                    attempts.append(Attempt(provider.name, 0.0, None, EXHAUSTED))
                continue
            # Un proveedor con fallos seguidos se salta, salvo que los que vienen detrás no
            # estén disponibles (saltados o sin cupo): entonces se prueba igualmente.
            if provider_health.should_skip(provider.name) and any(available(other) for other in later):
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
                for text in run.texts(max(allowed, 0.1), hold_chars, shown_by):
                    if first_text is None:
                        first_text = time.perf_counter() - run.started_at
                    yield text
            except ProviderError as error:
                logger.warning("El proveedor %s ha fallado: %s", provider.name, error)
                provider_health.record(provider.name, str(error))
                if error.unavailable_seconds:
                    provider_health.mark_exhausted(provider.name, error.unavailable_seconds)
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
                for text in run.texts(left, hold_chars, shown_by):
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
