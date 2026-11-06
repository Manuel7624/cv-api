"""Consultas a la base de datos.

Cada función lee las tablas (app/models.py) y devuelve los datos con la forma que
expone la API (app/schemas.py).
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas


def get_profile(db: Session) -> schemas.Profile:
    profile = db.scalars(select(models.Profile)).one()
    return schemas.Profile(
        name=profile.name,
        title=profile.title,
        location=profile.location,
        summary=profile.summary,
        availability=profile.availability,
        contact=schemas.Contact(
            email=profile.email,
            github=profile.github,
            linkedin=profile.linkedin,
        ),
    )


def get_experience(db: Session) -> list[schemas.Experience]:
    rows = db.scalars(select(models.Experience).order_by(models.Experience.position))
    return [
        schemas.Experience(
            role=row.role,
            company=row.company,
            kind=row.kind,
            period=row.period,
            highlights=[highlight.text for highlight in row.highlights],
        )
        for row in rows
    ]


def get_projects(db: Session) -> list[schemas.Project]:
    rows = db.scalars(select(models.Project).order_by(models.Project.position))
    return [
        schemas.Project(
            name=row.name,
            description=row.description,
            technologies=[technology.name for technology in row.technologies],
            repository=row.repository,
            highlights=[highlight.text for highlight in row.highlights],
        )
        for row in rows
    ]


def get_education(db: Session) -> list[schemas.Education]:
    rows = db.scalars(select(models.Education).order_by(models.Education.position))
    return [
        schemas.Education(
            title=row.title,
            institution=row.institution,
            period=row.period,
            status=row.status,
        )
        for row in rows
    ]


def get_skills(db: Session) -> schemas.Skills:
    rows = db.scalars(select(models.Skill).order_by(models.Skill.position))
    skills: dict[str, list[str]] = {"languages": [], "tools": [], "concepts": []}
    for row in rows:
        skills[row.category].append(row.name)
    return schemas.Skills(**skills)


def get_languages(db: Session) -> list[schemas.Language]:
    rows = db.scalars(select(models.Language).order_by(models.Language.position))
    return [schemas.Language(name=row.name, level=row.level) for row in rows]
