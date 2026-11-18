import json
from datetime import datetime
from pathlib import Path
from app.paths import APP_DATA_DIR


HISTORY_DIR = APP_DATA_DIR / "history"
HISTORY_FILE = HISTORY_DIR / "history.json"


class HistoryManager:
    def __init__(self):
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        if not HISTORY_FILE.exists():
            HISTORY_FILE.write_text("[]", encoding="utf-8")

    def list(self):
        try:
            data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def add(self, text, profile_name, audio_path):
        records = self.list()
        records.insert(0, {
            "text": text,
            "profile": profile_name,
            "audio_path": str(audio_path),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        })
        HISTORY_FILE.write_text(
            json.dumps(records[:500], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def clear(self):
        HISTORY_FILE.write_text("[]", encoding="utf-8")
