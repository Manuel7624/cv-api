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

// Efecto de escritura: la respuesta llega a trozos (a veces casi de golpe) y se
// muestra poco a poco a un ritmo suave. Si se acumula texto pendiente, acelera,
// y cuando la respuesta ha terminado, lo que falte se reparte a ritmo constante
// en un segundo como mucho. Siempre con textContent, nunca como HTML.
const MIN_CHARS_PER_FRAME = 3; // unas 180 letras por segundo a 60 fotogramas
const CATCH_UP_FRAMES = 60; // mientras llega: alcanzar lo recibido en ~1 s
const FINISH_FRAMES = 60; // al terminar: lo que falte, en ~1 s como mucho
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function createTypewriter(element) {
  let target = ""; // todo lo recibido hasta ahora
  let shown = 0; // letras ya mostradas
  let frame = null;
  let finishing = false;
  let finishRate = 0; // letras por fotograma desde que termina la respuesta
  let onDone = null;

  function render() {
    element.classList.remove("pending");
    // Vacío tras un reinicio: se borra lo mostrado hasta que llegue el texto nuevo.
    element.textContent = target ? target.slice(0, shown) : "Un momento…";
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  function step() {
    const pending = target.length - shown;
    if (pending <= 0) {
      frame = null;
      if (finishing && onDone) onDone();
      return;
    }
    const rate = finishing
      ? finishRate
      : Math.max(MIN_CHARS_PER_FRAME, Math.ceil(pending / CATCH_UP_FRAMES));
    shown += rate;
    shown = Math.min(shown, target.length);
    render();
    frame = requestAnimationFrame(step);
  }

  function showAllNow() {
    if (frame !== null) cancelAnimationFrame(frame);
    frame = null;
    shown = target.length;
    if (target) render();
  }

  return {
    update(text) {
      // Si el texto nuevo no continúa lo mostrado, es un reinicio: se empieza de cero.
      if (!text.startsWith(target.slice(0, shown))) shown = 0;
      target = text;
      if (reduceMotion || document.hidden) return showAllNow();
      if (!target) return render();
      if (frame === null) frame = requestAnimationFrame(step);
    },
    // Termina de mostrar lo que falte; la promesa se cumple al acabar.
    finish() {
      finishing = true;
      const pending = target.length - shown;
      finishRate = Math.max(MIN_CHARS_PER_FRAME, Math.ceil(pending / FINISH_FRAMES));
      if (document.hidden || frame === null) {
        showAllNow();
        return Promise.resolve();
      }
      return new Promise((resolve) => {
        onDone = resolve;
      });
    },
    stop() {
      if (frame !== null) cancelAnimationFrame(frame);
      frame = null;
    },
  };
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

  const typewriter = createTypewriter(answer);

  try {
    const result = await requestAnswer(text, typewriter.update);
    if (result.ok) {
      await typewriter.finish();
      remember(text, result.text);
    } else {
      typewriter.stop();
    }
    // textContent: la respuesta se muestra siempre como texto, nunca como HTML.
    answer.textContent = result.text;
  } catch (error) {
    console.error(error);
    typewriter.stop();
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
