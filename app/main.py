"""API del currículum de Manuel Sastre.

Para arrancarla:  uvicorn app.main:app --reload
Web del currículum:  http://127.0.0.1:8000/
Documentación interactiva (Swagger):  http://127.0.0.1:8000/docs
"""
import json
import logging
import mimetypes
import os
import re
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app import chat, crud, retrieval
from app.admin import router as admin_router
from app.chat_limits import MAX_MESSAGE_LENGTH
from app.llm import RESTART
from app.database import Base, SessionLocal, engine, get_db
from app.rate_limit import chat_limits, get_client_ip
from app.static_files import HTML_CACHE, UNVERSIONED_CACHE, add_versions, cache_control
from app.security import HSTS_HEADER, SECURITY_HEADERS, LimitRequestSize, arrived_over_https
from app.schemas import (
    ChatRequest,
    ChatResponse,
    Education,
    Experience,
    Language,
    Profile,
    Project,
    Skills,
)
from app.seed import seed
from app.stats import chat_stats

STATIC_DIR = Path(__file__).parent / "static"
# Windows no siempre conoce el tipo de las fuentes woff2.
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("image/x-icon", ".ico")

# Cabeceras de seguridad para todas las respuestas.
# Solo se permiten scripts, estilos y peticiones de esta misma web: aunque se
# colara HTML en la página, no podría cargar ni ejecutar código de fuera.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; img-src 'self' data:; object-src 'none'; "
    "base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
)
# /docs carga Swagger desde un CDN, así que esa política lo rompería.
PATHS_WITHOUT_CSP = ("/docs", "/redoc")

# La portada lleva la longitud máxima de la pregunta, que se puede configurar.
# Cada referencia a /static/ lleva ?v=<hash del contenido> (ver app/static_files.py):
# al publicar un cambio, el navegador pide el archivo nuevo sin borrar la caché.
INDEX_HTML = add_versions(
    (STATIC_DIR / "index.html").read_text(encoding="utf-8").replace(
        "{{MAX_MESSAGE_LENGTH}}", str(MAX_MESSAGE_LENGTH)
    )
)

# Cada mensaje permitido se apunta para guardarlo en la base de datos (si la hay),
# en el hilo de las estadísticas: el chat nunca espera a la base de datos.
chat_limits.on_use = chat_stats.log_limit_use
# Los límites siguen donde estaban antes de reiniciar (si hay base de datos). Se
# cargan con el primer mensaje, no al arrancar, para no despertar a Neon sin motivo.
chat_limits.loader = chat_stats.load_limit_uses

# Cada ruta que declara este tipo recibe una sesión abierta para esa petición.
DbSession = Annotated[Session, Depends(get_db)]


