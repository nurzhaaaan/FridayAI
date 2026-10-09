"""Private local settings and chat history; API keys are never persisted."""

import json
import os
from pathlib import Path
import tempfile


def directory():
    path = Path.home() / "Library" / "Application Support" / "Friday"
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def load():
    try:
        data = json.loads((directory() / "workspace.json").read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        settings = data.get("settings", {})
        if not isinstance(settings, dict):
            settings = {}
        if not isinstance(settings.get("model", ""), str):
            settings.pop("model", None)
        if not isinstance(settings.get("folder", ""), str):
            settings.pop("folder", None)
        if not isinstance(settings.get("speak", True), bool):
            settings.pop("speak", None)
        data["settings"] = settings
        return data
    except (OSError, ValueError):
        return {}


def save(settings, history):
    allowed = {
        key: value
        for key, value in settings.items()
        if key in ("provider", "model", "language", "folder", "speak")
    }
    messages = [
        {"role": m["role"], "content": m["content"]}
        for m in history[-100:]
        if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str)
    ]
    path = directory()
    fd, temp = tempfile.mkstemp(prefix=".friday-", dir=path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(
                {"settings": allowed, "history": messages}, file, ensure_ascii=False
            )
        os.replace(temp, path / "workspace.json")
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
