"""Aspecto de la web: iconos, tarjetas, "cómo está hecha", pie y estilos del chat.
Solo comprueba el HTML y el CSS que sirve la app; nunca llama a ninguna IA."""
import re

LINKEDIN = "https://www.linkedin.com/in/manuel-sastre-naranjo"
GITHUB = "https://github.com/Manuel7624"


def css_block(css, selector):
    """El contenido del primer bloque que empieza por `selector {`."""
    return css.split(selector + " {")[1].split("}")[0]


# --- Iconos ----------------------------------------------------------------------


def test_every_svg_icon_is_decorative_and_made_of_strokes(client):
    html = client.get("/").text
    svgs = re.findall(r"<svg[^>]*>", html)
    assert len(svgs) == 12  # 4 de la cabecera, 4 de las tarjetas, 2 botones, descarga y correo
    assert all('aria-hidden="true"' in svg for svg in svgs)
    # Iconos de trazo: ninguno rellena formas con color propio.
    assert "fill=\"currentColor\"" not in html and "icon-brand" not in html
    css = client.get("/static/styles.css").text
    icon = css_block(css, ".icon")
    assert "fill: none" in icon and "stroke: currentColor" in icon


def test_header_buttons_have_a_small_icon_before_the_text(client):
    html = client.get("/").text
    nav = html.split('<nav class="links"')[1].split("</nav>")[0]
    # Cada botón empieza por su icono y después va el texto.
    texts = re.findall(r'<svg class="icon"[^>]*>.*?</svg>\s*(?:<span class="text-long">)?([^<]+)', nav, re.S)
    assert [t.strip() for t in texts] == ["Descargar CV (PDF)", "Enviar un correo", "LinkedIn", "GitHub"]
    assert nav.count("<svg") == 4
    css = client.get("/static/styles.css").text
    assert "width: 15px" in css_block(css, ".links .icon") and "height: 15px" in css_block(css, ".links .icon")


# --- Chat ------------------------------------------------------------------------


def test_chat_styles(client):
    css = client.get("/static/styles.css").text
    assert "font-size: 30px" in css_block(css, ".chat h2")
    assert "width: 34px" in css_block(css, ".avatar") and "height: 34px" in css_block(css, ".avatar")
    suggestion = css_block(css, ".suggestion")
    assert "color: #1e40af" in suggestion and "background: #f6f9ff" in suggestion and "border: 1px solid #bfd0f7" in suggestion
    assert "rgba(29, 78, 216" in css_block(css, ".chat-card")  # sombra azulada
    focus = css_block(css, "#chat-input:focus-visible")
    assert "border-color: var(--blue)" in focus and "box-shadow: 0 0 0 4px" in focus
    mobile = css.split("@media (max-width: 600px) {")[1]
    # El título cabe en una línea en móvil: baja hasta 22 px como mínimo y sube hasta 25 px.
    assert "clamp(22px" in css_block(mobile, "  .chat h2") and ", 25px)" in css_block(mobile, "  .chat h2")


def test_chat_has_no_online_label_and_a_34px_welcome_avatar(client):
    html = client.get("/").text
    assert 'alt="" width="34" height="34"' in html
    assert "en línea" not in html.lower()


# --- Resumen ----------------------------------------------------------------------


def test_summary_cards_have_an_icon_label_and_a_short_one_line_footer(client):
    html = client.get("/").text
    cards = html.split('<div class="cards">')[1].split("</div>\n      <a class=\"button-soft download-full\"")[0]
    labels = re.findall(r'<span class="card-label"><svg class="icon icon-small icon-accent"[^>]*>.*?</svg>([^<]+)</span>', cards)
    assert labels == ["Experiencia", "Proyectos", "Formación", "Tecnologías"]
    footers = re.findall(r'<button class="card-question" type="button" data-question="([^"]+)" aria-label="Preguntar al chat: ([^"]+)">\s*<span>([^<]+)</span><span class="card-arrow" aria-hidden="true">→</span>', cards)
    assert [(question, label, short) for question, label, short in footers] == [
        ("¿Qué hiciste en las prácticas?", "¿Qué hiciste en las prácticas?", "¿Qué hiciste?"),
        ("¿Qué hace Balancea?", "¿Qué hace Balancea?", "¿Qué es Balancea?"),
        ("¿Qué aprendiste en el grado?", "¿Qué aprendiste en el grado?", "¿Qué aprendiste?"),
        ("¿Con cuál has trabajado más?", "¿Con cuál has trabajado más?", "¿Cuál usas más?"),
    ]  # lo que se ve es corto; al chat va la pregunta de siempre


def test_card_footer_is_one_line_and_the_same_height(client):
    css = client.get("/static/styles.css").text
    footer = css_block(css, ".card-question")
    assert "white-space: nowrap" in footer and "height: 46px" in footer
    assert "color: #4b5563" in css_block(css, ".card-label")
    # Los tres títulos de apartado (resumen, cómo está hecha y contacto) miden lo mismo: 20 px.
    assert "font-size: 20px" in css_block(css, ".section h2") and "font-size: 20px" in css_block(css, ".section-contact h2")
    assert "font-size" not in css_block(css, ".section-how")
    assert "padding-top: 19px" in css_block(css, ".section-summary")  # escritorio: 32 px desde la línea del aviso
    assert "padding-top: 22px" in css_block(css.split("@media (max-width: 600px) {")[1], "  .section-summary")  # móvil


