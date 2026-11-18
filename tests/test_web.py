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
    assert re.search(r'<img class="avatar" src="/static/img/manuel-sastre.jpg\?v=[0-9a-f]{10}" alt=""', html)


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
    assert re.search(r'<meta property="og:image" content="https://cv.example.com/static/img/og-image.png\?v=[0-9a-f]{10}">', html)
    assert '<meta name="twitter:card" content="summary_large_image">' in html
    assert "{{" not in html


def test_share_image_url_ignores_a_strange_host(client):
    html = client.get("/", headers={"host": 'x"><script>'}).text
    assert re.search(r'<meta property="og:image" content="/static/img/og-image.png\?v=[0-9a-f]{10}">', html)


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
    assert re.search(r'href="/static/Manuel_Sastre_CV.pdf\?v=[0-9a-f]{10}"', html)
    assert 'href="https://github.com/Manuel7624"' in html
    assert 'href="https://github.com/Manuel7624/cv-api"' in html
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
    assert re.search(r'<script src="/static/contact.js\?v=[0-9a-f]{10}" defer></script>', html)
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
        assert re.search(r'<link rel="icon" href="/static/img/favicon.svg\?v=[0-9a-f]{10}" type="image/svg\+xml">', html)
        assert re.search(r'<link rel="icon" href="/static/img/favicon.ico\?v=[0-9a-f]{10}" sizes="16x16 32x32">', html)
        assert re.search(r'<link rel="apple-touch-icon" href="/static/img/apple-touch-icon.png\?v=[0-9a-f]{10}">', html)


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


# --- Versiones en las URLs y caché ---


def static_references(html):
    return re.findall(r'(?:href|src|content)="(?:https?://[^/"]+)?(/static/[^"]+)"', html)


def test_every_static_file_has_a_content_version_except_fonts(client):
    import hashlib
    from pathlib import Path

    static = Path(__file__).parent.parent / "app" / "static"
    references = static_references(client.get("/").text)
    assert len(references) >= 10
    for url in references:
        path, _, query = url.removeprefix("/static/").partition("?")
        if path.startswith("fonts/"):
            assert query == "", url  # el CSS la pide sin versión: así coinciden
            continue
        expected = hashlib.sha256((static / path).read_bytes()).hexdigest()[:10]
        assert query == f"v={expected}", url
        assert client.get(url).status_code == 200


def test_font_preload_matches_the_css(client):
    html = client.get("/").text
    css = client.get("/static/styles.css").text
    assert 'href="/static/fonts/plus-jakarta-sans-latin.woff2"' in html
    assert 'url("/static/fonts/plus-jakarta-sans-latin.woff2")' in css


def test_the_version_changes_when_the_file_changes(tmp_path):
    from app.static_files import add_versions, file_version

    (tmp_path / "styles.css").write_text("body { color: red; }", encoding="utf-8")
    first = add_versions('<link href="/static/styles.css">', tmp_path)
    file_version.cache_clear()
    (tmp_path / "styles.css").write_text("body { color: blue; }", encoding="utf-8")
    second = add_versions('<link href="/static/styles.css">', tmp_path)
    file_version.cache_clear()
    assert first != second
    assert re.fullmatch(r'<link href="/static/styles.css\?v=[0-9a-f]{10}">', second)
    # Un archivo que no existe se deja como está.
    assert add_versions('<img src="/static/no-existe.png">', tmp_path) == '<img src="/static/no-existe.png">'


def test_html_is_never_cached(client, monkeypatch):
    assert client.get("/").headers["Cache-Control"] == "no-store"
    monkeypatch.setenv("ADMIN_TOKEN", "token-de-prueba-muy-largo-123")
    page = client.get("/admin/stats", auth=("x", "token-de-prueba-muy-largo-123"))
    assert page.headers["Cache-Control"] == "no-store"
    assert static_references(page.text)
    for url in static_references(page.text):
        assert "?v=" in url


