const { chromium } = require("playwright");
const assert = require("node:assert/strict");
(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.CHROMIUM_PATH || undefined,
    headless: true,
    args: ["--no-sandbox"],
  });
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.addInitScript(() => {
    window.__voiceQueue = [];
    window.__speeches = [];
    window.__starts = 0;
    window.__talking = false;
    window.SpeechSynthesisUtterance = class {
      constructor(text) {
        this.text = text;
      }
    };
    Object.defineProperty(window, "speechSynthesis", {
      value: {
        cancel() {
          window.__talking = false;
        },
        getVoices() {
          return [{ lang: "kk-KZ" }];
        },
        speak(utterance) {
          window.__talking = true;
          window.__speeches.push(utterance.text);
          setTimeout(() => {
            window.__talking = false;
            utterance.onend?.();
          }, 60);
        },
      },
    });
    window.SpeechRecognition = class {
      start() {
        if (window.__talking)
          throw new Error("Microphone active during speech");
        window.__starts++;
        this.onstart?.();
        if (window.__deny) {
          this.timer=setTimeout(() => this.onerror?.({error:'not-allowed'}),20);
          return;
        }
        const text = window.__voiceQueue.shift();
        if (text)
          this.timer = setTimeout(() => {
            if (this.aborted) return;
            this.onresult?.({ results: [[{ transcript: text }]] });
            this.onend?.();
          }, 30);
      }
      stop() {
        this.abort();
      }
      abort() {
        this.aborted = true;
        clearTimeout(this.timer);
        this.onend?.();
      }
    };
  });
  await page.route("**/api/status", (r) =>
    r.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        configured: true,
        provider: "ollama",
        model: "qwen3:4b",
      }),
    }),
  );
  const requests = [];
  await page.route("**/api/chat", (r) => {
    requests.push(r.request().postDataJSON());
    return r.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ answer: "Сәлем! Мен Friday." }),
    });
  });
  await page.goto(process.env.FRIDAY_URL || "http://127.0.0.1:8000/");
  await page.getByText("Жергілікті AI дайын", { exact: true }).waitFor();
  await page.evaluate(() => (window.__voiceQueue = ["Сәлем Friday", "тоқта"]));
  await page.locator("#voice-session").click();
  await page.waitForFunction(
    () =>
      window.__starts === 2 &&
      document.querySelector("#voice-session").getAttribute("aria-pressed") ===
        "false",
  );
  assert.equal(requests.length, 1);
  assert.equal(requests[0].messages[0].content, "Сәлем Friday");
  assert.deepEqual(await page.evaluate(() => window.__speeches), [
    "Сәлем! Мен Friday.",
  ]);
  assert.equal(await page.locator(".message.assistant").count(), 1);
  // Stop while waiting for an AI response: no later speech or microphone restart.
  let release;
  const held = new Promise((r) => (release = r));
  await page.route("**/api/chat", async (r) => {
    await held;
    await r.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ answer: "Late answer" }),
    });
  });
  await page.evaluate(() => (window.__voiceQueue = ["Екінші сұрақ"]));
  await page.locator("#voice-session").click();
  await page.waitForFunction(() => document.querySelector("#send").disabled);
  await page.locator("#voice-session").click();
  release();
  await page.waitForFunction(() => !document.querySelector("#send").disabled);
  assert.equal((await page.evaluate(() => window.__speeches)).length, 1);
  assert.equal(
    await page.locator("#voice-session").getAttribute("aria-pressed"),
    "false",
  );
  await page.route('**/api/chat', r => r.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:'AI unavailable'})}));
  await page.evaluate(() => window.__voiceQueue=['Қате сұрау']);
  await page.locator('#voice-session').click();
  await page.waitForFunction(() => document.querySelector('#notice').textContent.includes('AI unavailable'));
  assert.equal(await page.locator('#voice-session').getAttribute('aria-pressed'),'false');
  await page.evaluate(() => window.__deny=true);
  await page.locator('#voice-session').click();
  await page.waitForFunction(() => document.querySelector('#notice').textContent.includes('Микрофонға рұқсат'));
  assert.equal(await page.locator('#voice-session').getAttribute('aria-pressed'),'false');
  assert.deepEqual(errors, []);
  await browser.close();
  console.log(
    "PASS: automatic voice turn, spoken response, listen after playback, spoken stop, stop during request, API failure, microphone denial; speech/AI services mocked.",
  );
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
