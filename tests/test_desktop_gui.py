import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtCore import QTimer
from desktop.app import Window, STYLE
from test_desktop_agent import ScriptedModel


class NativeGUItests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(STYLE)

    def wait(self, condition, timeout=5):
        deadline = time.monotonic() + timeout
        while not condition() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        self.assertTrue(condition(), "GUI operation did not finish")

    def test_native_window_task_approval_and_real_output(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("desktop.storage.load", return_value={}),
            patch("desktop.storage.save"),
            patch("desktop.app.Model", return_value=ScriptedModel()),
        ):
            root = Path(directory)
            (root / "brief.txt").write_text("Budget 900")
            window = Window()
            window.speak_check.setChecked(False)
            window.set_folder(root)
            window.show()
            self.app.processEvents()
            self.assertEqual(window.workspace.root, root)
            window.input.setPlainText("Read brief.txt and save summary.md")
            approvals = []

            def accept_review():
                for dialog in window.findChildren(QDialog):
                    if (
                        dialog.isVisible()
                        and dialog.windowTitle() == "Файл өзгерісін растау"
                    ):
                        self.assertFalse((root / "summary.md").exists())
                        approvals.append(dialog.windowTitle())
                        dialog.accept()

            timer = QTimer()
            timer.timeout.connect(accept_review)
            timer.start(20)
            window.submit()
            self.wait(lambda: not window.busy)
            timer.stop()
            self.assertEqual((root / "summary.md").read_text(), "Қорытынды: Budget 900")
            self.assertEqual(len(approvals), 1)
            self.assertIn("Сақталды", window.chat.toPlainText())
            self.assertIn("read_file", window.events.toPlainText())
            self.assertEqual(window.history[-1]["role"], "assistant")
            window.close()
            self.app.processEvents()

    def test_transcript_enters_agent_without_browser(self):
        with (
            patch("desktop.storage.load", return_value={}),
            patch("desktop.storage.save"),
        ):
            window = Window()
            with patch.object(window, "submit") as submit:
                window.transcribed("Calculator аш")
                self.assertEqual(window.input.toPlainText(), "Calculator аш")
                submit.assert_called_once()
            window.close()

    def test_reactor_tracks_recording_work_and_error(self):
        with (
            patch("desktop.storage.load", return_value={}),
            patch("desktop.storage.save"),
        ):
            window = Window()
            with (
                patch.object(window.microphone, "start"),
                patch.object(window.microphone, "close"),
            ):
                window.toggle_recording()
                self.assertEqual(window.reactor.state, "listening")
                self.assertFalse(window.send_button.isEnabled())
                window.stop()
                self.assertEqual(window.reactor.state, "idle")
            window.set_busy(True)
            window.progress("Орындалуда")
            self.assertEqual(window.reactor.state, "thinking")
            window.failed("Микрофон қолжетімсіз")
            self.assertEqual(window.reactor.state, "error")
            window.close()

    def test_voice_pause_transcribes_and_executes_without_second_click(self):
        with (
            patch("desktop.storage.load", return_value={}),
            patch("desktop.storage.save"),
        ):
            window = Window()
            window.speak_check.setChecked(False)
            with (
                patch.object(window.microphone, "start"),
                patch.object(
                    window.microphone, "stop", return_value=b"recorded-wav"
                ) as stop,
                patch.object(
                    window.microphone, "recording_state", return_value="complete"
                ),
                patch.object(
                    window.transcriber, "transcribe", return_value="Calculator аш"
                ) as transcribe,
                patch("desktop.app.Agent.run", return_value="Calculator ашылды") as run,
            ):
                window.toggle_recording()
                self.assertTrue(window.recording)
                window.monitor_recording()
                self.wait(
                    lambda: (
                        bool(window.history)
                        and window.history[-1]["role"] == "assistant"
                    )
                )
                stop.assert_called_once()
                transcribe.assert_called_once_with(b"recorded-wav", "ollama", "", "kk")
                self.assertEqual(run.call_args.args[0], "Calculator аш")
                self.assertIn(
                    "Танылған бұйрық: Calculator аш", window.events.toPlainText()
                )
                self.assertFalse(window.recording)
                self.assertFalse(window.voice_monitor.isActive())
                self.assertTrue(window.mic_button.isEnabled())
            window.close()

    def test_silent_microphone_stops_without_submitting(self):
        with (
            patch("desktop.storage.load", return_value={}),
            patch("desktop.storage.save"),
        ):
            window = Window()
            with (
                patch.object(window.microphone, "start"),
                patch.object(window.microphone, "close"),
                patch.object(
                    window.microphone, "recording_state", return_value="silent"
                ),
                patch.object(window, "submit") as submit,
            ):
                window.toggle_recording()
                window.monitor_recording()
                self.assertFalse(window.recording)
                self.assertIn("Микрофон дыбыс қабылдамады", window.status.text())
                submit.assert_not_called()
            window.close()

    def test_sound_check_does_not_require_ai_and_empty_folder_is_rejected(self):
        with (
            patch("desktop.storage.load", return_value={}),
            patch("desktop.storage.save"),
        ):
            window = Window()
            with patch.object(window, "say") as say:
                window.test_voice_button.click()
                say.assert_called_once_with("Сәлем! Friday дауысы жұмыс істейді.")
            for invalid in (None, "", False):
                with self.assertRaises(ValueError):
                    window.set_folder(invalid)
            self.assertIsNone(window.workspace.root)
            self.assertNotEqual(window.folder_label.text(), "None")
            window.close()
