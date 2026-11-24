def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_profile(client):
    response = client.get("/profile")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Manuel Sastre"
    assert "github" in body["contact"]


def test_profile_contact_fields(client):
    contact = client.get("/profile").json()["contact"]
    assert set(contact) == {"email", "github", "linkedin"}


def test_profile_does_not_expose_phone(client):
    """El teléfono no debe aparecer en una API pública."""
    assert "phone" not in client.get("/profile").json()["contact"]


def test_experience_is_not_empty(client):
    response = client.get("/experience")
    assert response.status_code == 200
    assert len(response.json()) >= 1


def test_projects_include_balancea(client):
    names = [p["name"] for p in client.get("/projects").json()]
    assert "Balancea" in names


def test_education_and_skills(client):
    assert client.get("/education").status_code == 200
    assert "languages" in client.get("/skills").json()


def test_cv_matches_the_pdf(client):
    summary = client.get("/profile").json()["summary"]
    assert summary.endswith("una web personal con API propia (Python y FastAPI) y chat de IA.")
    assert "Busco mi primera" not in summary
    internship = client.get("/experience").json()[0]
    assert internship["period"] == "Ene 2026 – May 2026"
    assert client.get("/experience").json()[1]["period"] == "Abr 2026"
    assert "Apoyo de Codex" in internship["highlights"][0]
    assert internship["highlights"][1].startswith("Pruebas de integración manuales")
    assert "documento de entrada" in internship["highlights"][1]
    assert "real" not in internship["highlights"][1] and "ejemplo" not in internship["highlights"][1]
    assert not any("Kafka" in text or "Puesta en marcha en local" in text for text in internship["highlights"])
    projects = client.get("/projects").json()
    assert [project["name"] for project in projects] == ["CV con API y chat de IA", "Balancea"]
    assert projects[0]["repository"] == "https://github.com/Manuel7624/cv-api"
    assert projects[0]["technologies"] == ["Python", "FastAPI", "SQLite", "PostgreSQL", "Docker", "pytest"]
    skills = client.get("/skills").json()
    assert skills["languages"][-1] == "SQL (SQLite, PostgreSQL)"
    assert skills["backend"] == ["FastAPI", "APIs REST", "OpenAPI/Swagger", "SQLAlchemy", "Rate limiting", "Nociones de RAG"]
    assert "GitHub" in skills["tools"]
    assert "Nociones de Kafka" in skills["concepts"]
    assert "Codex" in client.get("/skills").json()["tools"]
    assert "Claude Code" in client.get("/skills").json()["tools"]


def test_python_course_has_no_year(client):
    course = client.get("/education").json()[1]
    assert course["title"] == "Curso de Python"
    assert course["period"] is None
    assert course["status"] == "En curso"


def test_profile_includes_linkedin(client):
    contact = client.get("/profile").json()["contact"]
    assert contact["linkedin"] == "https://www.linkedin.com/in/manuel-sastre-naranjo"


def test_languages(client):
    assert client.get("/languages").json() == [
        {"name": "Español", "level": "nativo"},
        {"name": "Inglés", "level": "B2 (2022)"},
    ]


def test_lists_keep_their_order(client):
    """Las listas salen en el mismo orden que en el CV."""
    experience = client.get("/experience").json()
    assert experience[0]["company"] == "Brainy Inteligencia Semántica"
    assert experience[0]["highlights"][0].startswith("Refactorización")
    assert client.get("/projects").json()[0]["technologies"][0] == "Python"
    assert client.get("/projects").json()[1]["technologies"][0] == "Java"
    assert client.get("/education").json()[-1]["title"] == "Bachillerato de Ciencias"
    assert client.get("/skills").json()["tools"][0] == "Docker"


def test_health_answers_get_and_head_without_touching_any_database(client, monkeypatch):
    from app import crud, database
    from app.stats import chat_stats

    def forbidden(*_args, **_kwargs):
        raise AssertionError("/health no debe consultar ninguna base de datos")

    for name in ("get_profile", "get_experience", "get_extra_info", "get_skills"):
        monkeypatch.setattr(crud, name, forbidden)
    monkeypatch.setattr(database, "SessionLocal", forbidden)
    monkeypatch.setattr(chat_stats, "snapshot", forbidden)
    assert client.get("/health").json() == {"status": "ok"}
    head = client.head("/health")
    assert head.status_code == 200 and head.content == b""


def test_health_is_not_in_swagger(client):
    assert "/health" not in client.get("/openapi.json").json()["paths"]


def test_new_cv_information_lives_in_separate_short_entries(client, db_session):
    """Lo nuevo del CV (IA, panel, rate limiting...) va en entradas cortas del RAG, no en el bloque
    que va siempre en el prompt, y nunca revela la ruta ni la contraseña del panel."""
    from app import crud

    entries = crud.get_extra_info(db_session, fixed_answer=False)
    questions = " ".join(entry["pregunta"] for entry in entries)
    for topic in ("CLAUDE.md", "sin IA", "panel de administración", "rate limiting", "SQLAlchemy"):
        assert topic in questions
    everything = " ".join(entry["respuesta"] for entry in entries) + str(client.get("/profile").json())
    assert "/admin" not in everything and "ADMIN_TOKEN" not in everything
    assert "25 días" not in everything
    assert "Desarrollo con agentes de IA" not in str(client.get("/profile").json())
