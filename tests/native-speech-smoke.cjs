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
  const wav = Buffer.alloc(44 + 4800);
  wav.write("RIFF", 0);
  wav.writeUInt32LE(wav.length - 8, 4);
  wav.write("WAVEfmt ", 8);
  wav.writeUInt32LE(16, 16);
  wav.writeUInt16LE(1, 20);
  wav.writeUInt16LE(1, 22);
  wav.writeUInt32LE(16000, 24);
  wav.writeUInt32LE(32000, 28);
  wav.writeUInt16LE(2, 32);
  wav.writeUInt16LE(16, 34);
  wav.write("data", 36);
  wav.writeUInt32LE(4800, 40);
  for (let i = 0; i < 2400; i++)
    wav.writeInt16LE(
      Math.round(Math.sin((i * 2 * Math.PI * 440) / 16000) * 1000),
      44 + i * 2,
    );
  await page.route("**/api/status", (r) =>
    r.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        configured: true,
        provider: "ollama",
        model: "test",
        native_speech: true,
      }),
    }),
  );
  const requests = [];
  await page.route("**/api/speech", (r) => {
    requests.push(r.request().postDataJSON());
    return r.fulfill({
      contentType: "audio/wav",
      headers: { "X-Friday-Voice-Language": "ru_RU" },
      body: wav,
    });
  });
  await page.goto(process.env.FRIDAY_URL || "http://127.0.0.1:8000/");
  await page.getByText("Жергілікті AI дайын", { exact: true }).waitFor();
  await page.locator("#settings-open").click();
  await page.locator("#voice-lang").selectOption("ru-RU");
  await page.locator("#test-speech").click();
  await page.waitForFunction(() =>
    document
      .querySelector("#speech-info")
      .textContent.includes("Дыбыстау аяқталды"),
  );
  assert.equal(requests.length, 1);
  assert.equal(requests[0].language, "ru-RU");
  // Unsupported recognition must give an explicit explanation, not a silent toggle.
  const unsupported = await browser.newPage();
  await unsupported.addInitScript(() => {
    window.SpeechRecognition = undefined;
    window.webkitSpeechRecognition = undefined;
  });
  await unsupported.route("**/api/status", (r) =>
    r.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ configured: true }),
    }),
  );
  await unsupported.goto(process.env.FRIDAY_URL || "http://127.0.0.1:8000/");
  await unsupported.locator("#voice-session").click();
  assert.match(
    await unsupported.locator("#session-state").innerText(),
    /Chrome немесе Edge/,
  );
  assert.equal(
    await unsupported.locator("#voice-session").getAttribute("aria-pressed"),
    "false",
  );
  assert.deepEqual(errors, []);
  await browser.close();
  console.log(
    "PASS: native WAV route used, real browser audio playback completion, unsupported recognition explanation; native audio fixture mocked.",
  );
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
