const { chromium } = require("playwright");
const assert = require("node:assert/strict");
(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.CHROMIUM_PATH || undefined,
    headless: true,
    args: ["--no-sandbox"],
  });
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1000 },
  });
  await page.addInitScript(() => {
    class FakeRecognition {
      start() {
        this.onstart?.();
        setTimeout(() => {
          this.onresult?.({
            results: [[{ transcript: "Дауыстық хабарлама" }]],
          });
          this.onend?.();
        }, 30);
      }
      stop() {
        this.onend?.();
      }
    }
    window.SpeechRecognition = FakeRecognition;
    window.SpeechSynthesisUtterance = class {
      constructor(text) {
        this.text = text;
      }
    };
    Object.defineProperty(window, "speechSynthesis", {
      value: {
        cancel() {},
        getVoices() {
          return [{ lang: "kk-KZ" }];
        },
        speak(utterance) {
          window.__spokenText = utterance.text;
          setTimeout(() => utterance.onend?.(), 20);
        },
      },
    });
  });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.route("**/api/status", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ configured: false, model: "test-model" }),
    }),
  );
  await page.route("**/api/chat", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ error: "AI қосылмаған. API кілтін орнатыңыз." }),
    }),
  );
  await page.goto(process.env.FRIDAY_URL || "http://127.0.0.1:8000/");
  await page.getByText("API кілті қажет", { exact: true }).waitFor();
  await page.screenshot({
    path: "/tmp/friday-desktop.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.locator("[data-prompt]").first().click();
  assert.match(await page.locator("#input").inputValue(), /жоспар/);
  await page.locator("#input").fill("Сәлем Friday");
  await page.locator("#send").click();
  await page
    .getByRole("button", { name: "Қайта жіберу", exact: true })
    .waitFor();
  assert.match(await page.locator("#notice").innerText(), /AI қосылмаған/);
  assert.equal(await page.locator(".message.user").count(), 1);
  // Mock only upstream chat behavior, leaving the real frontend/server assets intact.
  await page.locator("#mic").click();
  await page.waitForFunction(() =>
    document.querySelector("#input").value.includes("Дауыстық хабарлама"),
  );
  await page.locator("#input").fill("");
  const requests = [];
  await page.route("**/api/chat", async (route) => {
    requests.push(route.request().postDataJSON());
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        answer: "Сәлем! <script>alert(1)</script> Сізге қалай көмектесейін?",
      }),
    });
  });
  await page.getByRole("button", { name: "Қайта жіберу", exact: true }).click();
  await page.locator(".message.assistant").waitFor();
  await page.getByRole("button", { name: "Оқу", exact: true }).click();
  assert.match(await page.evaluate(() => window.__spokenText), /Сәлем/);

  assert.equal(await page.locator(".message.user").count(), 1);
  assert.match(
    await page.locator(".message.assistant .message-text").innerText(),
    /<script>/,
  );
  assert.equal(await page.locator(".message-text script").count(), 0);
  await page.locator("#input").fill("Жоспар құрайық");
  await page.locator("#input").press("Enter");
  await page.waitForFunction(
    () => document.querySelectorAll(".message.assistant").length === 2,
  );
  assert.equal(requests[1].messages.length, 3);
  await page
    .getByRole("button", { name: "Жазбаға сақтау", exact: true })
    .first()
    .click();
  await page.locator("#notes-open").click();
  await page.locator("#note-list .note").waitFor();
  await page.locator("#note-input").fill("Маңызды жұмыс");
  await page.locator("#note-form").getByRole("button").click();
  assert.equal(await page.locator("#note-list .note").count(), 2);
  await page.locator("#notes .close").click();
  const download = page.waitForEvent("download");
  await page.locator("#export").click();
  assert.equal((await download).suggestedFilename(), "friday-chat.txt");
  await page.reload();
  await page.locator(".message.assistant").first().waitFor();
  assert.equal(await page.locator(".message.assistant").count(), 2);
  await page.locator("#settings-open").click();
  await page.locator("#voice-lang").selectOption("ru-RU");
  await page.locator("#auto-speak").check();
  await page.locator("#settings .close").click();
  await page.reload();
  await page.locator("#settings-open").click();
  assert.equal(await page.locator("#voice-lang").inputValue(), "ru-RU");
  assert.equal(await page.locator("#auto-speak").isChecked(), true);
  await page.locator("#settings .close").click();
  await page.locator("#new-chat").click();
  assert.equal(await page.locator(".message").count(), 0);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "/tmp/friday-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    true,
  );
  await page.locator("#menu").click();
  assert.equal(
    await page
      .locator("#sidebar")
      .evaluate((e) => e.classList.contains("open")),
    true,
  );
  await page.locator(".history-row").last().locator("button").first().click();
  assert.equal(await page.locator(".message.assistant").count(), 2);
  assert.deepEqual(errors, []);
  await browser.close();
  console.log(
    "PASS: browser chat, missing-key error, retry, context, safe rendering, history persistence, notes, export, settings, mobile layout/navigation, voice input/output; AI and browser speech services mocked.",
  );
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
