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


PROVIDERS = [
    Provider(
        name="gemini",
        url="https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        api_key_env="GEMINI_API_KEY",
        model="gemini-3.5-flash-lite",
        extra_params={"reasoning_effort": "minimal"},
        # Si tarda más de 10 segundos, es mejor pasar al siguiente proveedor.
        timeout_seconds=10,
    ),
    Provider(
        name="groq",
        url="https://api.groq.com/openai/v1/chat/completions",
        api_key_env="GROQ_API_KEY",
        model="openai/gpt-oss-120b",
        extra_params={"reasoning_effort": "low"},
        # El plan gratuito rechaza peticiones de más de 8.000 tokens.
        max_request_tokens=8000,
    ),
]


# Señal que envía ask_providers cuando un proveedor falla a mitad de respuesta: lo
# recibido hasta entonces se descarta y la respuesta empieza de nuevo con el siguiente.
RESTART = object()


def ask_providers(
    system_prompt: str | Callable[[Provider], str],
    conversation: list[dict[str, str]],
    steps: list[str] | None = None,
) -> Iterator[str | object]:
    """Prueba los proveedores en orden y devuelve a trozos la respuesta del primero
    que responde. Si ninguno responde, no devuelve ningún texto.

    `system_prompt` puede ser el mismo texto para todos o una función que prepara
    las instrucciones de cada proveedor (por ejemplo, según su límite de tokens).
    Si un proveedor falla, se pasa al siguiente al momento, sin reintentos: también
    con un 429 (límite superado) o un 413 (petición demasiado grande).
    En `steps` se apunta cada intento con su resultado y su duración, para los logs.
    """
    for provider in PROVIDERS:
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
            note(steps, f"{provider.name} falla ({error})", start)
            if first_text is not None:
                yield RESTART
            continue
        note(steps, f"{provider.name} ok (primer texto {first_text:.2f} s)", start)
        return


def note(steps: list[str] | None, text: str, start: float) -> None:
    """Apunta un paso con los segundos que han pasado desde `start`."""
    if steps is not None:
        steps.append(f"{text} {time.perf_counter() - start:.2f} s")
