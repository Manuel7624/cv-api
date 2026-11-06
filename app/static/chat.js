// Chat "Habla con mi CV". Envía cada pregunta a POST /chat: la clave de la IA
// está en el servidor, nunca aquí. Usa createElement, definida en app.js.

const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const chatSend = document.getElementById("chat-send");
const chatLog = document.getElementById("chat-log");

function addChatMessage(text, author) {
  const message = createElement("p", `chat-message ${author}`, text);
  chatLog.append(message);
  chatLog.scrollTop = chatLog.scrollHeight;
  return message;
}

async function requestAnswer(question) {
  const response = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: question }),
  });
  const data = await response.json();
  if (response.ok) return data.answer;
  if (response.status === 429) return data.detail;
  return "No he podido procesar esa pregunta. Prueba a escribirla de otra forma.";
}

async function sendQuestion(question) {
  const text = question.trim();
  if (!text || chatSend.disabled) return;

  chatSend.disabled = true;
  chatInput.value = "";
  addChatMessage(text, "user");
  const answer = addChatMessage("Pensando…", "assistant pending");

  try {
    answer.textContent = await requestAnswer(text);
  } catch (error) {
    console.error(error);
    answer.textContent =
      "No he podido conectar. Puedes escribir a Manuel desde la sección de contacto.";
  }

  answer.classList.remove("pending");
  chatLog.scrollTop = chatLog.scrollHeight;
  chatSend.disabled = false;
  chatInput.focus();
}

chatForm.addEventListener("submit", (event) => {
  event.preventDefault();
  sendQuestion(chatInput.value);
});

for (const button of document.querySelectorAll(".suggestion")) {
  button.addEventListener("click", () => sendQuestion(button.textContent));
}