def silence_access_log() -> None:
    """Quita la línea que uvicorn escribe por cada petición ("GET / 200 OK" con la IP).

    El Dockerfile ya arranca con --no-access-log, pero así tampoco aparece si alguien
    arranca la app con otro comando (o con una imagen antigua): la IP de quien visita
    la web no debe acabar en los logs.
    """
    logging.getLogger("uvicorn.access").disabled = True


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Al arrancar, crea las tablas, carga los datos, prepara la búsqueda del chat y
    empieza a guardar las estadísticas. Al apagar, envía las que queden pendientes."""
    silence_access_log()
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        seed(session)
        retrieval.build_index(crud.get_extra_info(session, fixed_answer=False))
    chat_stats.connect(os.getenv("STATS_DATABASE_URL"))
    yield
    chat_stats.close()


app = FastAPI(
    title="CV API · Manuel Sastre",
    description="API REST que sirve mi currículum. Pruébala desde esta página.",
    version="0.1.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(admin_router)
# Peticiones de más de 32 KB: 413 sin leerlas enteras (ver app/security.py).
app.add_middleware(LimitRequestSize)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.update(SECURITY_HEADERS)
    static_cache = cache_control(request.url.path, request.url.query)
    if static_cache and response.status_code == 200:
        response.headers["Cache-Control"] = static_cache
    if arrived_over_https(request.url.scheme, request.headers.get("x-forwarded-proto")):
        response.headers["Strict-Transport-Security"] = HSTS_HEADER
    if not request.url.path.startswith(PATHS_WITHOUT_CSP):
        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
    return response


# Algunos navegadores (y el móvil al guardar la web en la pantalla de inicio) piden
# estos iconos en la raíz aunque la página indique otra ruta.
ROOT_ICONS = {
    "/favicon.ico": ("favicon.ico", "image/x-icon"),
    "/apple-touch-icon.png": ("apple-touch-icon.png", "image/png"),
}


@app.get("/favicon.ico", include_in_schema=False)
@app.get("/apple-touch-icon.png", include_in_schema=False)
def root_icon(request: Request) -> FileResponse:
    name, media_type = ROOT_ICONS[request.url.path]
    return FileResponse(
        STATIC_DIR / "img" / name,
        media_type=media_type,
        # Sin versión en la URL: el navegador pregunta cada vez si ha cambiado.
        headers={"Cache-Control": UNVERSIONED_CACHE},
    )


@app.get("/", include_in_schema=False)
def root(request: Request) -> HTMLResponse:
    """La raíz muestra la web del currículum."""
    return HTMLResponse(
        INDEX_HTML.replace("{{BASE_URL}}", public_base_url(request)),
        # Que el HTML no se guarde: así siempre lleva las versiones nuevas.
        headers={"Cache-Control": HTML_CACHE},
    )


# Solo nombres de host normales (letras, números, puntos, guiones y puerto).
VALID_HOST = re.compile(r"^[A-Za-z0-9.-]+(:[0-9]{1,5})?$")


def public_base_url(request: Request) -> str:
    """Dirección pública de la web, para la imagen al compartir en LinkedIn (que
    necesita una URL completa). Se puede fijar con PUBLIC_URL; si no, se deduce de
    la petición. Detrás del proxy de Render, el esquema llega en X-Forwarded-Proto."""
    configured = os.getenv("PUBLIC_URL", "").strip().rstrip("/")
    if configured:
        return configured
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip()
    if scheme not in ("http", "https"):
        scheme = "https"
    host = request.headers.get("host", "")
    if not VALID_HOST.match(host):
        return ""  # sin host fiable, la ruta relativa (vale para todo salvo la vista previa)
    return f"{scheme}://{host}"


@app.get("/health", tags=["sistema"])
def health() -> dict[str, str]:
    """Comprobación de que el servicio está vivo (la usará el despliegue)."""
    return {"status": "ok"}


@app.get("/profile", response_model=Profile, tags=["cv"])
def get_profile(db: DbSession) -> Profile:
    return crud.get_profile(db)


@app.get("/experience", response_model=list[Experience], tags=["cv"])
def get_experience(db: DbSession) -> list[Experience]:
    return crud.get_experience(db)


@app.get("/projects", response_model=list[Project], tags=["cv"])
def get_projects(db: DbSession) -> list[Project]:
    return crud.get_projects(db)


@app.get("/education", response_model=list[Education], tags=["cv"])
def get_education(db: DbSession) -> list[Education]:
    return crud.get_education(db)


@app.get("/skills", response_model=Skills, tags=["cv"])
def get_skills(db: DbSession) -> Skills:
    return crud.get_skills(db)


@app.get("/languages", response_model=list[Language], tags=["cv"])
def get_languages(db: DbSession) -> list[Language]:
    return crud.get_languages(db)


def check_chat_limits(request: Request) -> None:
    """Límite de mensajes por IP y total; lanza un 429 si se ha superado."""
    blocked = chat_limits.check(get_client_ip(request))
    if blocked:
        chat_stats.count(f"blocked_{blocked}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Has enviado muchos mensajes. Espera un poco o escríbeme "
            "desde la sección de contacto.",
        )


@app.post("/chat", response_model=ChatResponse, tags=["chat"])
def post_chat(payload: ChatRequest, request: Request, db: DbSession) -> ChatResponse:
    """Responde preguntas sobre el perfil de Manuel, con límite de mensajes por IP."""
    check_chat_limits(request)
    return ChatResponse(answer=chat.answer_question(db, payload.message, payload.history))


@app.post(
    "/chat/stream",
    tags=["chat"],
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
def post_chat_stream(payload: ChatRequest, request: Request, db: DbSession) -> StreamingResponse:
    """Igual que POST /chat, pero envía la respuesta a trozos según se genera.

    Formato server-sent events: líneas `data: {"text": "..."}` con cada trozo y
    `data: {"restart": true}` si hay que borrar lo recibido y empezar de nuevo.
    """
    check_chat_limits(request)

    def events() -> Iterator[str]:
        for event in chat.stream_answer(db, payload.message, payload.history):
            data = {"restart": True} if event is RESTART else {"text": event}
            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        # Que ningún proxy guarde la respuesta entera antes de enviarla.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
