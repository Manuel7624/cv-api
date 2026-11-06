"""Modelos de datos (Pydantic). Definen la forma de lo que devuelve la API.

FastAPI los usa para validar las respuestas y para generar la documentación
automática en /docs.
"""
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.chat_limits import MAX_MESSAGE_LENGTH


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
    period: str | None
    status: str


class Skills(BaseModel):
    languages: list[str]
    tools: list[str]
    concepts: list[str]


class Language(BaseModel):
    name: str
    level: str


class ChatRequest(BaseModel):
    message: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE_LENGTH),
    ]


class ChatResponse(BaseModel):
    answer: str
