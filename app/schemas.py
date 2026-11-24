"""Modelos de datos (Pydantic). Definen la forma de lo que devuelve la API.

FastAPI los usa para validar las respuestas y para generar la documentación
automática en /docs.
"""
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.chat_limits import MAX_ANSWER_LENGTH, MAX_HISTORY_MESSAGES, MAX_MESSAGE_LENGTH


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
    backend: list[str]
    tools: list[str]
    concepts: list[str]


class Language(BaseModel):
    name: str
    level: str


class ChatTurn(BaseModel):
    """Un mensaje anterior de la conversación, enviado por el navegador."""

    role: Literal["user", "assistant"]
    content: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_ANSWER_LENGTH),
    ]

    @model_validator(mode="after")
    def check_user_length(self) -> "ChatTurn":
        if self.role == "user" and len(self.content) > MAX_MESSAGE_LENGTH:
            raise ValueError("pregunta demasiado larga")
        return self


class ChatRequest(BaseModel):
    message: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE_LENGTH),
    ]
    history: list[ChatTurn] = Field(default_factory=list, max_length=MAX_HISTORY_MESSAGES)


class ChatResponse(BaseModel):
    answer: str
