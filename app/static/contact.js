// Botones "Enviar un correo". Un enlace mailto: solo funciona si el ordenador
// tiene un programa de correo configurado; si no, Windows pregunta con qué abrirlo
// y no pasa nada. Por eso, en el ordenador el botón abre un menú pequeño (Gmail,
// Outlook, otra app o copiar la dirección). En el móvil, que siempre tiene app de
// correo, abre directamente el mailto. Sin JavaScript, queda el enlace mailto.

const EMAIL = "manusastrenar@gmail.com";
const SUBJECT = "Contacto desde tu web";

const MAIL_OPTIONS = [
  {
    text: "Gmail",
    href: `https://mail.google.com/mail/?view=cm&fs=1&to=${EMAIL}&su=${encodeURIComponent(SUBJECT)}`,
    newTab: true,
  },
  {
    text: "Outlook",
    href: `https://outlook.office.com/mail/deeplink/compose?to=${EMAIL}&subject=${encodeURIComponent(SUBJECT)}`,
    newTab: true,
  },
  {
    text: "Otra app de correo",
    href: `mailto:${EMAIL}?subject=${encodeURIComponent(SUBJECT)}`,
    newTab: false,
  },
];

// Móvil: pantalla táctil y ancho pequeño.
const mobileQuery = window.matchMedia("(pointer: coarse) and (max-width: 768px)");

let menuCount = 0;

function setUpEmailMenu(wrapper) {
  const link = wrapper.querySelector(".email-link");
  const mailtoHref = link.href;
  menuCount += 1;
  const menuId = `email-options-${menuCount}`;

  // El enlace pasa a ser un botón que abre y cierra el menú.
  const button = document.createElement("button");
  button.type = "button";
  button.className = link.className;
  button.append(...link.childNodes);
  button.setAttribute("aria-expanded", "false");
  button.setAttribute("aria-controls", menuId);
  link.replaceWith(button);

  const menu = document.createElement("div");
  menu.className = "email-options";
  menu.id = menuId;
  menu.hidden = true;
  const list = document.createElement("ul");

  for (const option of MAIL_OPTIONS) {
    const item = document.createElement("a");
    item.className = "email-option";
    item.href = option.href;
    item.textContent = option.text;
    if (option.newTab) {
      item.target = "_blank";
      item.rel = "noopener";
    }
    item.addEventListener("click", () => closeMenu(false));
    const li = document.createElement("li");
    li.append(item);
    list.append(li);
  }

  const copyButton = document.createElement("button");
  copyButton.type = "button";
  copyButton.className = "email-option";
  copyButton.textContent = "Copiar dirección";
  const copyItem = document.createElement("li");
  copyItem.append(copyButton);
  list.append(copyItem);

  // Aviso para lectores de pantalla (y visible) al copiar.
  const status = document.createElement("p");
  status.className = "email-status";
  status.setAttribute("role", "status");

  menu.append(list, status);
  wrapper.append(menu);

  const options = () => [...menu.querySelectorAll(".email-option")];

  function openMenu() {
    menu.hidden = false;
    button.setAttribute("aria-expanded", "true");
  }

  function closeMenu(returnFocus) {
    if (menu.hidden) return;
    menu.hidden = true;
    button.setAttribute("aria-expanded", "false");
    status.textContent = "";
    copyButton.textContent = "Copiar dirección";
    if (returnFocus) button.focus();
  }

  button.addEventListener("click", () => {
    if (mobileQuery.matches) {
      window.location.href = mailtoHref;
      return;
    }
    if (menu.hidden) {
      openMenu();
      options()[0].focus();
    } else {
      closeMenu(false);
    }
  });

  copyButton.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(EMAIL);
      copyButton.textContent = "Correo copiado";
      status.textContent = "Correo copiado";
    } catch (error) {
      status.textContent = `No se ha podido copiar. La dirección es ${EMAIL}`;
    }
  });

  // Teclado: flechas para moverse por las opciones, Esc para cerrar.
  wrapper.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !menu.hidden) {
      event.preventDefault();
      closeMenu(true);
      return;
    }
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    if (mobileQuery.matches) return;
    event.preventDefault();
    if (menu.hidden) openMenu();
    const items = options();
    const current = items.indexOf(document.activeElement);
    const step = event.key === "ArrowDown" ? 1 : -1;
    const next = current === -1
      ? (step === 1 ? 0 : items.length - 1)
      : (current + step + items.length) % items.length;
    items[next].focus();
  });

  // Se cierra al pulsar fuera o al salir del menú con el tabulador.
  document.addEventListener("click", (event) => {
    if (!wrapper.contains(event.target)) closeMenu(false);
  });
  wrapper.addEventListener("focusout", (event) => {
    if (event.relatedTarget && !wrapper.contains(event.relatedTarget)) closeMenu(false);
  });
}

for (const wrapper of document.querySelectorAll(".email-menu")) {
  setUpEmailMenu(wrapper);
}