def test_clicking_a_card_sends_the_original_question():
    """chat.js manda el data-question del botón (la pregunta completa), no su texto."""
    import pathlib

    script = (pathlib.Path(__file__).resolve().parent.parent / "app/static/chat.js").read_text(encoding="utf-8")
    assert "dataset.question" in script
    assert "button.textContent" not in script and "button.innerText" not in script


def test_full_cv_download_is_a_button_26px_under_the_cards(client):
    html = client.get("/").text
    button = html.split('class="button-soft download-full"')[1].split("</a>")[0]
    assert "<svg" in button and "Descargar CV completo" in button and 'href="/static/Manuel_Sastre_CV.pdf' in html
    css = client.get("/static/styles.css").text
    assert "margin-top: 12px" in css_block(css, ".download-full")  # + 14 px de la rejilla = 26 px


# --- Cómo está hecha esta web ------------------------------------------------------


def test_how_it_is_made_has_three_numbered_steps_chips_and_two_equal_buttons(client):
    html = client.get("/").text
    how = html.split('aria-labelledby="how-heading"')[1].split('<section class="section section-contact"')[0]
    assert re.findall(r'<span class="how-number" aria-hidden="true">(\d)</span>\s*<h3>([^<]+)</h3>', how) == [
        ("1", "Método de trabajo con IA"),
        ("2", "Cómo responde el chat"),
        ("3", "Fiable y probada"),
    ]
    assert "Es una API con Python y FastAPI. El chat busca primero mis datos relacionados con tu pregunta y responde solo con ellos, para no inventarse nada." in how
    assert "Si un proveedor de IA falla, pasa a otro automáticamente. Funciona en Docker y está comprobada con tests automáticos." in how
    assert how.count('<li class="how-step">') == 3 and how.count("<li>") == 8  # 3 pasos y las 8 etiquetas de siempre
    assert how.index('class="tags"') < how.index('class="how-actions"')
    actions = how.split('<div class="how-actions">')[1]
    buttons = re.findall(r'<a class="button button-primary" href="([^"]+)"[^>]*>\s*<svg[^>]*aria-hidden="true">.*?</svg>\s*([^<]+?)\s*</a>', actions, re.S)
    assert buttons == [("/docs", "Probar la API en vivo"), ("https://github.com/Manuel7624/cv-api", "Ver el código en GitHub")]
    assert "La he desarrollado yo desde cero" not in html  # el párrafo largo ya no está


def test_how_it_is_made_layout(client):
    css = client.get("/static/styles.css").text
    assert "repeat(3, minmax(0, 1fr))" in css_block(css, ".how-steps")
    actions = css_block(css, ".how-actions")
    assert "flex-wrap: wrap" in actions and "justify-content: center" in actions and "gap: 14px 40px" in actions
    assert "border-top: 1px solid" in actions
    assert "flex: 0 0 auto" in css_block(css, ".how-actions .button")  # no se encogen
    assert "padding-top: 44px" in css_block(css, ".section-how")
    # En móvil, una columna.
    assert "grid-template-columns: 1fr" in css.split("@media (max-width: 600px) {")[1]
    assert "grid-template-columns: 1fr" in css.split("@media (max-width: 760px) {")[1]
    assert "background: var(--blue)" in css.split(".button-primary,")[1].split("}")[0]  # azul sólido #1d4ed8


# --- Pie de página -------------------------------------------------------------------


def test_footer_has_the_copyright_and_the_same_links_as_the_header(client):
    html = client.get("/").text
    footer = html.split('<footer class="site-footer">')[1].split("</footer>")[0]
    assert "© 2026 Manuel Sastre · Hecho con Python y FastAPI" in footer
    links = re.findall(r'<a href="([^"]+)" target="_blank" rel="noopener">([^<]+)</a>', footer)
    assert links == [(LINKEDIN, "LinkedIn"), (GITHUB, "GitHub")]
    header = html.split('<nav class="links"')[1].split("</nav>")[0]
    assert LINKEDIN in header and GITHUB in header
    assert html.index("</main>") < html.index('<footer class="site-footer">')


def test_footer_is_stacked_on_mobile_and_aligned_with_the_content(client):
    css = client.get("/static/styles.css").text
    assert "max-width: 1000px" in css_block(css, ".site-footer-inner")  # como el contenido de .page
    assert "justify-content: space-between" in css_block(css, ".site-footer-inner")
    mobile = css.split("@media (max-width: 600px) {")[1]
    assert "flex-direction: column" in css_block(mobile, "  .site-footer-inner")
    assert "min-height: 44px" in css_block(css, ".footer-links a")


