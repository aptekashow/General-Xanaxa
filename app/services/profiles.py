import json
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path

import torch
from app.paths import APP_DATA_DIR


VOICES_DIR = APP_DATA_DIR / "voices"


class ProfileManager:
    def __init__(self):
        VOICES_DIR.mkdir(parents=True, exist_ok=True)

    def create_profile(self, name, audio_path, reference_text, engine):
        name = name.strip()
        reference_text = reference_text.strip()

        if not name:
            raise ValueError("Укажи название голосового профиля.")

        if not reference_text:
            raise ValueError("Укажи текст образца голоса.")

        source = Path(audio_path)
        if not source.is_file():
            raise FileNotFoundError(f"Не найден аудиофайл: {source}")

        profile_id = uuid.uuid4().hex[:12]
        folder = VOICES_DIR / profile_id
        folder.mkdir(parents=True, exist_ok=False)

        audio_copy = folder / f"reference{source.suffix.lower()}"
        shutil.copy2(source, audio_copy)

        try:
            prompt = engine.create_profile(str(audio_copy), reference_text)
            torch.save(prompt, folder / "prompt.pt")

            metadata = {
                "id": profile_id,
                "name": name,
                "reference_text": reference_text,
                "audio_file": audio_copy.name,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }

            (folder / "profile.json").write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            return metadata

        except Exception:
            shutil.rmtree(folder, ignore_errors=True)
            raise

    def list_profiles(self):
        profiles = []

        for folder in VOICES_DIR.iterdir():
            metadata_file = folder / "profile.json"

            if folder.is_dir() and metadata_file.is_file():
                try:
                    profiles.append(
                        json.loads(metadata_file.read_text(encoding="utf-8"))
                    )
                except (OSError, json.JSONDecodeError):
                    continue

        return sorted(
            profiles,
            key=lambda item: item.get("created_at", ""),
            reverse=True,
        )

    def load_prompt(self, profile_id):
        if not re.fullmatch(r"[a-f0-9]{12}", profile_id):
            raise ValueError("Некорректный идентификатор профиля.")

        prompt_file = VOICES_DIR / profile_id / "prompt.pt"

        if not prompt_file.is_file():
            raise FileNotFoundError("Голосовой профиль не найден.")

        # Загружаем только собственные файлы профилей,
        # созданные этим приложением.
        return torch.load(
            prompt_file,
            map_location="cpu",
            weights_only=False,
        )

    def delete_profile(self, profile_id):
        if not re.fullmatch(r"[a-f0-9]{12}", profile_id):
            raise ValueError("Некорректный идентификатор профиля.")

        folder = VOICES_DIR / profile_id

        if not (folder / "profile.json").is_file():
            raise FileNotFoundError("Голосовой профиль не найден.")

        shutil.rmtree(folder)
