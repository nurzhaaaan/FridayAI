#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.10+ қажет. https://www.python.org/downloads/macos/ сайтынан орнатыңыз."
  read -r -p "Жабу үшін Enter басыңыз. "
  exit 1
fi
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else "Python 3.10+ қажет")'
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-web.txt
if [ -z "${FRIDAY_API_KEY:-}${Nurzhik_06:-}${OPENAI_API_KEY:-}" ]; then
  echo "OpenAI API кілтін енгізіңіз (экранда көрсетілмейді)."
  echo "Кілтсіз интерфейсті ашу үшін Enter басыңыз."
  read -r -s -p "API key: " FRIDAY_API_KEY
  echo
  export FRIDAY_API_KEY
fi
export FRIDAY_HOST=127.0.0.1
export PORT="${PORT:-8000}"
.venv/bin/python server.py &
friday_pid=$!
trap 'kill "$friday_pid" 2>/dev/null || true' EXIT INT TERM
for attempt in {1..20}; do
  if ! kill -0 "$friday_pid" 2>/dev/null; then
    echo "Сервер іске қосылмады. Жоғарыдағы қатені тексеріңіз."
    exit 1
  fi
  if curl --silent --fail "http://127.0.0.1:$PORT/api/status" >/dev/null; then
    open "http://127.0.0.1:$PORT"
    echo "Friday іске қосылды. Тоқтату үшін Ctrl+C басыңыз немесе Terminal терезесін жабыңыз."
    wait "$friday_pid"
    exit 0
  fi
  sleep 0.5
done
echo "Сервер дайын болмады."
exit 1
