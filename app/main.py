"""API del currículum de Manuel Sastre.

Para arrancarla:  uvicorn app.main:app --reload
Documentación interactiva (Swagger):  http://127.0.0.1:8000/docs
"""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app import data
from app.database import Base, SessionLocal, engine
from app.schemas import Education, Experience, Profile, Project, Skills
from app.seed import seed


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
def get_profile() -> Profile:
    return data.PROFILE


@app.get("/experience", response_model=list[Experience], tags=["cv"])
def get_experience() -> list[Experience]:
    return data.EXPERIENCE


@app.get("/projects", response_model=list[Project], tags=["cv"])
def get_projects() -> list[Project]:
    return data.PROJECTS


@app.get("/education", response_model=list[Education], tags=["cv"])
def get_education() -> list[Education]:
    return data.EDUCATION


@app.get("/skills", response_model=Skills, tags=["cv"])
def get_skills() -> Skills:
    return data.SKILLS
