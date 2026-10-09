"use strict";
const $ = (selector) => document.querySelector(selector);
const STORAGE = "friday.workspace.v1";
let state = {
  chats: [],
  active: null,
  notes: [],
  settings: { lang: "kk-KZ", speak: false },
};
let pending = null;
let recognition = null;
let listening = false;
let configured = false;
function notice(text) {
  $("#notice").textContent = text;
}
try {
  const saved = JSON.parse(localStorage.getItem(STORAGE) || "null");
  if (saved && Array.isArray(saved.chats) && Array.isArray(saved.notes)) {
    state.chats = saved.chats.filter(
      (c) =>
        c &&
        typeof c.id === "string" &&
        typeof c.title === "string" &&
        Array.isArray(c.messages) &&
        c.messages.every(
          (m) =>
            m &&
            ["user", "assistant"].includes(m.role) &&
            typeof m.content === "string",
        ),
    );
    state.notes = saved.notes.filter(
      (n) => n && typeof n.id === "string" && typeof n.text === "string",
    );
    state.active = saved.active;
    state.settings = {
      lang: ["kk-KZ", "ru-RU", "en-US"].includes(saved.settings?.lang)
        ? saved.settings.lang
        : "kk-KZ",
      speak: saved.settings?.speak === true,
    };
  }
} catch {
  notice("Браузердегі сақталған деректерді оқу мүмкін болмады.");
}
function save() {
  try {
    localStorage.setItem(STORAGE, JSON.stringify(state));
  } catch {
    notice(
      "Браузер жады толған немесе сақтау өшірілген. Әңгімені жүктеп алыңыз.",
    );
  }
}
function activeChat() {
  return state.chats.find((c) => c.id === state.active);
}
function button(text, action, label) {
  const b = document.createElement("button");
  b.type = "button";
  b.textContent = text;
  if (label) b.setAttribute("aria-label", label);
  b.addEventListener("click", action);
  return b;
}
function newChat() {
  window.speechSynthesis?.cancel();
  const c = { id: crypto.randomUUID(), title: "Жаңа әңгіме", messages: [] };
  state.chats.unshift(c);
  state.active = c.id;
  save();
  render();
  $("#sidebar").classList.remove("open");
  $("#input").focus();
  notice("");
}
function renderHistory() {
  const history = $("#history");
  history.replaceChildren();
  if (!state.chats.length) {
    const p = document.createElement("p");
    p.className = "empty-history";
    p.textContent = "Бірінші әңгімеңіз осы жерде пайда болады.";
    history.append(p);
  }
  for (const c of state.chats) {
    const row = document.createElement("div");
    row.className = "history-row" + (state.active === c.id ? " active" : "");
    row.append(
      button(
        c.title,
        () => {
          state.active = c.id;
          save();
          render();
          notice("");
          $("#sidebar").classList.remove("open");
        },
        c.title,
      ),
    );
    const del = button(
      "×",
      () => {
        if (pending === c.id)
          return notice("Алдымен жауаптың аяқталуын күтіңіз.");
        if (!confirm("Осы әңгімені өшіресіз бе?")) return;
        state.chats = state.chats.filter((x) => x.id !== c.id);
        if (state.active === c.id) state.active = state.chats[0]?.id || null;
        save();
        render();
      },
      "Әңгімені өшіру",
    );
    del.className = "history-delete";
    row.append(del);
    history.append(row);
  }
}
function speak(text) {
  if (!("speechSynthesis" in window))
    return notice("Бұл браузер дауыстап оқуды қолдамайды.");
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = state.settings.lang;
  const voice = window.speechSynthesis
    .getVoices()
    .find((v) =>
      v.lang.toLowerCase().startsWith(state.settings.lang.slice(0, 2)),
    );
  if (voice) utterance.voice = voice;
  else if (state.settings.lang === "kk-KZ")
    notice(
      "Қазақша дауыс табылмады. Құрылғыдағы дауыстарға байланысты оқылуы мүмкін.",
    );
  utterance.onerror = () =>
    notice("Дауыстап оқу орындалмады. Браузердің дауыс баптауын тексеріңіз.");
  window.speechSynthesis.speak(utterance);
}
function render() {
  renderHistory();
  const c = activeChat(),
    messages = $("#messages");
  messages.replaceChildren();
  $("#welcome").classList.toggle("hidden", !!c?.messages.length);
  for (const m of c?.messages || []) {
    const row = document.createElement("article");
    row.className = "message " + m.role;
    const badge = document.createElement("div");
    badge.className = "badge";
    badge.textContent = m.role === "user" ? "С" : "F";
    const body = document.createElement("div");
    body.className = "message-body";
    const name = document.createElement("div");
    name.className = "message-name";
    name.textContent = m.role === "user" ? "Сіз" : "Friday";
    const content = document.createElement("div");
    content.className = "message-text";
    content.textContent = m.content;
    body.append(name, content);
    if (m.role === "assistant") {
      const actions = document.createElement("div");
      actions.className = "message-actions";
      actions.append(
        button("Көшіру", async () => {
          try {
            await navigator.clipboard.writeText(m.content);
            notice("Жауап көшірілді.");
          } catch {
            notice("Көшіру қолжетімсіз. Мәтінді белгілеп көшіріңіз.");
          }
        }),
      );
      actions.append(button("Оқу", () => speak(m.content)));
      actions.append(
        button("Жазбаға сақтау", () => {
          state.notes.unshift({ id: crypto.randomUUID(), text: m.content });
          save();
          notice("Жазба сақталды.");
        }),
      );
      body.append(actions);
    }
    row.append(badge, body);
    messages.append(row);
  }
  if (pending && pending === c?.id) {
    const t = document.createElement("div");
    t.className = "thinking";
    t.textContent = "Friday ойлануда…";
    messages.append(t);
  }
  $("#send").disabled = !!pending;
  $("#retry").classList.toggle("hidden", !c?.failed || !!pending);
  $("#export").disabled = !c?.messages.length;
  $("#conversation").scrollTop = $("#conversation").scrollHeight;
}
async function send(retry = false) {
  if (pending) return;
  const text = $("#input").value.trim();
  if (!retry && !text) return;
  if (!activeChat()) newChat();
  const c = activeChat();
  if (!retry) {
    c.messages.push({ role: "user", content: text });
    if (c.messages.length === 1) c.title = text.slice(0, 42);
    $("#input").value = "";
    resizeInput();
  }
  c.failed = false;
  pending = c.id;
  save();
  render();
  notice("");
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 100000);
  try {
    // Bound context by both number of turns and encoded request size.
    const context = c.messages.slice(-39);
    while (
      context.length > 1 &&
      new TextEncoder().encode(JSON.stringify({ messages: context })).length >
        90000
    )
      context.shift();
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: context }),
      signal: controller.signal,
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Сұрау орындалмады.");
    if (typeof data.answer !== "string" || !data.answer)
      throw new Error("AI бос жауап қайтарды.");
    c.messages.push({ role: "assistant", content: data.answer });
    save();
    if (state.active === c.id && state.settings.speak) speak(data.answer);
  } catch (error) {
    c.failed = true;
    save();
    if (state.active === c.id) {
      notice(
        error.name === "AbortError"
          ? "Күту уақыты аяқталды. Қайта жіберіңіз."
          : error.message,
      );
    }
  } finally {
    clearTimeout(timer);
    pending = null;
    render();
  }
}
function resizeInput() {
  $("#input").style.height = "auto";
  $("#input").style.height = Math.min($("#input").scrollHeight, 180) + "px";
}
$("#chat-form").addEventListener("submit", (e) => {
  e.preventDefault();
  send();
});
$("#input").addEventListener("input", resizeInput);
$("#input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    send();
  }
});
$("#retry").addEventListener("click", () => send(true));
$("#new-chat").addEventListener("click", newChat);
window.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    newChat();
  }
});
$(".suggestions").addEventListener("click", (e) => {
  const target = e.target.closest("[data-prompt]");
  if (target) {
    $("#input").value = target.dataset.prompt;
    resizeInput();
    $("#input").focus();
  }
});
$("#menu").addEventListener("click", () =>
  $("#sidebar").classList.toggle("open"),
);
$("main").addEventListener("click", (e) => {
  if (!e.target.closest("#menu")) $("#sidebar").classList.remove("open");
});
$("#settings-open").addEventListener("click", () => {
  $("#voice-lang").value = state.settings.lang;
  $("#auto-speak").checked = state.settings.speak;
  $("#settings").showModal();
});
$("#voice-lang").addEventListener("change", (e) => {
  state.settings.lang = e.target.value;
  save();
});
$("#auto-speak").addEventListener("change", (e) => {
  state.settings.speak = e.target.checked;
  save();
});
$("#stop-speech").addEventListener("click", () =>
  window.speechSynthesis?.cancel(),
);
for (const b of document.querySelectorAll(".close"))
  b.addEventListener("click", () => b.closest("dialog").close());
