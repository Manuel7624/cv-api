"""Protecciones generales de la aplicación: tamaño máximo de las peticiones y
cabeceras de seguridad.
"""
from fastapi import HTTPException, status
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Ninguna petición legítima se acerca a esto: una pregunta (500 caracteres) más el
# historial (6 mensajes de hasta 1200) ocupan menos de 16 KB.
MAX_REQUEST_BYTES = 32 * 1024

TOO_LARGE_DETAIL = "La petición es demasiado grande."

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "DENY",
    # La web no usa la cámara, el micrófono ni la ubicación: nadie podrá pedirlos.
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}
# Le dice al navegador que use siempre HTTPS durante un año. Solo vale (y solo se
# envía) en respuestas que llegan por HTTPS.
HSTS_HEADER = "max-age=31536000"


class LimitRequestSize:
    """Rechaza con 413 las peticiones de más de `max_bytes` sin leerlas enteras.

    Si traen Content-Length, se mira antes de leer nada. Si no lo traen (envío por
    trozos), se cuentan los bytes según llegan y se corta al pasar del máximo. Así
    nadie puede llenar la memoria del servidor con un cuerpo enorme.
    """

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_REQUEST_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope["headers"])
        length = headers.get(b"content-length")
        if length is not None:
            try:
                too_large = int(length) > self.max_bytes
            except ValueError:
                too_large = True  # un Content-Length que no es un número no es fiable
            if too_large:
                await reject_too_large(send)
                return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    # FastAPI la convierte en una respuesta 413 normal.
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=TOO_LARGE_DETAIL
                    )
            return message

        await self.app(scope, limited_receive, send)


async def reject_too_large(send: Send) -> None:
    body = b'{"detail":"' + TOO_LARGE_DETAIL.encode() + b'"}'
    await send({
        "type": "http.response.start",
        "status": status.HTTP_413_CONTENT_TOO_LARGE,
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
            (b"connection", b"close"),
        ],
    })
    await send({"type": "http.response.body", "body": body})


def arrived_over_https(scheme: str, forwarded_proto: str | None) -> bool:
    """Si la petición llegó por HTTPS. Detrás del proxy de Render la conexión con la
    aplicación es HTTP, y el esquema original llega en X-Forwarded-Proto."""
    if forwarded_proto:
        return forwarded_proto.split(",")[0].strip().lower() == "https"
    return scheme == "https"
