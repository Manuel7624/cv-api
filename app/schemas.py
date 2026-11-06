"""Modelos de datos (Pydantic). Definen la forma de lo que devuelve la API.

FastAPI los usa para validar las respuestas y para generar la documentación
automática en /docs.
"""
from pydantic import BaseModel


class Contact(BaseModel):
    email: str
    github: str
    linkedin: str | None


class Profile(BaseModel):
    name: str
    title: str
    location: str
    summary: str
    availability: str
    contact: Contact


class Experience(BaseModel):
    role: str
    company: str
    kind: str
    period: str
    highlights: list[str]


class Project(BaseModel):
    name: str
    description: str
    technologies: list[str]
    repository: str
    highlights: list[str]


class Education(BaseModel):
    title: str
    institution: str
    period: str
    status: str


class Skills(BaseModel):
    languages: list[str]
    tools: list[str]
    concepts: list[str]


class Language(BaseModel):
    name: str
    level: str
