import re

import pytest

from app.chat_limits import MAX_MESSAGE_LENGTH


def test_root_serves_the_web(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert '<html lang="es">' in response.text
    assert "/static/chat.js" in response.text
    assert "/static/styles.css" in response.text


def test_page_has_the_main_parts_in_order(client):
    html = client.get("/").text
    parts = [
        "<h1>Manuel Sastre</h1>",
        "Disponibilidad inmediata",
        '<p class="role">Backend Developer</p>',
        "Pregúntame lo que quieras</h2>",
        "Resumen de mi perfil</h2>",
        "Cómo está hecha esta web</h2>",
        "¿Hablamos?</h2>",
    ]
    positions = [html.index(part) for part in parts]
    assert positions == sorted(positions)
    assert html.count("<h1") == 1


def test_chat_starts_with_the_welcome_and_the_ai_notice(client):
    html = client.get("/").text
    assert "¡Hola! Soy la IA de Manuel. Pregúntame lo que quieras sobre él." in html
    assert (
        "Respuestas generadas por IA (Google Gemini o Groq). Pueden contener errores; "
        "no escribas datos personales."
    ) in html
    assert html.count('class="suggestion"') == 4


def test_chat_log_is_accessible(client):
    html = client.get("/").text
    assert 'role="log"' in html
    assert 'id="chat-announcer" aria-live="polite"' in html
    assert 'alt="Foto de Manuel Sastre"' in html
    # Los avatares del chat son decorativos.
    assert '<img class="avatar" src="/static/img/manuel-sastre.jpg" alt=""' in html


def test_card_questions_are_buttons_that_ask_the_chat(client):
    html = client.get("/").text
    questions = re.findall(r'<button class="card-question"[^>]*aria-label="Preguntar al chat: ([^"]+)"', html)
    assert questions == [
        "¿Qué hiciste en las prácticas?",
        "¿Qué hace Balancea?",
        "¿Qué aprendiste en el grado?",
        "¿Con cuál has trabajado más?",
    ]


def test_chat_input_uses_the_backend_limit(client):
    html = client.get("/").text
    assert f'maxlength="{MAX_MESSAGE_LENGTH}"' in html
    assert '<textarea id="chat-input"' in html
    assert 'enterkeyhint="send"' in html


def test_web_explains_how_it_is_built(client):
    html = client.get("/").text
    for name in ("FastAPI", "SQLite", "PostgreSQL", "RAG", "Tests con pytest", "Gemini y Groq con respaldo"):
        assert f"<li>{name}</li>" in html


def test_page_has_no_inline_styles_or_scripts(client):
    """La CSP solo permite estilos y scripts de archivos de esta web."""
    html = client.get("/").text
    assert "style=" not in html
    assert "<style" not in html
    assert re.findall(r"<script(?![^>]* src=)", html) == []
    assert "fonts.googleapis.com" not in html


def test_share_preview_tags(client):
    html = client.get("/", headers={"x-forwarded-proto": "https", "host": "cv.example.com"}).text
    assert '<meta property="og:title" content="Manuel Sastre · Backend Developer">' in html
    assert '<meta property="og:image" content="https://cv.example.com/static/img/og-image.png">' in html
    assert '<meta name="twitter:card" content="summary_large_image">' in html
    assert "{{" not in html


def test_share_image_url_ignores_a_strange_host(client):
    html = client.get("/", headers={"host": 'x"><script>'}).text
    assert '<meta property="og:image" content="/static/img/og-image.png">' in html


def test_scripts_never_insert_html(client):
    """Los datos y las respuestas del chat se pintan siempre como texto."""
    script = client.get("/static/chat.js").text
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
    assert '"Escribiendo"' in script
    assert ".typing" in client.get("/static/styles.css").text


def test_web_links_to_cv_github_and_docs(client):
    html = client.get("/").text
    assert 'href="/static/Manuel_Sastre_CV.pdf"' in html
    assert 'href="https://github.com/Manuel7624"' in html
    assert 'href="https://github.com/Manuel7624/Curriculum-Avanzado"' in html
    assert 'href="https://www.linkedin.com/in/manuel-sastre-naranjo"' in html
    assert 'href="mailto:manusastrenar@gmail.com"' in html
    assert 'href="/docs"' in html


@pytest.mark.parametrize(
    ("path", "content_type"),
    [
        ("/static/chat.js", "javascript"),
        ("/static/styles.css", "text/css"),
        ("/static/img/manuel-sastre.jpg", "image/jpeg"),
        ("/static/img/favicon.svg", "image/svg+xml"),
        ("/static/img/og-image.png", "image/png"),
        ("/static/fonts/plus-jakarta-sans-latin.woff2", "font/woff2"),
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


def test_chat_types_the_answer_as_text(client):
    script = client.get("/static/chat.js").text
    assert "createTypewriter" in script
    assert "prefers-reduced-motion" in script
    assert "innerHTML" not in script and "insertAdjacentHTML" not in script