def test_versioned_static_files_are_cached_for_a_year(client):
    url = next(u for u in static_references(client.get("/").text) if u.startswith("/static/styles.css"))
    response = client.get(url)
    assert response.headers["Cache-Control"] == "public, max-age=31536000, immutable"


def test_unversioned_static_files_are_revalidated(client):
    for path in ("/static/styles.css", "/static/fonts/plus-jakarta-sans-latin.woff2", "/favicon.ico"):
        assert client.get(path).headers["Cache-Control"] == "no-cache"
    # Un 404 no se marca como guardable.
    assert client.get("/static/no-existe.css?v=123").headers.get("Cache-Control") != "public, max-age=31536000, immutable"


def test_chat_avatar_uses_the_versioned_url_from_the_page(client):
    script = client.get("/static/chat.js").text
    assert "/static/img/manuel-sastre.jpg" not in script
    assert 'document.querySelector(".message-assistant .avatar").getAttribute("src")' in script


def test_copy_address_only_changes_the_option_text(client):
    script = client.get("/static/contact.js").text
    assert '"✓ Correo copiado"' in script
    assert "COPIED_SECONDS = 2" in script
    # El aviso para lectores de pantalla existe, pero oculto a la vista.
    assert 'status.className = "visually-hidden"' in script
    assert 'status.setAttribute("role", "status")' in script
    assert ".email-status" not in client.get("/static/styles.css").text


def test_mobile_chat_is_shorter_and_does_not_trap_the_scroll(client):
    css = client.get("/static/styles.css").text
    mobile = css.split("@media (max-width: 600px) {")[1]
    log = mobile.split(".chat-log {")[1].split("}")[0]
    # Alto de reserva con vh y, detrás, dvh; y el scroll pasa a la página al llegar al límite.
    assert log.index("max-height: 55vh") < log.index("max-height: 55dvh")
    assert "overscroll-behavior-y: auto" in log
    assert "contain" not in log


def test_desktop_chat_log_is_unchanged(client):
    css = client.get("/static/styles.css").text
    base = css.split(".chat-log {")[1].split("}")[0]
    assert "max-height: 520px" in base
    assert "overscroll-behavior: contain" in base
    assert "padding: 18px 22px" in base


def test_on_narrow_screens_the_answer_is_placed_at_its_start(client):
    script = client.get("/static/chat.js").text.replace("\r\n", "\n")  # finales de línea de Windows
    assert 'window.matchMedia("(max-width: 600px)")' in script
    assert "function anchorToAnswer()" in script
    # Solo mueve el scroll interno del chat, nunca la página.
    anchor = script.split("function anchorToAnswer()")[1].split("\n}\n")[0]
    assert "chatLog.scrollTop" in anchor and "scrollIntoView" not in anchor and "window.scroll" not in anchor
    # En pantallas estrechas con una respuesta en curso, no baja al final del texto.
    latest = script.split("function scrollToLatest")[1].split("\n}\n")[0]
    assert latest.index("narrowScreen.matches && answerAnchor") < latest.index("chatLog.scrollTop = chatLog.scrollHeight")
    # Se suelta al empezar otra pregunta, al terminar la respuesta y si el usuario mueve el chat.
    assert script.count("answerAnchor = null") >= 3


def test_mobile_ai_notice_is_smaller_and_desktop_is_unchanged(client):
    css = client.get("/static/styles.css").text
    # Escritorio: el aviso sigue igual.
    base = css.split(".chat-note {")[1].split("}")[0]
    assert "margin: 10px 4px 0" in base and "font-size: 12px" in base and "line-height: 1.5" in base
    # Móvil: letra más pequeña, menos altura y botón del CV más cerca del aviso.
    mobile = css.split("@media (max-width: 600px) {")[1]
    note = mobile.split(".chat-note {")[1].split("}")[0]
    assert "font-size: 11px" in note and "line-height: 1.35" in note and "margin: 8px 2px 0" in note
    links = mobile.split(".links {")[1].split("}")[0]
    assert "margin-top: -4px" in links
