"""API del currículum de Manuel Sastre.

Para arrancarla:  uvicorn app.main:app --reload
Web del currículum:  http://127.0.0.1:8000/
Documentación interactiva (Swagger):  http://127.0.0.1:8000/docs
"""
import json
import mimetypes
import os
import re
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app import chat, crud, retrieval
from app.admin import router as admin_router
from app.chat_limits import MAX_MESSAGE_LENGTH
from app.llm import RESTART
from app.database import Base, SessionLocal, engine, get_db
from app.rate_limit import chat_limits, get_client_ip
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

# Cabeceras de seguridad para todas las respuestas.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "DENY",
}
# Solo se permiten scripts, estilos y peticiones de esta misma web: aunque se
# colara HTML en la página, no podría cargar ni ejecutar código de fuera.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; img-src 'self' data:; object-src 'none'; "
    "base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
)
# /docs carga Swagger desde un CDN, así que esa política lo rompería.
PATHS_WITHOUT_CSP = ("/docs", "/redoc")

# La portada lleva la longitud máxima de la pregunta, que se puede configurar.
INDEX_HTML = (STATIC_DIR / "index.html").read_text(encoding="utf-8").replace(
    "{{MAX_MESSAGE_LENGTH}}", str(MAX_MESSAGE_LENGTH)
)

# Cada ruta que declara este tipo recibe una sesión abierta para esa petición.
DbSession = Annotated[Session, Depends(get_db)]


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Al arrancar, crea las tablas, carga los datos, prepara la búsqueda del chat y
    empieza a guardar las estadísticas. Al apagar, envía las que queden pendientes."""
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


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.update(SECURITY_HEADERS)
    if not request.url.path.startswith(PATHS_WITHOUT_CSP):
        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
    return response


@app.get("/", include_in_schema=False)
def root(request: Request) -> HTMLResponse:
    """La raíz muestra la web del currículum."""
    return HTMLResponse(INDEX_HTML.replace("{{BASE_URL}}", public_base_url(request)))


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
