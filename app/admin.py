"""Página privada de estadísticas del chat: GET /admin/stats.

Muestra los contadores de uso y el registro de preguntas de los últimos 30 días
(las que no se respondieron o se rechazaron, y las últimas, de 50 en 50).

Está protegida con un token que se define en la variable de entorno ADMIN_TOKEN.
El navegador lo pide con su ventana de usuario y contraseña (HTTP Basic): el
usuario da igual y la contraseña es el token. Así el token no va en la URL ni
queda en los logs. Solo debe usarse con HTTPS (en Render lo es siempre).

Si ADMIN_TOKEN no está definido o es demasiado corto, la página no existe (404).
No aparece en /docs.

Contra quien pruebe contraseñas: tras FAILED_LOGINS_BEFORE_LOCK intentos fallidos
desde la misma IP en LOCK_WINDOW_SECONDS, esa IP queda bloqueada
LOCK_WINDOW_SECONDS (429), aunque luego acierte. La IP se guarda como hash con sal
(como en los límites del chat), solo en memoria.
"""
import logging
import os
import secrets
import threading
import time
from collections import deque
from datetime import date, timedelta
from collections.abc import Callable
from html import escape
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.chat import KEYWORDS_PROVIDER
from app.chat_limits import (
    MAX_MESSAGE_LENGTH,
    MESSAGES_PER_DAY_PER_IP,
    MESSAGES_PER_DAY_TOTAL,
    MESSAGES_PER_MINUTE_PER_IP,
)
from app.rate_limit import chat_limits, get_client_ip
from app.llm import PROVIDERS
from app.static_files import HTML_CACHE, add_versions
from app.stats import COUNTERS, QUESTION_DAYS, QUESTION_STATUSES, TIMINGS, chat_stats

logger = logging.getLogger("uvicorn.error")

# Un token corto se podría adivinar probando: se exige una longitud mínima.
MIN_TOKEN_LENGTH = 20
QUESTIONS_PER_PAGE = 50
# Estados del apartado "Preguntas sin respuesta o rechazadas".
MISSING_STATUSES = ("rejected", "no_information", "error")
PROVIDER_LABELS = {
    **{provider.name: provider.label for provider in PROVIDERS},
    KEYWORDS_PROVIDER: "Groq (palabras clave)",
}

FAILED_LOGINS_BEFORE_LOCK = 10
LOCK_WINDOW_SECONDS = 15 * 60


