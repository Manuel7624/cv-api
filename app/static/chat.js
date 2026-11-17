// Chat "Pregúntame lo que quieras". Envía cada pregunta a POST /chat/stream: la
// clave de la IA está en el servidor, nunca aquí. La respuesta llega a trozos y
// se va mostrando según se genera, siempre con textContent (nunca como HTML),
// para que ningún texto pueda inyectar código en la página.

const chatSection = document.getElementById("chat");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const chatSend = document.getElementById("chat-send");
const chatLog = document.getElementById("chat-log");
const chatAnnouncer = document.getElementById("chat-announcer");

const AVATAR_SRC = "/static/img/manuel-sastre.jpg";
const ERROR_TEXT = "No he podido procesar esa pregunta. Prueba a escribirla de otra forma.";
const CONNECTION_ERROR_TEXT =
  "No he podido conectar. Puedes escribirme desde la sección de contacto.";
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// Últimos mensajes de la conversación. Solo viven en esta página: el servidor
// no guarda nada, así que al recargar la conversación empieza de cero.
const MAX_HISTORY_MESSAGES = 6;
const chatHistory = [];
let waitingAnswer = false;

function createElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

// --- Scroll del área de mensajes ---

// Baja sola al último mensaje, salvo que el usuario haya subido a leer algo.
let followLatest = true;

chatLog.addEventListener("scroll", () => {
  const distanceToBottom = chatLog.scrollHeight - chatLog.scrollTop - chatLog.clientHeight;
  followLatest = distanceToBottom < 40;
});

function scrollToLatest(force = false) {
  if (force) followLatest = true;
  if (followLatest) chatLog.scrollTop = chatLog.scrollHeight;
}

// --- Mensajes ---

function addUserMessage(text) {
  const message = createElement("div", "message message-user");
  message.append(createElement("p", "bubble", text));
  chatLog.append(message);
  scrollToLatest(true);
}

function createTypingDots() {
  const dots = createElement("div", "bubble typing");
  dots.setAttribute("role", "img");
  dots.setAttribute("aria-label", "Escribiendo");
  dots.append(createElement("span"), createElement("span"), createElement("span"));
  return dots;
}

// Mensaje de la IA: avatar decorativo (alt="") y, de momento, los tres puntos.
function addAssistantMessage() {
  const message = createElement("div", "message message-assistant");
  const avatar = createElement("img", "avatar");
  avatar.src = AVATAR_SRC;
  avatar.alt = "";
  avatar.width = 32;
  avatar.height = 32;
  const dots = createTypingDots();
  message.append(avatar, dots);
  chatLog.append(message);
  scrollToLatest();

  const bubble = createElement("p", "bubble");
  return {
    message,
    // Muestra texto en lugar de los puntos (o los puntos otra vez, si está vacío).
    setText(text) {
      if (!text) {
        if (bubble.isConnected) bubble.replaceWith(dots);
        return;
      }
      if (!bubble.isConnected) dots.replaceWith(bubble);
      // Sin los espacios del final, para que el cursor quede pegado a la última
      // palabra mientras llega la respuesta (la respuesta final ya llega sin ellos).
      bubble.textContent = text.trimEnd();
      scrollToLatest();
    },
  };
}

// La respuesta se anuncia entera al terminar, no palabra a palabra.
function announce(text) {
  chatAnnouncer.textContent = "";
  window.setTimeout(() => {
    chatAnnouncer.textContent = text;
  }, 50);
}

// --- Petición al servidor ---

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

// --- Efecto de escritura ---

// La respuesta llega a trozos (a veces casi de golpe) y se muestra poco a poco a
// un ritmo suave. Si se acumula texto pendiente, acelera, y cuando la respuesta ha
// terminado, lo que falte se reparte a ritmo constante en un segundo como mucho.
const MIN_CHARS_PER_FRAME = 3; // unas 180 letras por segundo a 60 fotogramas
const CATCH_UP_FRAMES = 60; // mientras llega: alcanzar lo recibido en ~1 s
const FINISH_FRAMES = 60; // al terminar: lo que falte, en ~1 s como mucho

function createTypewriter(answer) {
  let target = ""; // todo lo recibido hasta ahora
  let shown = 0; // letras ya mostradas
  let frame = null;
  let finishing = false;
  let finishRate = 0; // letras por fotograma desde que termina la respuesta
  let onDone = null;

  // Vacío tras un reinicio: vuelven los tres puntos hasta que llegue el texto nuevo.
  const render = () => answer.setText(target.slice(0, shown));

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
    shown = Math.min(shown + rate, target.length);
    render();
    frame = requestAnimationFrame(step);
  }

  function showAllNow() {
    if (frame !== null) cancelAnimationFrame(frame);
    frame = null;
    shown = target.length;
    render();
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

// --- Enviar una pregunta ---

async function sendQuestion(question) {
  const text = question.trim();
  // Ni mensajes vacíos ni otro mensaje mientras llega una respuesta.
  if (!text || waitingAnswer) return;

  waitingAnswer = true;
  chatSend.disabled = true;
  chatSection.classList.add("started"); // en el móvil, oculta las sugerencias
  chatInput.value = "";
  resizeInput();
  addUserMessage(text);
  const answer = addAssistantMessage();
  const typewriter = createTypewriter(answer);
  // Mientras siga llegando, un cursor parpadea tras el texto (ver styles.css): si
  // un proveedor se para a medias, el texto no parece una respuesta terminada.
  // Si hay que cambiar de proveedor, llega un reinicio: el texto se quita y vuelven
  // los tres puntos hasta que llegue la respuesta buena.
  answer.message.classList.add("streaming");

  let finalText;
  try {
    const result = await requestAnswer(text, typewriter.update);
    if (result.ok) {
      await typewriter.finish();
      remember(text, result.text);
    } else {
      typewriter.stop();
      answer.message.classList.add("message-error");
    }
    finalText = result.text;
  } catch (error) {
    console.error(error);
    typewriter.stop();
    answer.message.classList.add("message-error");
    finalText = CONNECTION_ERROR_TEXT;
  }

  answer.message.classList.remove("streaming");
  answer.setText(finalText);
  // Solo ahora, con la respuesta completa de verdad, se anuncia al lector de pantalla.
  announce(finalText);
  waitingAnswer = false;
  chatSend.disabled = false;
}

// --- Caja de escribir ---

// Crece con el texto hasta 4 líneas (el máximo lo pone el CSS); después, scroll.
function resizeInput() {
  chatInput.style.height = "auto";
  chatInput.style.height = `${chatInput.scrollHeight + 2}px`;
}

chatInput.addEventListener("input", resizeInput);

// Intro envía; Mayúsculas+Intro hace un salto de línea.
chatInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    chatForm.requestSubmit();
  }
});

chatForm.addEventListener("submit", (event) => {
  event.preventDefault();
  sendQuestion(chatInput.value);
});

// --- Sugerencias y preguntas de las tarjetas ---

// Sube hasta el chat y envía la pregunta como si la hubiera escrito el usuario.
for (const button of document.querySelectorAll("[data-question]")) {
  button.addEventListener("click", () => {
    if (waitingAnswer) return;
    chatSection.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
    sendQuestion(button.dataset.question);
  });
}
