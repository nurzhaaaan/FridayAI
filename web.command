#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.10+ қажет. https://www.python.org/downloads/macos/ сайтынан орнатыңыз."
  read -r -p "Жабу үшін Enter басыңыз. "
  exit 1
fi
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else "Python 3.10+ қажет")'
if ! python3 -m venv .venv; then
  echo "Python виртуалды ортасы жасалмады. python.org сайтынан Python 3.10+ орнатыңыз."
  exit 1
fi
if ! .venv/bin/python -m pip install -r requirements-web.txt; then
  echo "Тәуелділіктер орнатылмады. Жоғарыдағы pip қатесін көшіріңіз."
  exit 1
fi
ollama_pid=""
friday_pid=""
cleanup() {
  if [ -n "$friday_pid" ]; then kill "$friday_pid" 2>/dev/null || true; fi
  if [ -n "$ollama_pid" ]; then kill "$ollama_pid" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM
if [ -z "${FRIDAY_PROVIDER:-}" ]; then
  echo "Friday AI режимін таңдаңыз:"
  echo "1 — MacBook-та жергілікті AI (Ollama, API кілті қажет емес)"
  echo "2 — OpenAI (API кілті қажет)"
  echo "3 — Интерфейсті ғана ашу"
  read -r -p "Таңдау [1]: " friday_choice
  case "${friday_choice:-1}" in
    1) export FRIDAY_PROVIDER=ollama ;;
    2|3) export FRIDAY_PROVIDER=openai ;;
    *) echo "1, 2 немесе 3 таңдаңыз."; exit 1 ;;
  esac
else
  friday_choice=""
fi
if [ "$FRIDAY_PROVIDER" = "ollama" ]; then
  ollama_bin="$(command -v ollama || true)"
  if [ -z "$ollama_bin" ] && [ -x /Applications/Ollama.app/Contents/Resources/ollama ]; then
    ollama_bin=/Applications/Ollama.app/Contents/Resources/ollama
  fi
  if [ -z "$ollama_bin" ]; then
    echo "Алдымен https://ollama.com/download/mac сайтынан Ollama орнатыңыз және ашыңыз."
    echo "Содан кейін bash start.command командасын қайта орындаңыз."
    exit 1
  fi
  if ! curl --silent --fail http://127.0.0.1:11434/api/tags >/dev/null; then
    "$ollama_bin" serve > .venv/ollama.log 2>&1 &
    ollama_pid=$!
    for attempt in {1..30}; do
      if curl --silent --fail http://127.0.0.1:11434/api/tags >/dev/null; then break; fi
      sleep 1
    done
  fi
  export FRIDAY_MODEL="${FRIDAY_MODEL:-qwen3:4b}"
  echo "Модель: $FRIDAY_MODEL. Алғашқы жүктеу бірнеше ГБ және уақыт қажет етеді."
  if ! curl --silent --fail --max-time 3 http://127.0.0.1:11434/api/tags >/dev/null; then
    echo "Ollama 11434 портында жауап бермейді. Ollama қолданбасын ашып, қайта іске қосыңыз."
    exit 1
  fi
  if ! "$ollama_bin" pull "$FRIDAY_MODEL"; then
    echo "Модель жүктелмеді. Жоғарыдағы Ollama қатесін көшіріңіз."
    exit 1
  fi
elif [ "$FRIDAY_PROVIDER" = "openai" ]; then
  if [ "${friday_choice:-}" != "3" ] && [ -z "${FRIDAY_API_KEY:-}${Nurzhik_06:-}${OPENAI_API_KEY:-}" ]; then
    echo "OpenAI API кілтін енгізіңіз (экранда көрсетілмейді)."
    read -r -s -p "API key: " FRIDAY_API_KEY
    echo
    export FRIDAY_API_KEY
  fi
else
  echo "FRIDAY_PROVIDER openai немесе ollama болуы керек."
  exit 1
fi
export FRIDAY_HOST=127.0.0.1
export PORT="${PORT:-8000}"
.venv/bin/python server.py &
friday_pid=$!
for attempt in {1..20}; do
  if ! kill -0 "$friday_pid" 2>/dev/null; then
    echo "Сервер іске қосылмады. Жоғарыдағы қатені тексеріңіз."
    exit 1
  fi
  if curl --silent --fail "http://127.0.0.1:$PORT/api/status" >/dev/null; then
    friday_browser=""
    for app in "/Applications/Google Chrome.app" "$HOME/Applications/Google Chrome.app" "/Applications/Microsoft Edge.app" "$HOME/Applications/Microsoft Edge.app"; do
      if [ -d "$app" ]; then friday_browser="$app"; break; fi
    done
    if [ -n "$friday_browser" ]; then
      open -a "$friday_browser" "http://127.0.0.1:$PORT" || echo "Бетті Chrome/Edge ішінде қолмен ашыңыз: http://127.0.0.1:$PORT"
    else
      echo "Дауыспен сөйлесу үшін Chrome немесе Edge орнатыңыз. Safari дауыс тануын қолдамауы мүмкін."
      open "http://127.0.0.1:$PORT" || echo "Бетті қолмен ашыңыз: http://127.0.0.1:$PORT"
    fi
    echo "Friday іске қосылды. Тоқтату үшін Ctrl+C басыңыз немесе Terminal терезесін жабыңыз."
    wait "$friday_pid"
    exit 0
  fi
  sleep 0.5
done
echo "Сервер дайын болмады."
exit 1
