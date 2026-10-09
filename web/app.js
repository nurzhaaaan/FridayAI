"use strict";
const $ = (selector) => document.querySelector(selector);
const STORAGE = "friday.workspace.v1";
let state = {
  chats: [],
  active: null,
  notes: [],
  settings: { lang: "kk-KZ", speak: false, engine: "auto" },
};
let pending = null;
let recognition = null;
let listening = false;
let configured = false;
let nativeSpeech = false;
let voiceMode = false;
let speaking = false;
let restartTimer = null;
let speechFinish = null;
function cancelSpeech() {
  if (speechFinish) speechFinish(false);
  window.speechSynthesis?.cancel();
}
function sessionState(text) {
  $("#session-state").textContent = text;
}
function stopSession() {
  voiceMode = false;
  clearTimeout(restartTimer);
  const previous = recognition;
  recognition = null;
  previous?.abort?.();
  listening = false;
  $("#mic").classList.remove("listening");
  $("#voice-label").textContent = "Мәтін немесе дауыс";
  cancelSpeech();
  $("#voice-session").setAttribute("aria-pressed", "false");
  $("#voice-session").textContent = "◉ Friday-мен сөйлесу";
  $(".orb").classList.remove("voice-active");
  sessionState("Дауыс режимі өшірулі");
}
function resumeListening() {
  clearTimeout(restartTimer);
  if (!voiceMode || pending || speaking || listening) return;
  restartTimer = setTimeout(() => {
    if (voiceMode && !pending && !speaking && !listening) startListening(true);
  }, 400);
}
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
      engine: saved.settings?.engine === "browser" ? "browser" : "auto",
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
  stopSession();
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
          stopSession();
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
function nativeSpeak(text) {
  cancelSpeech();
  return new Promise((resolve) => {
    speaking = true;
    recognition?.abort?.();
    if (voiceMode) sessionState("Mac дауысы дайындалуда…");
    const controller = new AbortController();
    let audio = null,
      url = null,
      finished = false;
    const timer = setTimeout(() => {
      notice("Дыбыстау уақыты аяқталды.");
      done(false);
    }, 150000);
    const done = (ok) => {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      controller.abort();
      if (audio) {
        audio.onended = null;
        audio.onerror = null;
        audio.pause();
      }
      if (url) URL.revokeObjectURL(url);
      speaking = false;
      speechFinish = null;
      resolve(ok);
      resumeListening();
    };
    speechFinish = done;
    (async () => {
      try {
        const response = await fetch("/api/speech", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text, language: state.settings.lang }),
          signal: controller.signal,
        });
        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.error || "Mac дауысы жасалмады.");
        }
        const blob = await response.blob();
        if (finished) return;
        const locale = response.headers.get("X-Friday-Voice-Language");
        if (locale && locale.slice(0, 2) !== state.settings.lang.slice(0, 2))
          notice(
            "Таңдалған тілдің дауысы жоқ. Mac-тың " +
              locale +
              " дауысы қолданылды.",
          );
        url = URL.createObjectURL(blob);
        audio = new Audio(url);
        audio.onended = () => done(true);
        audio.onerror = () => {
          notice(
            "Дыбыс ойнатылмады. Браузер мен Mac дыбыс деңгейін тексеріңіз.",
          );
          done(false);
        };
        if (voiceMode) sessionState("Friday жауап беруде…");
        await audio.play();
      } catch (error) {
        if (finished) return;
        notice(
          error.name === "NotAllowedError"
            ? "Браузер дыбысты бұғаттады. Баптаулардан «Дыбысты тексеру» басыңыз."
            : error.message,
        );
        done(false);
      }
    })();
  });
}
function speak(text) {
  if (nativeSpeech && state.settings.engine === "auto")
    return nativeSpeak(text);
  if (
    !("speechSynthesis" in window) ||
    !("SpeechSynthesisUtterance" in window)
  ) {
    notice("Бұл браузер дауыстап оқуды қолдамайды.");
    return Promise.resolve(false);
  }
  cancelSpeech();
  return new Promise((resolve) => {
    speaking = true;
    recognition?.abort?.();
    if (voiceMode) sessionState("Friday жауап беруде…");
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
        "Қазақша дауыс жоқ болса, Баптаулардан орысша немесе ағылшынша таңдаңыз.",
      );
    let finished = false;
    const watchdog = setTimeout(() => {
      notice(
        "Браузер дауысы жауап бермеді. Баптаулардан Mac дауысын таңдаңыз.",
      );
      done(false);
    }, 180000);
    const done = (ok) => {
      if (finished) return;
      finished = true;
      clearTimeout(watchdog);
      speaking = false;
      speechFinish = null;
      resolve(ok);
      resumeListening();
    };
    speechFinish = done;
    utterance.onend = () => done(true);
    utterance.onerror = () => {
      notice("Дауыстап оқу орындалмады. Құрылғының дауыс баптауын тексеріңіз.");
      done(false);
    };
    try {
      window.speechSynthesis.speak(utterance);
    } catch {
      done(false);
    }
  });
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
  recognition?.abort?.();
  if (voiceMode) sessionState("Friday ойлануда…");
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
    if (state.active === c.id && (voiceMode || state.settings.speak)) {
      const ok = await speak(data.answer);
      if (!ok && voiceMode) stopSession();
    }
  } catch (error) {
    c.failed = true;
    if (voiceMode) stopSession();
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
    resumeListening();
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
  $("#speech-engine").value = state.settings.engine;
  $("#speech-info").textContent =
    `Микрофон тануы: ${Recognition ? "бар" : "жоқ — Chrome/Edge қолданыңыз"}. Қауіпсіз бет: ${window.isSecureContext ? "иә" : "жоқ — localhost арқылы ашыңыз"}. Mac дауысы: ${nativeSpeech ? "бар" : "жоқ"}.`;
  $("#settings").showModal();
});
$("#voice-lang").addEventListener("change", (e) => {
  stopSession();
  state.settings.lang = e.target.value;
  save();
});
$("#speech-engine").addEventListener("change", (e) => {
  stopSession();
  state.settings.engine = e.target.value;
  save();
});
$("#test-speech").addEventListener("click", async () => {
  const text =
    state.settings.lang === "ru-RU"
      ? "Здравствуйте, я Фрайдей. Проверка звука."
      : state.settings.lang === "en-US"
        ? "Hello, I am Friday. This is a sound test."
        : "Сәлем, мен Friday. Дыбысты тексеру.";
  $("#speech-info").textContent = "Дыбыс тексерілуде…";
  const ok = await speak(text);
  $("#speech-info").textContent = ok
    ? "Дыбыстау аяқталды. Естілмесе, Mac дыбыс деңгейін және таңдалған шығару құрылғысын тексеріңіз."
    : $("#notice").textContent;
});
$("#auto-speak").addEventListener("change", (e) => {
  state.settings.speak = e.target.checked;
  save();
});
$("#stop-speech").addEventListener("click", () => stopSession());
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
function startListening(automatic = false) {
  if (!Recognition || !window.isSecureContext) {
    stopSession();
    const message = !Recognition
      ? "Бұл браузерде дауыс тану жоқ. Chrome немесе Edge арқылы ашыңыз."
      : "Бетті localhost арқылы ашыңыз: http://127.0.0.1:8000";
    sessionState(message);
    return notice(message);
  }
  if (pending || speaking) return;
  const current = new Recognition();
  recognition = current;
  current.lang = state.settings.lang;
  current.interimResults = false;
  current.onstart = () => {
    if (recognition !== current) return;
    listening = true;
    $("#mic").classList.add("listening");
    $("#voice-label").textContent = "Тыңдап тұрмын…";
    if (voiceMode)
      sessionState("Тыңдап тұрмын. Тоқтату: «тоқта» немесе батырманы басыңыз.");
    else notice("Сөйлеңіз. Мәтінді тексеріп, жіберіңіз.");
  };
  current.onresult = (e) => {
    if (recognition !== current || (automatic && !voiceMode)) return;
    const transcript = e.results[0][0].transcript.trim();
    if (!transcript) return;
    if (
      automatic &&
      /^(тоқта|тоқтат|стоп|stop|stop friday)[.!?]?$/i.test(transcript)
    ) {
      stopSession();
      return notice("Дауыс режимі тоқтатылды.");
    }
    $("#input").value = automatic
      ? transcript
      : ($("#input").value + " " + transcript).trim();
    resizeInput();
    if (automatic) send();
    else $("#input").focus();
  };
  current.onerror = (e) => {
    if (recognition !== current) return;
    if (e.error === "aborted" || e.error === "no-speech") return;
    stopSession();
    const errors = {
      "not-allowed":
        "Микрофонға рұқсат беріңіз: браузер баптауы және Mac System Settings → Privacy & Security → Microphone.",
      "audio-capture":
        "Микрофон табылмады. Mac-та енгізу құрылғысын тексеріңіз.",
      "language-not-supported":
        "Бұл тілде дауыс тану қолжетімсіз. Баптаулардан Русский немесе English таңдаңыз.",
      network:
        "Дауыс тану қызметіне байланыс жоқ. Chrome/Edge және интернетті тексеріңіз.",
    };
    const message = errors[e.error] || "Дауыс тану қатесі: " + e.error;
    sessionState(message);
    notice(message);
  };
  current.onend = () => {
    if (recognition !== current) return;
    listening = false;
    recognition = null;
    $("#mic").classList.remove("listening");
    $("#voice-label").textContent = "Мәтін немесе дауыс";
    resumeListening();
  };
  try {
    current.start();
  } catch {
    stopSession();
    notice("Микрофонды қосу мүмкін болмады.");
  }
}
$("#mic").addEventListener("click", () => {
  if (voiceMode) {
    stopSession();
    return;
  }
  if (listening) {
    recognition?.stop();
    return;
  }
  startListening();
});
$("#voice-session").addEventListener("click", async () => {
  if (voiceMode) {
    stopSession();
    return;
  }
  if (pending) return notice("Алдымен жауаптың аяқталуын күтіңіз.");
  if (!Recognition || !window.isSecureContext) {
    startListening(true);
    return;
  }
  $("#voice-session").disabled = true;
  try {
    await checkStatus();
  } finally {
    $("#voice-session").disabled = false;
  }
  if (!configured) {
    sessionState("AI қосылымы дайын емес.");
    return notice("Алдымен Ollama моделін немесе OpenAI кілтін қосыңыз.");
  }
  stopSession();
  if (!activeChat()) newChat();
  voiceMode = true;
  $("#voice-session").setAttribute("aria-pressed", "true");
  $("#voice-session").textContent = "■ Сөйлесуді тоқтату";
  $(".orb").classList.add("voice-active");
  notice(
    "Айтқаныңыз автоматты жіберіледі. Friday сөйлеген кезде микрофон тыңдамайды.",
  );
  startListening(true);
});
document.addEventListener("visibilitychange", () => {
  if (document.hidden) stopSession();
});
window.addEventListener("pagehide", stopSession);
async function checkStatus() {
  try {
    const response = await fetch("/api/status");
    if (!response.ok) throw new Error("Status failed");
    const data = await response.json();
    configured = data.configured;
    nativeSpeech = data.native_speech === true;
    $("#status").textContent = configured
      ? data.provider === "ollama"
        ? "Жергілікті AI дайын"
        : "AI кілті орнатылған"
      : data.provider === "ollama"
        ? "Ollama қосылмаған"
        : "API кілті қажет";
    $("#status").classList.toggle("online", configured);
    $("#connection-info").textContent = configured
      ? `Қызмет: ${data.provider || "openai"}. Модель: ${data.model}. ${data.detail || "Қосылым алғашқы сұрауда тексеріледі."}`
      : data.detail || "Ollama моделін немесе OpenAI API кілтін қосыңыз.";
    if (!configured)
      notice(
        data.detail || "AI жауаптары үшін Ollama немесе API кілтін қосыңыз.",
      );
  } catch {
    configured = false;
    $("#status").textContent = "Сервер қолжетімсіз";
    $("#status").classList.remove("online");
    $("#connection-info").textContent = "Сервермен байланыс жоқ.";
    notice("Сервермен байланыс жоқ. Бетті жаңартып көріңіз.");
  }
}
render();
checkStatus();
