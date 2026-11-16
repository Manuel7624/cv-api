"""Página privada de estadísticas del chat: GET /admin/stats.

Está protegida con un token que se define en la variable de entorno ADMIN_TOKEN.
El navegador lo pide con su ventana de usuario y contraseña (HTTP Basic): el
usuario da igual y la contraseña es el token. Así el token no va en la URL ni
queda en los logs. Solo debe usarse con HTTPS (en Render lo es siempre).

Si ADMIN_TOKEN no está definido o es demasiado corto, la página no existe (404).
No aparece en /docs.
"""
import logging
import os
import secrets
from html import escape
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.chat_limits import (
    MAX_MESSAGE_LENGTH,
    MESSAGES_PER_DAY_PER_IP,
    MESSAGES_PER_DAY_TOTAL,
    MESSAGES_PER_MINUTE_PER_IP,
)
from app.rate_limit import chat_limits
from app.stats import COUNTERS, TIMINGS, chat_stats

logger = logging.getLogger("uvicorn.error")

# Un token corto se podría adivinar probando: se exige una longitud mínima.
MIN_TOKEN_LENGTH = 20

router = APIRouter(include_in_schema=False)
basic_auth = HTTPBasic(auto_error=False, realm="Estadisticas")


def require_admin(
    credentials: Annotated[HTTPBasicCredentials | None, Depends(basic_auth)],
) -> None:
    token = os.getenv("ADMIN_TOKEN", "")
    if len(token) < MIN_TOKEN_LENGTH:
        if token:
            logger.warning("ADMIN_TOKEN es demasiado corto: la página de estadísticas está desactivada")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    # compare_digest tarda lo mismo acierte o no: no da pistas sobre el token.
    if credentials is None or not secrets.compare_digest(
        credentials.password.encode(), token.encode()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": 'Basic realm="Estadisticas"'},
        )


def format_value(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.2f} s".replace(".", ",")
    return str(value)


def stats_table(snapshot: dict) -> str:
    """Tabla con una fila por estadística y una columna para el total y cada día."""
    columns = [("Total", snapshot["total"])] + list(snapshot["days"].items())
    labels = dict(COUNTERS)
    labels.update({f"average_{name}": label for name, label in TIMINGS.items()})
    header = "".join(f"<th scope='col'>{escape(name)}</th>" for name, _ in columns)
    rows = []
    for key, label in labels.items():
        cells = "".join(f"<td>{escape(format_value(data[key]))}</td>" for _, data in columns)
        rows.append(f"<tr><th scope='row'>{escape(label)}</th>{cells}</tr>")
    return (
        "<div class='table'><table>"
        f"<thead><tr><th scope='col'>Estadística</th>{header}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


@router.get("/admin/stats", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
def admin_stats() -> HTMLResponse:
    snapshot = chat_stats.snapshot()
    started = snapshot["started_at"].strftime("%d/%m/%Y %H:%M UTC")
    limits = [
        ("Mensajes que quedan del tope global (últimas 24 h)",
         f"{chat_limits.remaining_total()} de {MESSAGES_PER_DAY_TOTAL}"),
        ("Límite por IP y minuto", MESSAGES_PER_MINUTE_PER_IP),
        ("Límite por IP y día", MESSAGES_PER_DAY_PER_IP),
        ("Longitud máxima de la pregunta", f"{MAX_MESSAGE_LENGTH} caracteres"),
        ("Datos desde", started),
    ]
    limit_rows = "".join(
        f"<tr><th scope='row'>{escape(label)}</th><td>{escape(str(value))}</td></tr>"
        for label, value in limits
    )
    page = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex, nofollow">
  <title>Estadísticas del chat</title>
  <link rel="stylesheet" href="/static/admin.css">
</head>
<body>
  <main>
    <h1>Estadísticas del chat</h1>
    <p>Sin preguntas, IPs ni datos personales. Los días van en UTC y los datos se
    pierden si el servicio se reinicia.</p>
    <h2>Límites</h2>
    <div class="table"><table><tbody>{limit_rows}</tbody></table></div>
    <h2>Uso</h2>
    {stats_table(snapshot)}
  </main>
</body>
</html>"""
    return HTMLResponse(
        page,
        headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"},
    )
