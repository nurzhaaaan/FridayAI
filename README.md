# Friday AI

A personal AI assistant with a Kazakh web interface, contextual chat and browser voice controls. Answers use either OpenAI (`gpt-4o-mini`) or a local Ollama model (`qwen3:4b`). Russian and English are also supported.

## MacBook quick start

Download this repository using GitHub **Code → Download ZIP**, extract it, then open Terminal in the extracted folder and run:

```bash
bash start.command
```

Install Python 3.10+ from python.org first. The launcher creates a local virtual environment, installs web dependencies, offers local Ollama, OpenAI, or interface-only mode, starts the server, and opens your browser. Choose 1 for local AI without an API key. Install and open Ollama from https://ollama.com/download/mac first; the launcher downloads the selected model (several GB on first use). Choose 2 for OpenAI or 3 for interface-only mode. Keep Terminal open; Ctrl+C stops the server. See `MACBOOK-START.txt` for Kazakh instructions. The launcher supports Intel and Apple Silicon through compatible Python, but has not been run on a physical MacBook.

## Start the web application

Python 3.10+ is required. The web app does not require PyTorch, Whisper or server audio hardware.

```bash
cd /workspace/FridayAI
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-web.txt
python server.py
```

Set `FRIDAY_API_KEY` securely in your environment before starting the server. The existing `Nurzhik_06` variable and `OPENAI_API_KEY` are also accepted. Do not commit a key or place it in frontend code. This app does not automatically load `.env` files.

The server defaults to loopback port 8000. Open the local application in a browser. `PORT`, `FRIDAY_HOST` and `FRIDAY_MODEL` can override the port, bind address and model. For the prepared cloud environment, `source /workspace/.fridayai/activate.sh` activates installed dependencies without creating another virtual environment.

## Local AI and hands-free voice

Set `FRIDAY_PROVIDER=ollama` and optionally `FRIDAY_MODEL=qwen3:4b`. Start Ollama and run `ollama pull qwen3:4b` before `python server.py`. The server checks the local model list for readiness, sends chat to `127.0.0.1:11434` and uses no external proxy for these local requests. OpenAI remains the default for direct server startup.

Click **Friday-мен сөйлесу** to enable an explicit microphone session. Final transcripts are sent automatically; Friday speaks the answer and resumes listening after playback ends. Recognition pauses during AI requests and speech, preventing the assistant from hearing itself. Say **тоқта / стоп / stop**, click the stop button, or hide the tab to end listening. Recognition/network/playback failures stop the session rather than retrying indefinitely. This is a visible browser session, not a background wake-word service.

Browser speech recognition can use a remote provider even with local Ollama, so the whole application is not fully offline. Kazakh synthesis availability depends on installed device voices. If unavailable, select Russian or English in settings. Local model performance depends on Mac memory and hardware; neither real Ollama inference nor physical Mac audio has been validated in the cloud.

## Features

- Multi-turn chat with a bounded context window, loading state, readable API errors and retry.
- Multiple conversations, local history, individual deletion and text export.
- Notes: add your own notes or save an assistant response.
- Voice input using browser speech recognition; review the transcript before sending.
- Optional spoken answers, language selection and stop playback.
- Responsive layout, keyboard navigation and reduced-motion support.
- API credentials stay on the server; model output is rendered as text, never executed as HTML.

Chats and notes are saved in this browser's local storage, not synchronized between devices. Model context includes the most recent messages (up to 39, further trimmed for request size). Clearing chats does not clear notes. The app cannot browse the internet, open programs or execute computer commands.

Voice recognition depends on browser support and provider language availability. Use Chrome/Edge and allow microphone access on HTTPS or localhost. Kazakh speech recognition and speech synthesis depend on the device/provider and may be unavailable. Browser speech recognition may send audio to its provider. Text input works without voice support. AI messages are sent to the selected provider: local Ollama or OpenAI. OpenAI requires a valid key and available quota.

## Verification

```bash
python -m unittest discover -s tests -v
node --check web/app.js
```

The suite tests HTTP routes, input limits, origin checks, missing credentials, context forwarding, error sanitization and the OpenAI request contract. External OpenAI calls are mocked, so passing tests do not establish account connectivity.

Optional browser smoke test (with the server running): install Playwright in your test environment, then run `node tests/browser-smoke.cjs` and `node tests/voice-smoke.cjs`. Set `CHROMIUM_PATH` for a system Chromium executable and `FRIDAY_URL` for a different server URL. This tests chat/retry, context, safe output rendering, history, notes, export, settings, mobile navigation and browser voice controls. AI responses and browser speech services are mocked; microphone hardware and real provider language support require a manual check.

## Legacy local voice assistant

The original `python main.py` interface remains available. Install `requirements.txt`, FFmpeg and platform-compatible PortAudio/eSpeak libraries. It loads the OpenAI Whisper `base` model, records from a physical microphone and speaks through the host audio device. The cloud machine has no audio devices, so use the web app there. The checked-in macOS Python executables/native binaries are not used on Linux.

## Deployment scope

This server is for a personal development workflow and binds to loopback by default. Before exposing it to other people, add user authentication, persistent per-user storage, TLS via a reverse proxy and deployment-level rate limits. The built-in server is not a production hosting stack. No public site has been deployed by this repository change.
