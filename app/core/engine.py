from pathlib import Path

import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel
from app.paths import get_model_path


MODEL_PATH = get_model_path()


class VoiceEngine:
    def __init__(self):
        self.model = None

    def load_model(self):
        if self.model is not None:
            return

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA не обнаружена. Проверь драйвер NVIDIA.")

        model_path = get_model_path()
        if not model_path.exists():
            raise FileNotFoundError(
                "Модель Qwen3-TTS не найдена. Откройте Настройки и укажите папку "
                f"Qwen3-TTS-12Hz-0.6B-Base. Текущий путь: {model_path}"
            )

        self.model = Qwen3TTSModel.from_pretrained(
            str(model_path),
            device_map="cuda:0",
            dtype=torch.float32,
            attn_implementation="sdpa",
        )

    def create_profile(self, audio_path: str, reference_text: str):
        self.load_model()

        audio = Path(audio_path)
        if not audio.is_file():
            raise FileNotFoundError(f"Аудиофайл не найден: {audio}")

        if not reference_text.strip():
            raise ValueError("Нужно указать текст образца голоса.")

        prompts = self.model.create_voice_clone_prompt(
            ref_audio=str(audio),
            ref_text=reference_text.strip(),
            x_vector_only_mode=False,
        )

        return prompts[0]

    def synthesize(self, text: str, voice_prompt, output_path: str):
        self.load_model()

        if not text.strip():
            raise ValueError("Введите текст для озвучивания.")

        wavs, sample_rate = self.model.generate_voice_clone(
            text=text.strip(),
            language="Russian",
            voice_clone_prompt=[voice_prompt],
            do_sample=True,
            top_k=50,
            top_p=1.0,
            temperature=0.9,
            subtalker_dosample=False,
            max_new_tokens=256,
        )

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        sf.write(str(output), wavs[0], sample_rate)
        return output