class FailedLogins:
    """Intentos fallidos por IP (en hash) y bloqueos temporales."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self.clock = clock
        self.lock = threading.Lock()
        self.failures: dict[str, deque[float]] = {}
        self.locked_until: dict[str, float] = {}

    def is_locked(self, key: str) -> bool:
        now = self.clock()
        with self.lock:
            until = self.locked_until.get(key)
            if until is not None and now >= until:  # el bloqueo ya ha pasado
                del self.locked_until[key]
                until = None
            return until is not None

    def record_failure(self, key: str) -> None:
        now = self.clock()
        with self.lock:
            failures = self.failures.setdefault(key, deque())
            failures.append(now)
            while failures and now - failures[0] >= LOCK_WINDOW_SECONDS:
                failures.popleft()
            if len(failures) >= FAILED_LOGINS_BEFORE_LOCK:
                self.locked_until[key] = now + LOCK_WINDOW_SECONDS
                del self.failures[key]
                logger.warning(
                    "Página de estadísticas: %d intentos fallidos desde una IP; bloqueada %d min",
                    FAILED_LOGINS_BEFORE_LOCK, LOCK_WINDOW_SECONDS // 60,
                )
            # Las IPs que ya no tienen fallos recientes no ocupan memoria.
            for other in [k for k, v in self.failures.items() if not v or now - v[-1] >= LOCK_WINDOW_SECONDS]:
                del self.failures[other]

    def forget(self, key: str) -> None:
        with self.lock:
            self.failures.pop(key, None)

    def reset(self) -> None:
        with self.lock:
            self.failures.clear()
            self.locked_until.clear()


failed_logins = FailedLogins()

router = APIRouter(include_in_schema=False)
basic_auth = HTTPBasic(auto_error=False, realm="Estadisticas")


def require_admin(
    request: Request,
    credentials: Annotated[HTTPBasicCredentials | None, Depends(basic_auth)],
) -> None:
    token = os.getenv("ADMIN_TOKEN", "")
    if len(token) < MIN_TOKEN_LENGTH:
        if token:
            logger.warning("ADMIN_TOKEN es demasiado corto: la página de estadísticas está desactivada")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    key = chat_limits.ip_key(get_client_ip(request))  # hash con sal, nunca la IP
    if failed_logins.is_locked(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos. Vuelve a probar más tarde.",
            headers={"Retry-After": str(LOCK_WINDOW_SECONDS)},
        )
    if credentials is None:  # el navegador aún no ha pedido la contraseña: no cuenta
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": 'Basic realm="Estadisticas"'},
        )
    # compare_digest tarda lo mismo acierte o no: no da pistas sobre el token.
    if secrets.compare_digest(credentials.password.encode(), token.encode()):
        failed_logins.forget(key)
        return
    failed_logins.record_failure(key)
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


DAILY_DAYS = 30
SUMMARY_DAYS = 7


def daily_row(values: dict) -> list[int]:
    """Columnas de la tabla por días a partir de los contadores de un día (o de una
    suma de días): mensajes, sin información, errores y respondidos por cada
    proveedor. Los errores son los mensajes que ningún proveedor pudo responder y los
    fallos internos; Groq sale sin los que fueron con palabras clave."""
    keywords = values["answered_groq_keywords"]
    return [
        values["messages"],
        values["no_information"],
        values["unanswered"] + values["internal_errors"],
        values["answered_gemini"],
        values["answered_gemini_backup"],
        max(0, values["answered_groq"] - keywords),
        keywords,
    ]


def daily_table(snapshot: dict, today: date) -> str:
    """Mensajes por día de los últimos 30 días, con un resumen de los últimos 7 y 30.

    Sale de los mismos contadores del snapshot (una sola consulta a la base de datos):
    no hace ninguna consulta más."""
    days = [(today - timedelta(days=offset)).isoformat() for offset in range(DAILY_DAYS)]
    empty = {name: 0 for name in COUNTERS}
    rows = {day: daily_row(snapshot["days"].get(day, empty)) for day in days}

    def total(selected: list[str]) -> list[int]:
        return [sum(column) for column in zip(*(rows[day] for day in selected))]

    header = (
        "<th scope='col'>Día (UTC)</th><th scope='col'>Mensajes</th>"
        "<th scope='col'>Sin información</th><th scope='col'>Errores</th>"
        "<th scope='col'>Gemini 3.5</th><th scope='col'>Gemini 3.1 (reserva)</th>"
        "<th scope='col'>Groq</th><th scope='col'>Groq (palabras clave)</th>"
    )

    def line(label: str, values: list[int], css: str = "") -> str:
        cells = "".join(f"<td>{value}</td>" for value in values)
        return f"<tr{css}><th scope='row'>{escape(label)}</th>{cells}</tr>"

    body = [
        line(f"Últimos {SUMMARY_DAYS} días", total(days[:SUMMARY_DAYS]), " class='summary'"),
        line(f"Últimos {DAILY_DAYS} días", total(days), " class='summary'"),
    ]
    for index, day in enumerate(days):
        body.append(line(f"{day} (hoy)" if index == 0 else day, rows[day]))
    return (
        "<div class='table'><table class='daily'>"
        f"<thead><tr>{header}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
    )


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


def storage_notice(snapshot: dict) -> tuple[str, str]:
    """Clase CSS y texto que explican de dónde salen los datos."""
    if snapshot["source"] == "database":
        return "ok", "Datos guardados en PostgreSQL: no se pierden al reiniciar el servicio."
    if snapshot["database_configured"]:
        return "warning", (
            "Sin conexión con la base de datos de estadísticas. Se muestran solo los datos "
            "en memoria desde el último arranque; se guardarán cuando vuelva la conexión."
        )
    return "warning", (
        "STATS_DATABASE_URL no está definida: las estadísticas están solo en memoria y "
        "se pierden si el servicio se reinicia."
    )


def questions_section(
    title: str, anchor: str, page_param: str, page: int, other_params: dict[str, int],
    statuses: tuple[str, ...] | None,
) -> str:
    """Apartado con una tabla de preguntas y enlaces a la página anterior y siguiente."""
    result = chat_stats.questions(statuses, page, QUESTIONS_PER_PAGE)
    pages = max(1, -(-result["total"] // QUESTIONS_PER_PAGE))
    rows = []
    for row in result["rows"]:
        asked_at = row["asked_at"].strftime("%d/%m/%Y %H:%M:%S")
        provider = PROVIDER_LABELS.get(row["provider"], row["provider"] or "-")
        rows.append(
            "<tr>"
            f"<td class='nowrap'>{escape(asked_at)}</td>"
            f"<td>{escape(row['question'])}</td>"
            f"<td>{escape(row['answer'])}</td>"
            f"<td>{escape(provider)}</td>"
            f"<td>{escape(QUESTION_STATUSES.get(row['status'], row['status']))}</td>"
            "</tr>"
        )
    if not rows:
        table = "<p>No hay preguntas.</p>"
    else:
        table = (
            "<div class='table'><table class='questions'><thead><tr>"
            "<th scope='col'>Fecha (UTC)</th><th scope='col'>Pregunta</th>"
            "<th scope='col'>Respuesta</th><th scope='col'>Proveedor</th>"
            "<th scope='col'>Estado</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table></div>"
        )

    def link(target: int, text: str) -> str:
        params = {**other_params, page_param: target}
        query = "&amp;".join(f"{name}={value}" for name, value in params.items())
        return f"<a href='?{query}#{anchor}'>{text}</a>"

    nav = []
    if page > 1:
        nav.append(link(page - 1, "← Anteriores"))
    nav.append(f"<span>Página {min(page, pages)} de {pages} · {result['total']} preguntas</span>")
    if page < pages:
        nav.append(link(page + 1, "Siguientes →"))
    memory_note = (
        "<p class='notice warning'>Sin conexión con la base de datos: solo las preguntas "
        "en memoria desde el último arranque.</p>"
        if result["source"] == "memory" else ""
    )
    return (
        f"<h2 id='{anchor}'>{escape(title)}</h2>{memory_note}{table}"
        f"<p class='pages'>{' '.join(nav)}</p>"
    )


@router.get("/admin/stats", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
def admin_stats(
    missing_page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    latest_page: Annotated[int, Query(ge=1, le=10_000)] = 1,
) -> HTMLResponse:
    snapshot = chat_stats.snapshot()
    notice = storage_notice(snapshot)
    used_today = MESSAGES_PER_DAY_TOTAL - chat_limits.remaining_total()
    limits = [
        ("Mensajes usados del tope global (últimas 24 h)",
         f"{used_today} de {MESSAGES_PER_DAY_TOTAL}"),
        ("Límite por IP y minuto", MESSAGES_PER_MINUTE_PER_IP),
        ("Límite por IP y día", MESSAGES_PER_DAY_PER_IP),
        ("Longitud máxima de la pregunta", f"{MAX_MESSAGE_LENGTH} caracteres"),
        ("Datos desde", snapshot["since"]),
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
  <link rel="icon" href="/static/img/favicon.svg" type="image/svg+xml">
  <link rel="icon" href="/static/img/favicon.ico" sizes="16x16 32x32">
  <link rel="apple-touch-icon" href="/static/img/apple-touch-icon.png">
  <link rel="stylesheet" href="/static/admin.css">
</head>
<body>
  <main>
    <h1>Estadísticas del chat</h1>
    <p>Las preguntas se guardan de forma anónima, sin IPs, y se borran a los
    {QUESTION_DAYS} días. Para los límites solo se guarda un hash de la IP, que se borra
    a las 24 horas. La aplicación no guarda IPs; el hosting puede registrarlas como parte
    de sus logs de servidor. <strong>Todas las horas y los días de este panel están en UTC</strong>
    (en España, una o dos horas menos que la hora local según la época del año).</p>
    <p class="notice {notice[0]}">{escape(notice[1])}</p>
    <p class="cap">Tope global de mensajes: <strong>{used_today} de {MESSAGES_PER_DAY_TOTAL}</strong>
    usados en las últimas 24 horas.</p>
    <h2>Mensajes por día (últimos {DAILY_DAYS} días, UTC)</h2>
    {daily_table(snapshot, chat_stats.clock().date())}
    <h2>Límites</h2>
    <div class="table"><table><tbody>{limit_rows}</tbody></table></div>
    <h2>Detalle por contador</h2>
    {stats_table(snapshot)}
    {questions_section("Preguntas sin respuesta o rechazadas", "missing", "missing_page",
                       missing_page, {"latest_page": latest_page}, MISSING_STATUSES)}
    {questions_section("Últimas preguntas", "latest", "latest_page",
                       latest_page, {"missing_page": missing_page}, None)}
  </main>
</body>
</html>"""
    return HTMLResponse(
        add_versions(page),
        headers={"Cache-Control": HTML_CACHE, "X-Robots-Tag": "noindex, nofollow"},
    )
