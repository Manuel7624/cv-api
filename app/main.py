"""API del currículum de Manuel Sastre.

Para arrancarla:  uvicorn app.main:app --reload
Documentación interactiva (Swagger):  http://127.0.0.1:8000/docs
"""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import crud
from app.database import Base, SessionLocal, engine, get_db
from app.schemas import Education, Experience, Profile, Project, Skills
from app.seed import seed

# Cada ruta que declara este tipo recibe una sesión abierta para esa petición.
DbSession = Annotated[Session, Depends(get_db)]


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Al arrancar, crea las tablas que falten y carga los datos iniciales."""
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        seed(session)
    yield


app = FastAPI(
    title="CV API · Manuel Sastre",
    description="API REST que sirve mi currículum. Pruébala desde esta página.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """La raíz lleva directamente a la documentación."""
    return RedirectResponse(url="/docs")


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
