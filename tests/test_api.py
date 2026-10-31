from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_profile():
    response = client.get("/profile")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Manuel Sastre"
    assert "github" in body["contact"]


def test_profile_does_not_expose_phone():
    """El teléfono no debe aparecer en una API pública."""
    assert "phone" not in client.get("/profile").json()["contact"]


def test_experience_is_not_empty():
    response = client.get("/experience")
    assert response.status_code == 200
    assert len(response.json()) >= 1


def test_projects_include_balancea():
    names = [p["name"] for p in client.get("/projects").json()]
    assert "Balancea" in names


def test_education_and_skills():
    assert client.get("/education").status_code == 200
    assert "languages" in client.get("/skills").json()
