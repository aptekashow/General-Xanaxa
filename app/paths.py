import json
import os
import sys
import shutil
from pathlib import Path

APP_NAME = "GeneralXanaxa"
APP_DATA_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / APP_NAME
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)

# One-time migration from the original developer folder, if it still exists.
_LEGACY_ROOT = Path(r"C:\VoiceForgeRU")
for _name in ("voices", "history", "audio"):
    _old = _LEGACY_ROOT / _name
    _new = APP_DATA_DIR / _name
    if _old.exists() and not _new.exists():
        try:
            shutil.copytree(_old, _new)
        except OSError:
            pass

CONFIG_FILE = APP_DATA_DIR / "settings.json"

def load_settings():
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

def get_model_path():
    settings = load_settings()
    configured = settings.get("model_path")
    if configured:
        return Path(configured)
    env_path = os.environ.get("QWEN_TTS_MODEL")
    if env_path:
        return Path(env_path)
    legacy = Path(r"C:\VoiceForgeRU\\models\\Qwen3-TTS-12Hz-0.6B-Base")
    if legacy.exists():
        return legacy
    return legacy

def set_model_path(path):
    settings = load_settings()
    settings["model_path"] = str(Path(path))
    CONFIG_FILE.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")

def resource_path(relative):
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return base / relative
