#!/bin/bash
# Read-only diagnostics; never print API keys or environment values.
cd "$(dirname "$0")" || exit 1
echo "Friday diagnostics"
if command -v python3 >/dev/null 2>&1; then
  python3 --version
  python3 -c 'import sys; print("Python 3.10+:", sys.version_info >= (3, 10))'
else
  echo "Python: not found"
fi
if [ -x .venv/bin/python ]; then
  .venv/bin/python --version
  .venv/bin/python -c 'import importlib.util; print("OpenAI SDK installed:", importlib.util.find_spec("openai") is not None)'
else
  echo "Project virtualenv: missing"
fi
if command -v ollama >/dev/null 2>&1; then
  echo "Ollama CLI: found"
elif [ -x /Applications/Ollama.app/Contents/Resources/ollama ]; then
  echo "Ollama CLI: installed in app, not on PATH"
else
  echo "Ollama CLI: missing"
fi
python3 - <<'PY'
import json
from urllib.request import build_opener, ProxyHandler
opener=build_opener(ProxyHandler({}))
for name,url in [('Ollama','http://127.0.0.1:11434/api/tags'),('Friday','http://127.0.0.1:8000/api/status')]:
    try:
        with opener.open(url,timeout=3) as response:
            data=json.loads(response.read(2_000_000))
        if name=='Ollama':
            print('Ollama reachable. Models:', ', '.join(m.get('name','?') for m in data.get('models',[])) or 'none')
        else:
            print('Friday reachable. Provider:', data.get('provider'), 'Model:', data.get('model'), 'Configured:', data.get('configured'))
    except Exception as exc:
        print(name + ': not reachable (' + type(exc).__name__ + ')')
PY