$("#clear-all").addEventListener("click", () => {
  if (pending) {
    $("#settings").close();
    return notice("Алдымен жауаптың аяқталуын күтіңіз.");
  }
  if (
    confirm(
      "Барлық әңгімелерді өшіру керек пе? Бұл әрекетті қайтару мүмкін емес.",
    )
  ) {
    state.chats = [];
    state.active = null;
    save();
    render();
    $("#settings").close();
  }
});
$("#export").addEventListener("click", () => {
  const c = activeChat();
  if (!c) return;
  const text = c.messages
    .map((m) => `${m.role === "user" ? "Сіз" : "Friday"}:\n${m.content}`)
    .join("\n\n");
  const url = URL.createObjectURL(
    new Blob([text], { type: "text/plain;charset=utf-8" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = "friday-chat.txt";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
function renderNotes() {
  $("#note-list").replaceChildren();
  for (const n of state.notes) {
    const div = document.createElement("div");
    div.className = "note";
    const text = document.createElement("span");
    text.textContent = n.text;
    div.append(text);
    div.append(
      button("Өшіру", () => {
        if (!confirm("Жазбаны өшіресіз бе?")) return;
        state.notes = state.notes.filter((x) => x.id !== n.id);
        save();
        renderNotes();
      }),
    );
    $("#note-list").append(div);
  }
}
$("#notes-open").addEventListener("click", () => {
  renderNotes();
  $("#notes").showModal();
});
$("#note-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const text = $("#note-input").value.trim();
  if (!text) return;
  state.notes.unshift({ id: crypto.randomUUID(), text });
  $("#note-input").value = "";
  save();
  renderNotes();
});
const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
$("#mic").addEventListener("click", () => {
  if (!Recognition)
    return notice(
      "Бұл браузер дауыс тануды қолдамайды. Chrome немесе Edge қолданыңыз.",
    );
  if (!window.isSecureContext)
    return notice("Микрофон үшін HTTPS немесе localhost қажет.");
  if (listening) {
    recognition.stop();
    return;
  }
  recognition = new Recognition();
  recognition.lang = state.settings.lang;
  recognition.interimResults = false;
  recognition.onstart = () => {
    listening = true;
    $("#mic").classList.add("listening");
    $("#voice-label").textContent = "Тыңдап тұрмын…";
    notice("Сөйлеңіз. Аяқтағаннан кейін мәтінді тексеріп, жіберіңіз.");
  };
  recognition.onresult = (e) => {
    $("#input").value = (
      $("#input").value +
      " " +
      e.results[0][0].transcript
    ).trim();
    resizeInput();
    $("#input").focus();
  };
  recognition.onerror = (e) =>
    notice(
      e.error === "not-allowed"
        ? "Микрофонға рұқсат берілмеді. Браузер рұқсатын тексеріңіз."
        : "Дауыс танылмады: " + e.error + ". Мәтінмен жаза аласыз.",
    );
  recognition.onend = () => {
    listening = false;
    $("#mic").classList.remove("listening");
    $("#voice-label").textContent = "Мәтін немесе дауыс";
  };
  try {
    recognition.start();
  } catch {
    notice("Микрофонды қосу мүмкін болмады.");
  }
});
async function checkStatus() {
  try {
    const response = await fetch("/api/status");
    if (!response.ok) throw new Error("Status failed");
    const data = await response.json();
    configured = data.configured;
    $("#status").textContent = configured
      ? "AI кілті орнатылған"
      : "API кілті қажет";
    $("#status").classList.toggle("online", configured);
    $("#connection-info").textContent = configured
      ? `Модель: ${data.model}. Қосылым алғашқы сұрау кезінде тексеріледі.`
      : "Сервердің FRIDAY_API_KEY немесе Nurzhik_06 айнымалысына OpenAI кілтін орнатыңыз, содан кейін серверді қайта іске қосыңыз.";
    if (!configured)
      notice("Интерфейс дайын. AI жауаптары үшін серверге API кілтін қосыңыз.");
  } catch {
    $("#status").textContent = "Сервер қолжетімсіз";
    $("#status").classList.remove("online");
    $("#connection-info").textContent = "Сервермен байланыс жоқ.";
    notice("Сервермен байланыс жоқ. Бетті жаңартып көріңіз.");
  }
}
render();
checkStatus();
