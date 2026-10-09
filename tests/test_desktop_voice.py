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

    @patch("sounddevice.RawInputStream")
    @patch("sounddevice.query_devices", return_value={"default_samplerate": 16000})
    def test_speech_then_silence_completes_but_background_silence_does_not(
        self, query, stream
    ):
        with patch("desktop.voice.time.monotonic", return_value=100) as clock:
            mic = Microphone()
            mic.start()
            callback = stream.call_args.kwargs["callback"]
            callback(b"\0\0" * 160, 160, None, None)
            clock.return_value = 105
            self.assertEqual(mic.recording_state(), "listening")
            callback(b"\x00\x10" * 160, 160, None, None)
            clock.return_value = 106
            self.assertEqual(mic.recording_state(), "listening")
            callback(b"\0\0" * 160, 160, None, None)
            clock.return_value = 107
            self.assertEqual(mic.recording_state(), "complete")
            mic.close()
            mic.start()
            clock.return_value = 120
            self.assertEqual(mic.recording_state(), "silent")
            mic.close()

    @patch(
        "faster_whisper.WhisperModel",
        side_effect=TypeError("unexpected keyword argument test_option"),
    )
    def test_incompatible_voice_dependency_is_actionable(self, model):
        with (
            tempfile.TemporaryDirectory() as home,
            patch("desktop.voice.Path.home", return_value=Path(home)),
        ):
            with self.assertRaisesRegex(ValueError, "test_option.*start.command"):
                Transcriber().transcribe(b"audio", "ollama")
