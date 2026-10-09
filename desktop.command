#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [ "$(uname -s)" != "Darwin" ]; then
  echo "Бұл іске қосу файлы Mac үшін. Linux-та GUI әзірлеу үшін desktop_entry.py қолданыңыз."
  exit 1
fi
mac_major="$(sw_vers -productVersion | cut -d. -f1)"
if [ "$mac_major" -lt 12 ]; then
  echo "Friday Desktop үшін macOS 12 Monterey немесе жаңасы қажет."
  exit 1
fi
friday_python=""
for candidate in python3.12 python3.13 python3.11 python3.10 python3; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] < (3,14) else 1)' 2>/dev/null; then
    friday_python="$(command -v "$candidate")"; break
  fi
done
if [ -z "$friday_python" ]; then
  echo "Python 3.12 орнатыңыз: https://www.python.org/downloads/release/python-31210/"
  echo "macOS 64-bit universal2 installer таңдаңыз. Python 3.14 бұл GUI нұсқасына сәйкес емес."
  exit 1
fi
if ! "$friday_python" -m venv .venv-desktop; then
  echo "Desktop виртуалды ортасы жасалмады. Жоғарыдағы қатені тексеріңіз."
  exit 1
fi
if ! .venv-desktop/bin/python -m pip install -r requirements-desktop.txt; then
  echo "Desktop тәуелділіктері орнатылмады. Жоғарыдағы pip қатесін көшіріңіз."
  exit 1
fi
if [ "${FRIDAY_SKIP_OLLAMA:-0}" != "1" ]; then
  ollama_bin="$(command -v ollama || true)"
  if [ -z "$ollama_bin" ] && [ -x /Applications/Ollama.app/Contents/Resources/ollama ]; then
    ollama_bin=/Applications/Ollama.app/Contents/Resources/ollama
  fi
  if [ -n "$ollama_bin" ]; then
    if ! curl --silent --fail --max-time 3 http://127.0.0.1:11434/api/tags >/dev/null; then
      open -a Ollama || true
      for attempt in {1..20}; do
        if curl --silent --fail --max-time 2 http://127.0.0.1:11434/api/tags >/dev/null; then break; fi
        sleep 1
      done
    fi
    if curl --silent --fail --max-time 3 http://127.0.0.1:11434/api/tags >/dev/null; then
      echo "Жергілікті AI моделі тексерілуде. Алғашқы жүктеу бірнеше ГБ болуы мүмкін."
      "$ollama_bin" pull "${FRIDAY_MODEL:-qwen3:4b}" || echo "Модель жүктелмеді. GUI баптауынан OpenAI қолдануға немесе Ollama-ны түзетуге болады."
    fi
  else
    echo "Жергілікті AI үшін Ollama орнатыңыз: https://ollama.com/download/mac"
    echo "GUI бәрібір ашылады; Баптауларда OpenAI қызметін таңдауға болады."
  fi
fi
echo "Friday Desktop ашылуда. Браузер қолданылмайды."
exec .venv-desktop/bin/python -I desktop_entry.py
