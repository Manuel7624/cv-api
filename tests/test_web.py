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
        "no escribas datos personales. Las preguntas se guardan de forma anónima 30 días "
        "para mejorar el chat."
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
    assert 'href="mailto:manusastrenar@gmail.com?subject=Contacto%20desde%20tu%20web"' in html
    assert 'href="/docs"' in html


@pytest.mark.parametrize(
    ("path", "content_type"),
    [
        ("/static/chat.js", "javascript"),
        ("/static/styles.css", "text/css"),
        ("/static/img/manuel-sastre.jpg", "image/jpeg"),
        ("/static/img/favicon.svg", "image/svg+xml"),
        ("/static/img/favicon.ico", "image/x-icon"),
        ("/static/img/apple-touch-icon.png", "image/png"),
        ("/favicon.ico", "image/x-icon"),
        ("/apple-touch-icon.png", "image/png"),
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


def test_email_buttons_offer_a_menu_with_mailto_fallback(client):
    html = client.get("/").text
    assert html.count('<div class="email-menu') == 2
    assert html.count('class="button email-link"') + html.count('class="button button-primary email-link"') == 2
    assert '<script src="/static/contact.js" defer></script>' in html
    script = client.get("/static/contact.js").text
    for text in ("Gmail", "Outlook", "Otra app de correo", "Copiar dirección", "Correo copiado"):
        assert text in script
    assert "https://mail.google.com/mail/?view=cm&fs=1&to=" in script
    assert "https://outlook.office.com/mail/deeplink/compose?to=" in script
    assert 'item.rel = "noopener"' in script
    assert '"aria-expanded"' in script and '"Escape"' in script
    assert "(pointer: coarse)" in script
    for sink in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
        assert sink not in script


def test_unfinished_answers_show_a_caret_and_are_announced_at_the_end(client):
    script = client.get("/static/chat.js").text
    assert 'classList.add("streaming")' in script
    assert script.index('classList.remove("streaming")') < script.index("announce(finalText)")
    css = client.get("/static/styles.css").text
    # El cursor va solo detrás del texto, nunca en la burbuja de los tres puntos.
    assert ".message-assistant.streaming .bubble:not(.typing)::after" in css
    assert ".message-assistant.streaming .bubble::after" not in css
    typing = css.split(".typing {")[1].split("}")[0]
    assert "align-items: center" in typing and "justify-content: center" in typing


def test_web_shows_the_ai_work_method(client):
    html = client.get("/").text
    assert (
        "La he desarrollado yo desde cero con un método de trabajo con IA: defino los "
        "requisitos y las reglas del proyecto, pido a Claude Code un plan para cada tarea "
        "que reviso y ajusto yo, la implementa por pasos pequeños y yo reviso el "
        "resultado, lo pruebo y decido qué se queda."
    ) in html
    card = html.split('aria-label="Tecnologías">')[1].split("</ul>")[0]
    assert "<li>Claude Code</li>" in card and "<li>Codex</li>" in card
    assert 'data-question="¿Cómo usas la IA para programar?"' in html
    assert "¿Cuál es tu disponibilidad?" not in html


def test_favicon_is_the_chat_bubble_with_the_ai_sparkle(client):
    svg = client.get("/static/img/favicon.svg").text
    assert '<rect width="32" height="32" rx="7" fill="#1d4ed8"/>' in svg
    assert 'fill="#fff"' in svg  # el bocadillo blanco
    assert "<text" not in svg  # ya no es la "M"


def test_every_page_links_the_icons(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "token-de-prueba-muy-largo-123")
    pages = [client.get("/").text, client.get("/admin/stats", auth=("x", "token-de-prueba-muy-largo-123")).text]
    for html in pages:
        assert '<link rel="icon" href="/static/img/favicon.svg" type="image/svg+xml">' in html
        assert '<link rel="icon" href="/static/img/favicon.ico" sizes="16x16 32x32">' in html
        assert '<link rel="apple-touch-icon" href="/static/img/apple-touch-icon.png">' in html


def test_icon_files_have_the_right_sizes(client):
    import struct

    ico = client.get("/favicon.ico").content
    reserved, kind, count = struct.unpack("<HHH", ico[:6])
    sizes = sorted(ico[6 + 16 * i] for i in range(count))
    assert (reserved, kind, sizes) == (0, 1, [16, 32])
    png = client.get("/apple-touch-icon.png").content
    assert png[1:4] == b"PNG"  # firma de un archivo PNG
    assert struct.unpack(">II", png[16:24]) == (180, 180)
    assert "/favicon.ico" not in client.get("/openapi.json").text
