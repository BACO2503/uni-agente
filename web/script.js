/* Asesor UNI — frontend sin framework. */

const chat = document.getElementById("chat");
const emptyState = document.getElementById("emptyState");
const composer = document.getElementById("composer");
const input = document.getElementById("questionInput");
const sendBtn = document.getElementById("sendBtn");
const suggestionsEl = document.getElementById("suggestions");

const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");

const drawer = document.getElementById("drawer");
const drawerScrim = document.getElementById("drawerScrim");
const drawerClose = document.getElementById("drawerClose");
const drawerSource = document.getElementById("drawerSource");
const drawerLocator = document.getElementById("drawerLocator");
const drawerExcerpt = document.getElementById("drawerExcerpt");
const drawerOcrBadge = document.getElementById("drawerOcrBadge");

const SUGGESTIONS = [
  "¿Cuál es el promedio mínimo para aprobar una materia?",
  "¿Cuántas horas de prácticas se necesitan para titularse?",
  "¿Qué cubre la beca deportiva?",
  "¿Qué pasa si falto por motivos de salud?",
];

let lastSourcesById = {}; // messageIndex -> sources[]

function renderSuggestions() {
  suggestionsEl.innerHTML = "";
  SUGGESTIONS.forEach((q) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chip";
    btn.textContent = q;
    btn.addEventListener("click", () => {
      input.value = q;
      composer.requestSubmit();
    });
    suggestionsEl.appendChild(btn);
  });
}
renderSuggestions();

async function checkStatus() {
  try {
    const res = await fetch("/api/health");
    if (!res.ok) throw new Error("bad status");
    const data = await res.json();
    statusDot.className = "status__dot ok";
    statusText.textContent = `en línea · ${data.chunks_indexados} fragmentos indexados`;
  } catch (e) {
    statusDot.className = "status__dot error";
    statusText.textContent = "el servidor no responde";
  }
}
checkStatus();

function scrollToBottom() {
  chat.scrollTop = chat.scrollHeight;
}

function addMessage({ role, text, pending = false, error = false }) {
  emptyState.style.display = "none";
  const wrapper = document.createElement("div");
  wrapper.className = `msg msg--${role}${pending ? " msg--pending" : ""}${error ? " msg--error" : ""}`;
  const bubble = document.createElement("div");
  bubble.className = "msg__bubble";
  bubble.textContent = text;
  wrapper.appendChild(bubble);
  chat.appendChild(wrapper);
  scrollToBottom();
  return wrapper;
}

function renderAnswer(wrapper, answerText, sources, provider) {
  const bubble = wrapper.querySelector(".msg__bubble");
  bubble.innerHTML = "";

  // Reemplaza marcadores [n] por chips clicables que abren la ficha de la fuente.
  const parts = answerText.split(/(\[\d+\])/g);
  parts.forEach((part) => {
    const match = part.match(/^\[(\d+)\]$/);
    if (match) {
      const n = parseInt(match[1], 10);
      const source = sources.find((s) => s.n === n);
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "cite";
      chip.textContent = n;
      if (source) {
        chip.addEventListener("click", () => openDrawer(source));
      } else {
        chip.disabled = true;
      }
      bubble.appendChild(chip);
    } else if (part) {
      bubble.appendChild(document.createTextNode(part));
    }
  });

  if (provider && provider !== "echo") {
    const meta = document.createElement("div");
    meta.className = "msg__meta";
    meta.textContent = `generado con ${provider}`;
    wrapper.appendChild(meta);
  }
  scrollToBottom();
}

function openDrawer(source) {
  drawerSource.textContent = source.source;
  drawerLocator.textContent = source.locator;
  drawerExcerpt.textContent = source.text;
  drawerOcrBadge.hidden = !source.via_ocr;
  drawer.classList.add("open");
  drawer.setAttribute("aria-hidden", "false");
  drawerScrim.classList.add("open");
}

function closeDrawer() {
  drawer.classList.remove("open");
  drawer.setAttribute("aria-hidden", "true");
  drawerScrim.classList.remove("open");
}
drawerClose.addEventListener("click", closeDrawer);
drawerScrim.addEventListener("click", closeDrawer);
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeDrawer();
});

composer.addEventListener("submit", async (e) => {
  e.preventDefault();
  const question = input.value.trim();
  if (!question) return;

  input.value = "";
  sendBtn.disabled = true;

  addMessage({ role: "user", text: question });
  const pendingWrapper = addMessage({ role: "assistant", text: "Buscando en los documentos…", pending: true });

  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Error ${res.status}`);
    }

    const data = await res.json();
    pendingWrapper.classList.remove("msg--pending");
    renderAnswer(pendingWrapper, data.answer, data.sources, data.provider);
  } catch (err) {
    pendingWrapper.classList.remove("msg--pending");
    pendingWrapper.classList.add("msg--error");
    pendingWrapper.querySelector(".msg__bubble").textContent =
      "No pude obtener una respuesta: " + err.message;
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
});
