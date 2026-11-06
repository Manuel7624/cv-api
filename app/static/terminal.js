// Recuadro tipo terminal: hace una petición real a la API y muestra el JSON.

const terminalForm = document.getElementById("terminal-form");
const terminalPath = document.getElementById("terminal-path");
const terminalRun = document.getElementById("terminal-run");
const terminalOutput = document.getElementById("terminal-output");

async function runRequest() {
  const path = terminalPath.value;
  terminalRun.disabled = true;
  terminalOutput.textContent = `$ curl ${window.location.origin}${path}\n`;

  try {
    const response = await fetch(path);
    const body = await response.json();
    terminalOutput.textContent += `HTTP ${response.status}\n${JSON.stringify(body, null, 2)}`;
  } catch (error) {
    console.error(error);
    terminalOutput.textContent += "No se ha podido conectar con la API.";
  }

  terminalRun.disabled = false;
}

terminalForm.addEventListener("submit", (event) => {
  event.preventDefault();
  runRequest();
});
