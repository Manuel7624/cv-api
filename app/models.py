"""Tablas de la base de datos (SQLAlchemy).

No confundir con app/schemas.py: aquí se define cómo se guardan los datos y allí
la forma de lo que devuelve la API.

La columna `position` guarda el orden en el que se muestra cada elemento, porque
SQL no garantiza ningún orden si no se le indica.
"""
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Profile(Base):
    __tablename__ = "profile"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    title: Mapped[str]
    location: Mapped[str]
    summary: Mapped[str]
    availability: Mapped[str]
    email: Mapped[str]
    github: Mapped[str]
    linkedin: Mapped[str | None]


class Experience(Base):
    __tablename__ = "experience"

    id: Mapped[int] = mapped_column(primary_key=True)
    role: Mapped[str]
    company: Mapped[str]
    kind: Mapped[str]
    period: Mapped[str]
    position: Mapped[int]

    highlights: Mapped[list["ExperienceHighlight"]] = relationship(
        order_by="ExperienceHighlight.position",
        cascade="all, delete-orphan",
    )


class ExperienceHighlight(Base):
    __tablename__ = "experience_highlight"

    id: Mapped[int] = mapped_column(primary_key=True)
    experience_id: Mapped[int] = mapped_column(ForeignKey("experience.id"))
    text: Mapped[str]
    position: Mapped[int]


class Project(Base):
    __tablename__ = "project"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    description: Mapped[str]
    repository: Mapped[str]
    position: Mapped[int]

    highlights: Mapped[list["ProjectHighlight"]] = relationship(
        order_by="ProjectHighlight.position",
        cascade="all, delete-orphan",
    )
    technologies: Mapped[list["ProjectTechnology"]] = relationship(
        order_by="ProjectTechnology.position",
        cascade="all, delete-orphan",
    )


class ProjectHighlight(Base):
    __tablename__ = "project_highlight"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"))
    text: Mapped[str]
    position: Mapped[int]


class ProjectTechnology(Base):
    __tablename__ = "project_technology"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"))
    name: Mapped[str]
    position: Mapped[int]


class Education(Base):
    __tablename__ = "education"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    institution: Mapped[str]
    period: Mapped[str | None]
    status: Mapped[str]
    position: Mapped[int]


class Skill(Base):
    __tablename__ = "skill"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str]  # "languages", "tools" o "concepts"
    name: Mapped[str]
    position: Mapped[int]


class Language(Base):
    __tablename__ = "language"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    level: Mapped[str]
    position: Mapped[int]