def test_footer_text_has_enough_contrast():
    def luminance(color):
        channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        channels = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]

    def contrast(a, b):
        high, low = sorted((luminance(a), luminance(b)), reverse=True)
        return (high + 0.05) / (low + 0.05)

    pairs = [("#4b5563", "#f6f7f9"), ("#4b5563", "#ffffff"), ("#1e40af", "#f6f9ff"),
             ("#1d4ed8", "#e8efff"), ("#ffffff", "#1d4ed8"), ("#1d4ed8", "#f6f7f9")]
    assert all(contrast(*pair) >= 4.5 for pair in pairs)


# --- Aviso legal bajo la tarjeta -------------------------------------------------

FULL_NOTICE = (
    "Respuestas generadas por IA (Google Gemini o Groq). Pueden contener errores; no escribas "
    "datos personales. Las preguntas se guardan de forma anónima 30 días para mejorar el chat."
)


def test_notice_is_plain_text_plus_one_button_right_below_the_card(client):
    html = client.get("/").text
    section = html.split('<section class="chat" id="chat"')[1].split("</section>")[0]
    section = re.sub(r"<!--.*?-->", "", section, flags=re.S)  # sin los comentarios
    card, note = section.split('<div class="chat-note">')
    assert card.rstrip().endswith("</div>")  # la tarjeta ya está cerrada antes del aviso
    assert "chat-note" not in card and "<details" not in html and "<summary" not in html
    line = note.split('<p class="chat-note-line">')[1].split("</p>")[0]
    # Solo "Más info" es un control; el resto de la línea es texto normal.
    assert len(re.findall(r"<button", line)) == 1 and "<a " not in line
    assert re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", line)).strip() == "Respuestas generadas por IA · pueden contener errores · Más info"
    assert '<span class="chat-note-label">' in line  # el texto va en un solo bloque: los espacios no se pierden
    button = re.search(r"<button([^>]*)>([^<]*)</button>", line)
    assert button.group(2) == "Más info"
    attrs = button.group(1)
    assert 'type="button"' in attrs and 'aria-expanded="false"' in attrs and 'aria-controls="chat-note-text"' in attrs
    # El texto completo está oculto al empezar y lo controla el botón.
    assert f'<p class="chat-note-text" id="chat-note-text" hidden>{FULL_NOTICE}</p>' in note


def test_notice_script_toggles_the_button_and_the_text(client):
    html = client.get("/").text
    assert re.search(r'<script src="/static/notice.js\?v=[0-9a-f]{10}" defer></script>', html)
    script = client.get("/static/notice.js").text
    assert 'getElementById("chat-note-toggle")' in script and 'getElementById("chat-note-text")' in script
    assert "aria-expanded" in script and "noticeText.hidden" in script
    # El chat y el menú del correo no se tocan.
    assert "chat-note" not in client.get("/static/chat.js").text + client.get("/static/contact.js").text


def test_only_the_more_info_button_is_pressable_with_a_44px_target(client):
    css = client.get("/static/styles.css").text
    line = css_block(css, ".chat-note-line")
    assert "display: flex" in line and "min-height: 44px" in line and "cursor" not in line  # texto normal, sin mano
    assert "cursor" not in css_block(css, ".chat-note") and "cursor" not in css_block(css, ".chat-note-text")
    more = css_block(css, ".chat-note-more")
    assert "min-width: 44px" in more and "min-height: 44px" in more and "cursor: pointer" in more
    assert "flex: 0 0 auto" in more  # no se estira por toda la línea
    assert "color: var(--blue)" in more and "text-decoration: underline" in more
    assert "background: none" in more and "border: 0" in more
    assert "outline-offset: 0" in css_block(css, ".chat-note-more:focus-visible")  # el aro no tapa el punto de antes
    assert "margin-left: 4px" in more
    # Fuera de la tarjeta (que tiene overflow oculto) el aro de foco de la zona táctil se ve entero.
    assert "overflow" not in css_block(css, ".chat")
    assert "padding: 6px 0 12px" in css_block(css, ".chat-note-text")  # el aro no tapa el texto desplegado
    mobile = css.split("@media (max-width: 600px) {")[1]
    assert "font-size: 11.5px" in css_block(mobile, "  .chat-note")


def test_notice_line_is_shortened_on_narrow_screens_only(client):
    css = client.get("/static/styles.css").text
    narrow = css.split("@media (max-width: 440px) {")[1]
    assert "display: none" in css_block(narrow, "  .chat-note-extra")
    assert "display: none" not in css_block(css, ".chat-note")  # en el texto completo sigue todo


def test_bot_avatar_is_at_the_bottom_of_the_bubble_on_mobile_and_desktop(client):
    css = client.get("/static/styles.css").text
    assert "align-items: flex-end" in css_block(css, ".message")
    # Ninguna regla de móvil lo cambia: abajo en todos los anchos.
    mobile = css.split("@media (max-width: 600px) {")[1]
    assert "  .message {" not in mobile and "  .message-assistant {" not in mobile and "  .avatar {" not in mobile
    # El avatar sigue siendo un círculo de 34 px que no se estira ni se deforma.
    avatar = css_block(css, ".avatar")
    assert "width: 34px" in avatar and "height: 34px" in avatar and "border-radius: 50%" in avatar
    assert "object-fit: cover" in avatar and "flex: 0 0 auto" in avatar
