// Aviso legal bajo el chat: "Más info" muestra u oculta el texto completo.
// Es un botón de verdad (Intro y Espacio funcionan solos) que avisa a los lectores
// de pantalla de si el texto está desplegado (aria-expanded).
const noticeToggle = document.getElementById("chat-note-toggle");
const noticeText = document.getElementById("chat-note-text");

if (noticeToggle && noticeText) {
  noticeToggle.addEventListener("click", () => {
    const wasOpen = noticeToggle.getAttribute("aria-expanded") === "true";
    noticeToggle.setAttribute("aria-expanded", String(!wasOpen));
    noticeText.hidden = wasOpen;
  });
}
