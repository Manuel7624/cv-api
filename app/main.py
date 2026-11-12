"""API del currículum de Manuel Sastre.

Para arrancarla:  uvicorn app.main:app --reload
Web del currículum:  http://127.0.0.1:8000/
Documentación interactiva (Swagger):  http://127.0.0.1:8000/docs
"""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app import chat, crud, retrieval
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

STATIC_DIR = Path(__file__).parent / "static"

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

# Cada ruta que declara este tipo recibe una sesión abierta para esa petición.
DbSession = Annotated[Session, Depends(get_db)]


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Al arrancar, crea las tablas, carga los datos y prepara la búsqueda del chat."""
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        seed(session)
        retrieval.build_index(crud.get_extra_info(session, fixed_answer=False))
    yield


app = FastAPI(
    title="CV API · Manuel Sastre",
    description="API REST que sirve mi currículum. Pruébala desde esta página.",
    version="0.1.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.update(SECURITY_HEADERS)
    if not request.url.path.startswith(PATHS_WITHOUT_CSP):
        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
    return response


@app.get("/", include_in_schema=False)
def root() -> FileResponse:
    """La raíz muestra la web del currículum."""
    return FileResponse(STATIC_DIR / "index.html")


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


@app.post("/chat", response_model=ChatResponse, tags=["chat"])
def post_chat(payload: ChatRequest, request: Request, db: DbSession) -> ChatResponse:
    """Responde preguntas sobre el perfil de Manuel, con límite de mensajes por IP."""
    if not chat_limits.allow(get_client_ip(request)):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Has enviado muchos mensajes. Espera un poco o escribe a Manuel "
            "desde la sección de contacto.",
        )
    return ChatResponse(answer=chat.answer_question(db, payload.message, payload.history))
