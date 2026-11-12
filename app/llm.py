"""Proveedores de IA del chatbot.

Gemini y Groq aceptan el mismo formato de petición (el de OpenAI), así que una
sola clase sirve para los dos. Para cambiar de proveedor o de modelo basta con
editar la lista PROVIDERS: se prueban en orden hasta que uno responde.

Las claves se leen de variables de entorno y solo se usan aquí, en el backend.
"""
import logging
import os
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

    def complete(self, system_prompt: str, conversation: list[dict[str, str]]) -> str:
        """Envía la conversación al proveedor y devuelve el texto de su respuesta.

        `conversation` son los mensajes anteriores más la pregunta nueva, al final.
        """
        api_key = os.getenv(self.api_key_env)
        if not api_key:
            raise ProviderError("falta la clave")

        try:
            response = httpx.post(
                self.url,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": self.model,
                    "messages": [{"role": "system", "content": system_prompt}, *conversation],
                    "max_tokens": MAX_ANSWER_TOKENS,
                    "temperature": 0.2,
                    **self.extra_params,
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            text = response.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as error:
            raise ProviderError(f"respuesta {error.response.status_code}") from None
        except httpx.HTTPError as error:
            raise ProviderError(type(error).__name__) from None
        except (KeyError, IndexError, TypeError, ValueError):
            raise ProviderError("respuesta con formato inesperado") from None

        if not isinstance(text, str) or not text.strip():
            raise ProviderError("respuesta vacía")
        return text.strip()


PROVIDERS = [
    Provider(
        name="gemini",
        url="https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        api_key_env="GEMINI_API_KEY",
        model="gemini-3.5-flash-lite",
        extra_params={"reasoning_effort": "minimal"},
        # A veces tarda más de 10 segundos en responder.
        timeout_seconds=20,
    ),
    Provider(
        name="groq",
        url="https://api.groq.com/openai/v1/chat/completions",
        api_key_env="GROQ_API_KEY",
        model="openai/gpt-oss-120b",
        extra_params={"reasoning_effort": "low"},
    ),
]


def ask_providers(system_prompt: str, conversation: list[dict[str, str]]) -> str | None:
    """Prueba los proveedores en orden. Devuelve None si ninguno responde."""
    for provider in PROVIDERS:
        try:
            return provider.complete(system_prompt, conversation)
        except ProviderError as error:
            logger.warning("El proveedor %s ha fallado: %s", provider.name, error)
    return None
