"""Respuestas falsas de los proveedores de IA, en el formato de streaming.

Los proveedores envían líneas "data: {json}" con cada trozo de texto y "data: [DONE]"
al final. Aquí se construyen esas respuestas sin llamar a ninguna API.
"""
import json
from contextlib import contextmanager

import httpx


def stream_response(*chunks, status_code=200, done=True):
    """Respuesta que envía `chunks` como trozos de texto (cada uno, un dict delta)."""
    lines = [
        "data: " + json.dumps({"choices": [{"delta": {"content": chunk}}]})
        for chunk in chunks
    ]
    if done:
        lines.append("data: [DONE]")
    return httpx.Response(
        status_code,
        content="\n\n".join(lines).encode(),
        request=httpx.Request("POST", "https://x.test"),
    )


def ok(text):
    """Respuesta correcta, enviada en dos trozos para probar que se unen bien."""
    middle = len(text) // 2
    return stream_response(text[:middle], text[middle:])


def failure(status_code=500):
    return httpx.Response(status_code, request=httpx.Request("POST", "https://x.test"))


def provider_name(url, model):
    """Nombre del proveedor de llm.PROVIDERS al que va la petición."""
    from app import llm

    for provider in llm.PROVIDERS:
        if provider.url == url and provider.model == model:
            return provider.name
    return "groq" if "groq" in url else "gemini"


def use_fake_stream(monkeypatch, answer_for):
    """Sustituye httpx.stream. `answer_for(name)` da la respuesta de cada proveedor
    (una httpx.Response o una excepción). Devuelve la lista de llamadas."""
    calls = []

    @contextmanager
    def fake_stream(method, url, **kwargs):
        name = provider_name(url, kwargs["json"]["model"])
        calls.append({
            "provider": name,
            "url": url,
            "prompt": kwargs["json"]["messages"][0]["content"],
            **kwargs,
        })
        result = answer_for(name)
        if isinstance(result, Exception):
            raise result
        yield result

    monkeypatch.setattr(httpx, "stream", fake_stream)
    return calls
