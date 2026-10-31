"""Datos del currículum.

De momento viven aquí, en el código. En el siguiente paso los moveremos a una
base de datos y esta capa será la que los lea.
Importante: solo se incluye lo que es verdad y se puede defender en entrevista.
"""
from app.schemas import (
    Contact,
    Education,
    Experience,
    Profile,
    Project,
    Skills,
)

PROFILE = Profile(
    name="Manuel Sastre",
    title="Junior Backend Developer",
    location="Zaragoza, España",
    summary=(
        "Técnico Superior en Desarrollo de Aplicaciones Multiplataforma, con "
        "prácticas en una empresa de software (Python, Docker y GitLab) y un "
        "proyecto propio en Android con Java y SQLite. Busco mi primera "
        "oportunidad como desarrollador backend junior."
    ),
    availability="Disponibilidad inmediata",
    contact=Contact(
        email="manusastrenar@gmail.com",
        github="https://github.com/Manuel7624",
    ),
)

EXPERIENCE = [
    Experience(
        role="Prácticas de desarrollo (FCT)",
        company="Brainy Inteligencia Semántica",
        kind="Prácticas",
        period="26 de enero de 2026 – 15 de mayo de 2026",
        highlights=[
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
    ),
    Experience(
        role="Azafato",
        company="The Wave 2026, Zaragoza",
        kind="Trabajo temporal",
        period="14 – 16 de abril de 2026",
        highlights=[
            "Preparación y reorganización del escenario principal entre "
            "intervenciones.",
            "Atención e información a los asistentes durante el evento.",
        ],
    ),
]

PROJECTS = [
    Project(
        name="Balancea",
        description="Aplicación móvil Android de finanzas personales "
        "(proyecto final de grado).",
        technologies=["Java", "Android Studio", "SQLite", "MPAndroidChart"],
        repository="https://github.com/Manuel7624/TFG_ManuelSastre",
        highlights=[
            "Al registrarte indicas tu saldo y vas añadiendo gastos e "
            "ingresos, que actualizan el saldo.",
            "Gráficas de ingresos vs gastos mensuales y anuales, evolución "
            "mensual y desglose por categoría.",
            "Persistencia local con SQLite y acceso a datos centralizado en "
            "clases propias; código organizado en paquetes y documentado con "
            "JavaDoc.",
        ],
    ),
]

EDUCATION = [
    Education(
        title="Técnico Superior en Desarrollo de Aplicaciones Multiplataforma",
        institution="Océano Atlántico",
        period="2024 – 2026",
        status="Completado",
    ),
    Education(
        title="Curso de Python",
        institution="Coddy",
        period="2026",
        status="En curso",
    ),
    Education(
        title="Bachillerato de Ciencias",
        institution="IES Tiempos Modernos",
        period="2022 – 2024",
        status="Completado",
    ),
]

SKILLS = Skills(
    languages=[
        "Python (prácticas y curso en Coddy)",
        "Java (grado y proyecto final)",
        "SQL (SQLite)",
    ],
    tools=[
        "Docker",
        "Git",
        "GitLab",
        "Android Studio",
        "Visual Studio Code",
        "Consola",
    ],
    concepts=[
        "Programación orientada a objetos",
        "APIs",
        "Nociones de Kafka",
        "Windows y Linux",
    ],
)
