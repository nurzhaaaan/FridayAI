"""Native microphone recording and local/cloud transcription."""

import io
import math
import struct
import time
from pathlib import Path
import tempfile
import threading
import wave


class Microphone:
    def __init__(self):
        self.stream = None
        self.frames = []
        self.rate = 16000
        self.samples = 0
        self.lock = threading.Lock()
        self.level = 0.0
        self.started_at = 0.0
        self.last_voice_at = None

    def start(self):
        import sounddevice as sd

        info = sd.query_devices(kind="input")
        self.rate = int(info["default_samplerate"])
        self.frames = []
        self.samples = 0
        self.level = 0.0
        self.started_at = time.monotonic()
        self.last_voice_at = None

        def callback(data, frames, timing, status):
            with self.lock:
                if self.samples < self.rate * 60:
                    raw = bytes(data)
                    values = struct.unpack("<" + "h" * (len(raw) // 2), raw)
                    self.level = (
                        math.sqrt(sum(v * v for v in values) / max(1, len(values)))
                        / 32768
                    )
                    if self.level >= 0.012:
                        self.last_voice_at = time.monotonic()
                    self.frames.append(raw)
                    self.samples += frames

        self.stream = sd.RawInputStream(
            samplerate=self.rate, channels=1, dtype="int16", callback=callback
        )
        try:
            self.stream.start()
        except Exception:
            self.stream.close()
            self.stream = None
            raise

    def recording_state(self):
        """Finish after speech followed by silence; never transcribe pure silence."""
        now = time.monotonic()
        with self.lock:
            if self.last_voice_at is not None:
                return "complete" if now - self.last_voice_at >= 1.8 else "listening"
            return "silent" if now - self.started_at >= 12 else "listening"

    def stop(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        with self.lock:
            raw = b"".join(self.frames)
        if not raw:
            raise ValueError("Микрофоннан дыбыс жазылмады.")
        out = io.BytesIO()
        with wave.open(out, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(self.rate)
            wav.writeframes(raw)
        return out.getvalue()

    def close(self):
        if self.stream:
            self.stream.abort()
            self.stream.close()
            self.stream = None


class Transcriber:
    def __init__(self):
        self.model = None
        self.lock = threading.Lock()

    def transcribe(self, audio, provider, key="", language="kk"):
        if provider == "openai":
            from openai import OpenAI
            import os

            key = (
                key
                or os.getenv("FRIDAY_API_KEY")
                or os.getenv("Nurzhik_06")
                or os.getenv("OPENAI_API_KEY")
            )
            if not key:
                raise ValueError("API кілті жоқ.")
            with OpenAI(api_key=key, timeout=90, max_retries=1) as client:
                result = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=("recording.wav", audio, "audio/wav"),
                    language=language,
                )
            text = result.text
        else:
            from faster_whisper import WhisperModel

            with self.lock:
                if self.model is None:
                    cache = Path.home() / "Library" / "Caches" / "Friday" / "whisper"
                    cache.mkdir(parents=True, exist_ok=True)
                    self.model = WhisperModel(
                        "small",
                        device="cpu",
                        compute_type="int8",
                        cpu_threads=4,
                        download_root=str(cache),
                    )
                with tempfile.TemporaryDirectory(
                    prefix="friday-recording-"
                ) as directory:
                    file = Path(directory) / "recording.wav"
                    file.write_bytes(audio)
                    segments, info = self.model.transcribe(
                        str(file), language=language, vad_filter=True
                    )
                    text = " ".join(segment.text for segment in segments)
        if not text.strip():
            raise ValueError("Сөз танылмады. Микрофон мен дауыс тілін тексеріңіз.")
        return text.strip()
