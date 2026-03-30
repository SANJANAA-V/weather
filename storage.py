from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any

DATA_FILE = Path(__file__).resolve().parent / "server_data.json"
_LOCK = Lock()


def _load_data() -> dict[str, Any]:
    if not DATA_FILE.exists():
        return {"profiles": {}}
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"profiles": {}}


def _save_data(data: dict[str, Any]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_profile(username: str) -> dict[str, Any]:
    with _LOCK:
        data = _load_data()
        return data.get("profiles", {}).get(username, {"favorites": [], "history": [], "compare": []})


def save_profile(username: str, profile: dict[str, Any]) -> dict[str, Any]:
    with _LOCK:
        data = _load_data()
        profiles = data.setdefault("profiles", {})
        profiles[username] = {
            "favorites": profile.get("favorites", []),
            "history": profile.get("history", []),
            "compare": profile.get("compare", []),
        }
        _save_data(data)
        return profiles[username]
