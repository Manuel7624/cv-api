// Pide los datos a la API y los pinta en la página.
// El texto se añade con textContent, nunca como HTML, para que ningún dato
// pueda inyectar código en la página.

function createElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function createList(items, className) {
  const list = createElement("ul", className);
  for (const item of items) {
    list.append(createElement("li", "", item));
  }
  return list;
}

async function getJson(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`${path} ha respondido ${response.status}`);
  }
  return response.json();
}

function createExternalButton(text, url) {
  const link = createElement("a", "button", text);
  link.href = url;
  link.target = "_blank";
  link.rel = "noopener";
  return link;
}

function renderProfile(profile) {
  document.getElementById("name").textContent = profile.name;
  document.getElementById("title").textContent = profile.title;
  document.getElementById("summary").textContent = profile.summary;
  document.getElementById("github").href = profile.contact.github;

  const email = createElement("a", "", profile.contact.email);
  email.href = `mailto:${profile.contact.email}`;
  document.getElementById("meta").append(`${profile.location} · `, email);

  const availability = document.getElementById("availability");
  availability.textContent = profile.availability;
  availability.hidden = false;
}

function renderExperience(items) {
  const container = document.getElementById("experience");
  for (const item of items) {
    const block = createElement("article", "item");
    block.append(
      createElement("h3", "", `${item.role} · ${item.company}`),
      createElement("p", "item-meta", `${item.period} · ${item.kind}`),
      createList(item.highlights),
    );
    container.append(block);
  }
}

function renderProjects(items) {
  const container = document.getElementById("projects");
  for (const item of items) {
    const repository = createElement("a", "repository", "Ver repositorio");
    repository.href = item.repository;
    repository.target = "_blank";
    repository.rel = "noopener";

    const block = createElement("article", "item");
    block.append(
      createElement("h3", "", item.name),
      createElement("p", "description", item.description),
      createList(item.technologies, "chips"),
      createList(item.highlights),
      repository,
    );
    container.append(block);
  }
}

function renderEducation(items) {
  const container = document.getElementById("education");
  for (const item of items) {
    const block = createElement("article", "item");
    block.append(
      createElement("h3", "", item.title),
      createElement("p", "item-meta", `${item.institution} · ${item.period} · ${item.status}`),
    );
    container.append(block);
  }
}

function renderSkills(skills) {
  const groups = [
    ["Lenguajes", skills.languages],
    ["Herramientas", skills.tools],
    ["Conceptos", skills.concepts],
  ];
  const container = document.getElementById("skills");
  for (const [title, items] of groups) {
    const block = createElement("div");
    block.append(createElement("h3", "", title), createList(items));
    container.append(block);
  }
}

function renderContact(contact) {
  const container = document.getElementById("contact");

  const email = createElement("a", "button primary", "Enviar un correo");
  email.href = `mailto:${contact.email}`;
  container.append(email);

  if (contact.linkedin) {
    container.append(createExternalButton("LinkedIn", contact.linkedin));
  }
  container.append(createExternalButton("GitHub", contact.github));
}

function renderLanguages(items) {
  const names = items.map((item) => `${item.name} · ${item.level}`);
  document.getElementById("languages").append(createList(names, "plain-list"));
}

async function loadCv() {
  const status = document.getElementById("status");
  try {
    const [profile, experience, projects, education, skills, languages] = await Promise.all([
      getJson("/profile"),
      getJson("/experience"),
      getJson("/projects"),
      getJson("/education"),
      getJson("/skills"),
      getJson("/languages"),
    ]);
    renderProfile(profile);
    renderExperience(experience);
    renderProjects(projects);
    renderEducation(education);
    renderSkills(skills);
    renderLanguages(languages);
    renderContact(profile.contact);
    status.hidden = true;
    document.getElementById("content").hidden = false;
  } catch (error) {
    console.error(error);
    status.textContent =
      "No se ha podido cargar el currículum. Recarga la página o descárgalo en PDF.";
  }
}

loadCv();
