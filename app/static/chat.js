// Chat "Habla con mi CV". Envía cada pregunta a POST /chat/stream: la clave de la
// IA está en el servidor, nunca aquí. La respuesta llega a trozos y se va
// mostrando según se genera. Usa createElement, definida en app.js.

const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const chatSend = document.getElementById("chat-send");
const chatLog = document.getElementById("chat-log");

// Últimos mensajes de la conversación. Solo viven en esta página: el servidor
// no guarda nada, así que al recargar la conversación empieza de cero.
const MAX_HISTORY_MESSAGES = 6;
const chatHistory = [];

function addChatMessage(text, author) {
  const message = createElement("p", `chat-message ${author}`, text);
  chatLog.append(message);
  chatLog.scrollTop = chatLog.scrollHeight;
  return message;
}

// Burbuja con puntos animados mientras llega la respuesta.
function addTypingIndicator() {
  const message = createElement("p", "chat-message assistant pending");
  const dots = createElement("span", "typing-dots");
  dots.setAttribute("aria-hidden", "true");
  dots.append(createElement("span"), createElement("span"), createElement("span"));
  message.append("Escribiendo", dots);
  chatLog.append(message);
  chatLog.scrollTop = chatLog.scrollHeight;
  return message;
}

const ERROR_TEXT = "No he podido procesar esa pregunta. Prueba a escribirla de otra forma.";

// Pide la respuesta y llama a onText(textoHastaAhora) cada vez que llega un trozo.
// El servidor envía líneas "data: {json}" separadas por una línea en blanco.
async function requestAnswer(question, onText) {
  const response = await fetch("/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: question, history: chatHistory }),
  });
  if (response.status === 429) return { ok: false, text: (await response.json()).detail };
  if (!response.ok) return { ok: false, text: ERROR_TEXT };

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let pending = "";
  let text = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    pending += value;
    const events = pending.split("\n\n");
    pending = events.pop(); // el último puede estar incompleto
    for (const event of events) {
      if (!event.startsWith("data: ")) continue;
      const data = JSON.parse(event.slice(6));
      text = data.restart ? "" : text + data.text;
      onText(text);
    }
  }
  text = text.trim();
  return text ? { ok: true, text } : { ok: false, text: ERROR_TEXT };
}

function remember(question, answer) {
  chatHistory.push(
    { role: "user", content: question },
    { role: "assistant", content: answer },
  );
  chatHistory.splice(0, Math.max(0, chatHistory.length - MAX_HISTORY_MESSAGES));
}

async function sendQuestion(question) {
  const text = question.trim();
  if (!text || chatSend.disabled) return;

  chatSend.disabled = true;
  chatInput.value = "";
  addChatMessage(text, "user");
  const answer = addTypingIndicator();

  // textContent: la respuesta se muestra siempre como texto, nunca como HTML.
  const show = (partial) => {
    // Vacío tras un reinicio: se borra lo mostrado hasta que llegue el texto nuevo.
    answer.classList.remove("pending");
    answer.textContent = partial || "Un momento…";
    chatLog.scrollTop = chatLog.scrollHeight;
  };

  try {
    const result = await requestAnswer(text, show);
    answer.textContent = result.text;
    if (result.ok) remember(text, result.text);
  } catch (error) {
    console.error(error);
    answer.textContent =
      "No he podido conectar. Puedes escribirme desde la sección de contacto.";
  }

  answer.classList.remove("pending");
  // Lleva al inicio de la respuesta, para que se lea desde el principio.
  chatLog.scrollTop = answer.offsetTop - chatLog.offsetTop;
  chatSend.disabled = false;
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await sendQuestion(chatInput.value);
  chatInput.focus();
});

for (const button of document.querySelectorAll(".suggestion")) {
  button.addEventListener("click", () => sendQuestion(button.textContent));
}
