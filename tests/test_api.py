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
    assert client.get("/profile").json()["summary"].endswith("seguir creciendo en Python.")
    internship = client.get("/experience").json()[0]
    assert internship["period"] == "26 de enero – 15 de mayo de 2026"
    assert "Apoyo de Codex" in internship["highlights"][0]
    assert "comprobación mediante pruebas" in internship["highlights"][0]
    assert "Codex" in client.get("/skills").json()["tools"]


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
    assert client.get("/projects").json()[0]["technologies"][0] == "Java"
    assert client.get("/education").json()[-1]["title"] == "Bachillerato de Ciencias"
    assert client.get("/skills").json()["tools"][0] == "Docker"
