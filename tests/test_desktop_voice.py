import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave
from types import SimpleNamespace
from desktop.voice import Microphone, Transcriber
from desktop import storage


class DesktopVoiceTests(unittest.TestCase):
    @patch("sounddevice.RawInputStream")
    @patch("sounddevice.query_devices", return_value={"default_samplerate": 48000})
    def test_recording_produces_valid_wav(self, query, stream):
        mic = Microphone()
        mic.start()
        callback = stream.call_args.kwargs["callback"]
        callback(b"\0\0" * 480, 480, None, None)
        with wave.open(io.BytesIO(mic.stop()), "rb") as audio:
            self.assertEqual(audio.getframerate(), 48000)
            self.assertEqual(audio.getnframes(), 480)
            self.assertEqual(audio.getnchannels(), 1)
        stream.return_value.stop.assert_called_once()
        stream.return_value.close.assert_called_once()

    @patch("faster_whisper.WhisperModel")
    def test_local_transcription_path_and_model_reuse(self, model):
        model.return_value.transcribe.return_value = (
            [SimpleNamespace(text="Сәлем Friday")],
            None,
        )
        with (
            tempfile.TemporaryDirectory() as home,
            patch("desktop.voice.Path.home", return_value=Path(home)),
        ):
            transcriber = Transcriber()
            self.assertEqual(
                transcriber.transcribe(b"audio", "ollama", language="kk"),
                "Сәлем Friday",
            )
            self.assertEqual(
                transcriber.transcribe(b"audio", "ollama", language="kk"),
                "Сәлем Friday",
            )
            model.assert_called_once()
            self.assertEqual(model.call_args.args[0], "small")
            self.assertFalse(
                Path(model.return_value.transcribe.call_args.args[0]).exists()
            )

    def test_private_storage_never_persists_keys(self):
        with (
            tempfile.TemporaryDirectory() as home,
            patch("desktop.storage.directory", return_value=Path(home)),
        ):
            storage.save(
                {"provider": "openai", "key": "private-key-test", "model": "test"},
                [{"role": "user", "content": "Hello"}],
            )
            raw = (Path(home) / "workspace.json").read_text()
            self.assertNotIn("private-key-test", raw)
            self.assertNotIn('"key"', raw)
            self.assertEqual(storage.load()["history"][0]["content"], "Hello")
            self.assertEqual(
                (Path(home) / "workspace.json").stat().st_mode & 0o777, 0o600
            )
