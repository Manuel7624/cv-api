import re

import pytest

from app.chat_limits import MAX_MESSAGE_LENGTH


def test_root_serves_the_web(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "/static/app.js" in response.text
    assert "/static/styles.css" in response.text


def test_chat_comes_before_the_cv(client):
    html = client.get("/").text
    assert "Pregúntame lo que quieras sobre Manuel" in html
    assert html.index('id="chat-form"') < html.index('id="experience"')


def test_chat_input_uses_the_backend_limit(client):
    assert f'maxlength="{MAX_MESSAGE_LENGTH}"' in client.get("/").text


def test_web_explains_how_it_is_built(client):
    html = client.get("/").text
    assert "Cómo está hecha esta web" in html
    for name in ("Navegador", "FastAPI", "SQLite", "Docker", "pytest"):
        assert name in html


def test_terminal_only_offers_real_get_routes(client):
    html = client.get("/").text
    routes = re.findall(r'<option value="([^"]+)"', html)
    assert routes
    for route in routes:
        assert client.get(route).status_code == 200


@pytest.mark.parametrize("path", ["/static/app.js", "/static/chat.js", "/static/terminal.js"])
def test_scripts_never_insert_html(client, path):
    """Los datos y las respuestas del chat se pintan siempre como texto."""
    script = client.get(path).text
    for sink in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
        assert sink not in script


def test_security_headers(client):
    headers = client.get("/").headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in headers["Content-Security-Policy"]
    assert "Content-Security-Policy" in client.get("/profile").headers


def test_docs_keep_working_without_csp(client):
    response = client.get("/docs")
    assert response.status_code == 200
    assert "Content-Security-Policy" not in response.headers


def test_chat_shows_a_typing_indicator(client):
    script = client.get("/static/chat.js").text
    assert "addTypingIndicator" in script
    assert '"Escribiendo"' in script
    assert ".typing-dots" in client.get("/static/styles.css").text


def test_web_has_contact_section(client):
    assert 'id="contact"' in client.get("/").text
    assert "renderContact" in client.get("/static/app.js").text


def test_web_links_to_cv_github_and_docs(client):
    html = client.get("/").text
    assert 'href="/static/Manuel_Sastre_CV.pdf"' in html
    assert 'href="https://github.com/Manuel7624"' in html
    assert 'href="/docs"' in html


@pytest.mark.parametrize(
    ("path", "content_type"),
    [
        ("/static/app.js", "javascript"),
        ("/static/chat.js", "javascript"),
        ("/static/terminal.js", "javascript"),
        ("/static/styles.css", "text/css"),
        ("/static/img/manuel-sastre.jpg", "image/jpeg"),
    ],
)
def test_static_files_are_served(client, path, content_type):
    response = client.get(path)
    assert response.status_code == 200
    assert content_type in response.headers["content-type"]


def test_cv_pdf_is_served(client):
    response = client.get("/static/Manuel_Sastre_CV.pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_static_does_not_expose_app_code(client):
    assert client.get("/static/%2e%2e/main.py").status_code == 404


def test_api_docs_still_work(client):
    assert client.get("/docs").status_code == 200
    assert "/profile" in client.get("/openapi.json").json()["paths"]
