"""Datos iniciales del currículum y su carga en la base de datos.

Se cargan al arrancar la aplicación, solo si la base está vacía. Por eso, cambiar
algo aquí no actualiza una base ya creada: en local hay que borrar cv.db y
reiniciar.
Importante: solo se incluye lo que es verdad y se puede defender en entrevista.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models

PROFILE = {
    "name": "Manuel Sastre",
    "title": "Junior Backend Developer",
    "location": "Zaragoza, España",
    "summary": (
        "Técnico Superior en Desarrollo de Aplicaciones Multiplataforma, con "
        "prácticas en una empresa de software (Python, Docker y GitLab) y un "
        "proyecto propio en Android con Java y SQLite. Busco mi primera "
        "oportunidad como desarrollador backend junior."
    ),
    "availability": "Disponibilidad inmediata",
    "email": "manusastrenar@gmail.com",
    "github": "https://github.com/Manuel7624",
}

EXPERIENCE = [
    {
        "role": "Prácticas de desarrollo (FCT)",
        "company": "Brainy Inteligencia Semántica",
        "kind": "Prácticas",
        "period": "26 de enero de 2026 – 15 de mayo de 2026",
        "highlights": [
            "Refactorización y optimización de workers en Python para mejorar "
            "su estructura y legibilidad.",
            "Dockerización de los workers que aún no estaban contenerizados y "
            "subida de los cambios a nuevas ramas en GitLab.",
            "Puesta en marcha en local de la API (versión anterior) de la "
            "plataforma, junto con el frontend y una base de datos de pruebas, "
            "para familiarizarme con su arquitectura y funcionamiento; "
            "nociones de Kafka.",
            "Control de versiones con Git y GitLab (clonado, ramas, commits y "
            "push) y uso básico de la consola.",
        ],
    },
    {
        "role": "Azafato",
        "company": "The Wave 2026, Zaragoza",
        "kind": "Trabajo temporal",
        "period": "14 – 16 de abril de 2026",
        "highlights": [
            "Preparación y reorganización del escenario principal entre "
            "intervenciones.",
            "Atención e información a los asistentes durante el evento.",
        ],
    },
]

PROJECTS = [
    {
        "name": "Balancea",
        "description": "Aplicación móvil Android de finanzas personales "
        "(proyecto final de grado).",
        "technologies": ["Java", "Android Studio", "SQLite", "MPAndroidChart"],
        "repository": "https://github.com/Manuel7624/TFG_ManuelSastre",
        "highlights": [
            "Al registrarte indicas tu saldo y vas añadiendo gastos e "
            "ingresos, que actualizan el saldo.",
            "Gráficas de ingresos vs gastos mensuales y anuales, evolución "
            "mensual y desglose por categoría.",
            "Persistencia local con SQLite y acceso a datos centralizado en "
            "clases propias; código organizado en paquetes y documentado con "
            "JavaDoc.",
        ],
    },
]

EDUCATION = [
    {
        "title": "Técnico Superior en Desarrollo de Aplicaciones Multiplataforma",
        "institution": "Océano Atlántico",
        "period": "2024 – 2026",
        "status": "Completado",
    },
    {
        "title": "Curso de Python",
        "institution": "Coddy",
        "period": "2026",
        "status": "En curso",
    },
    {
        "title": "Bachillerato de Ciencias",
        "institution": "IES Tiempos Modernos",
        "period": "2022 – 2024",
        "status": "Completado",
    },
]

SKILLS = {
    "languages": [
        "Python (prácticas y curso en Coddy)",
        "Java (grado y proyecto final)",
        "SQL (SQLite)",
    ],
    "tools": [
        "Docker",
        "Git",
        "GitLab",
        "Android Studio",
        "Visual Studio Code",
        "Consola",
    ],
    "concepts": [
        "Programación orientada a objetos",
        "APIs",
        "Nociones de Kafka",
        "Windows y Linux",
    ],
}


def seed(session: Session) -> None:
    """Carga los datos iniciales si la base está vacía.

    Todo se guarda en un único commit: o se carga entero o no se carga nada, así
    que comprobar si existe el perfil basta para saber si ya está cargado.
    """
    if session.scalar(select(models.Profile.id)) is not None:
        return

    session.add(models.Profile(**PROFILE))

    for position, item in enumerate(EXPERIENCE):
        session.add(
            models.Experience(
                role=item["role"],
                company=item["company"],
                kind=item["kind"],
                period=item["period"],
                position=position,
                highlights=[
                    models.ExperienceHighlight(text=text, position=index)
                    for index, text in enumerate(item["highlights"])
                ],
            )
        )

    for position, item in enumerate(PROJECTS):
        session.add(
            models.Project(
                name=item["name"],
                description=item["description"],
                repository=item["repository"],
                position=position,
                highlights=[
                    models.ProjectHighlight(text=text, position=index)
                    for index, text in enumerate(item["highlights"])
                ],
                technologies=[
                    models.ProjectTechnology(name=name, position=index)
                    for index, name in enumerate(item["technologies"])
                ],
            )
        )

    for position, item in enumerate(EDUCATION):
        session.add(models.Education(**item, position=position))

    for category, names in SKILLS.items():
        for position, name in enumerate(names):
            session.add(models.Skill(category=category, name=name, position=position))

    session.commit()
