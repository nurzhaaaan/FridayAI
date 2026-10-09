"""Native Qt desktop GUI. No web server and no browser."""

import html
from pathlib import Path
import platform
import subprocess
import tempfile
import threading
import time
from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QPlainTextEdit,
    QLineEdit,
    QComboBox,
    QCheckBox,
    QFileDialog,
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QInputDialog,
    QTreeView,
    QTabWidget,
    QFileSystemModel,
)
from .hud import Reactor
from .agent import Agent, Model
from .tools import Workspace, applications, open_application
from .voice import Microphone, Transcriber
from . import storage

STYLE = """
QWidget {background:#07121d;color:#c6e5ef;font-size:12px;font-family:"Helvetica Neue";}
QMainWindow {background:#07121d;}
QWidget#panel {border:1px solid #193b4c;background:#0a1825;border-radius:3px;}
QLabel#title {font-size:26px;font-weight:600;color:#65e8ff;letter-spacing:5px;}
QLabel#sub {color:#6593a6;font-size:10px;}
QLabel#section {color:#54d5ee;font-size:11px;font-weight:600;padding:8px 0;}
QPushButton {border:1px solid #225268;border-radius:3px;padding:10px;background:#0d2332;color:#b9e8f4;}
QPushButton:hover {border-color:#65e8ff;background:#123447;}
QPushButton:disabled {color:#496372;border-color:#182e3c;}
QPushButton#send {background:#53d8ef;color:#071c28;font-weight:600;}
QTextBrowser,QPlainTextEdit,QLineEdit,QComboBox,QTreeView {border:1px solid #193b4c;border-radius:3px;padding:8px;background:#081420;selection-background-color:#245b70;}
QComboBox QAbstractItemView {background:#102635;color:#c6e5ef;}
QTreeView {font-size:11px;}
QTabWidget::pane {border:0;}
QTabBar::tab {background:#0b1e2c;color:#6f9bac;padding:10px;border-bottom:1px solid #193b4c;}
QTabBar::tab:selected {color:#65e8ff;border-bottom:2px solid #65e8ff;}
QScrollBar:vertical {background:#081420;width:7px;}
QScrollBar::handle:vertical {background:#245268;min-height:25px;}
"""


class Bridge(QObject):
    answer = Signal(str, str)
    failure = Signal(str)
    progress = Signal(str)
    approval = Signal(object)
    transcript = Signal(str)
    speech_done = Signal()


class ApprovalRequest:
    def __init__(self, proposal):
        self.proposal = proposal
        self.event = threading.Event()
        self.accepted = False


def friendly_error(exc):
    if isinstance(exc, TypeError):
        # Parameter/type failures need their message to diagnose incompatible wheels.
        import re

        detail = re.sub(r"sk-[A-Za-z0-9_-]+", "[hidden]", str(exc))[:350]
        return "TypeError: " + detail
    if isinstance(exc, (ValueError, InterruptedError)):
        return str(exc)
    names = {
        "AuthenticationError": "API кілті жарамсыз.",
        "RateLimitError": "API лимиті немесе баланс шектеуі.",
        "URLError": "Ollama қолжетімсіз. Ollama қолданбасын ашып, модельді жүктеңіз.",
        "HTTPError": "Модель сұрауды қабылдамады. Ollama моделін немесе API баптауын тексеріңіз.",
        "APITimeoutError": "AI жауап беру уақыты аяқталды.",
        "PortAudioError": "Микрофон қолжетімсіз. Mac Privacy & Security → Microphone рұқсатын тексеріңіз.",
    }
    return names.get(type(exc).__name__, "Операция орындалмады: " + type(exc).__name__)


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Friday — Mac AI Assistant")
        self.resize(1320, 850)
        saved = storage.load()
        prefs = saved.get("settings", {})
        self.history = (
            [
                m
                for m in saved.get("history", [])
                if isinstance(m, dict)
                and m.get("role") in ("user", "assistant")
                and isinstance(m.get("content"), str)
            ]
            if isinstance(saved.get("history", []), list)
            else []
        )
        self.workspace = Workspace()
        self.busy = False
        self.closing = False
        self.cancel = threading.Event()
        self.pending_approval = None
        self.microphone = Microphone()
        self.transcriber = Transcriber()
        self.recording = False
        self.speech_process = None
        self.speech_epoch = 0
        self.speech_lock = threading.Lock()
        self.bridge = Bridge(self)
        self.bridge.answer.connect(self.received)
        self.bridge.failure.connect(self.failed)
        self.bridge.progress.connect(self.progress)
        self.bridge.approval.connect(self.show_approval)
        self.bridge.transcript.connect(self.transcribed)
        self.bridge.speech_done.connect(lambda: self.progress("Дауыс аяқталды."))
        container = QWidget()
        self.setCentralWidget(container)
        outer = QVBoxLayout(container)
        outer.setContentsMargins(22, 16, 22, 16)
        header = QHBoxLayout()
        title = QLabel("F R I D A Y")
        title.setObjectName("title")
        header.addWidget(title)
        subtitle = QLabel("PERSONAL INTELLIGENCE  /  MAC DESKTOP")
        subtitle.setObjectName("sub")
        header.addWidget(subtitle)
        header.addStretch()
        self.service_label = QLabel()
        self.service_label.setObjectName("section")
        header.addWidget(self.service_label)
        outer.addLayout(header)
        layout = QHBoxLayout()
        layout.setSpacing(16)
        outer.addLayout(layout, 1)
        side = QWidget()
        side.setObjectName("panel")
        side.setFixedWidth(240)
        left = QVBoxLayout(side)
        section = QLabel("01 / ЖҰМЫС КЕҢІСТІГІ")
        section.setObjectName("section")
        left.addWidget(section)
        self.folder_label = QLabel("Жұмыс папкасы таңдалмаған")
        self.folder_label.setWordWrap(True)
        left.addWidget(self.folder_label)
        for attr, text, callback in (
            ("folder_button", "＋  Папканы таңдау", self.pick_folder),
            ("finder_button", "↗  Finder ішінде ашу", self.open_finder),
            ("apps_button", "▦  Қолданбаны ашу", self.pick_app),
            ("file_button", "⌕  Файлды талдау", self.pick_file),
        ):
            button = QPushButton(text)
            button.clicked.connect(callback)
            setattr(self, attr, button)
            left.addWidget(button)
        self.tree = QTreeView()
        self.tree.setMinimumHeight(130)
        self.fs = QFileSystemModel(self)
        self.tree.setModel(self.fs)
        for column in (1, 2, 3):
            self.tree.hideColumn(column)
        self.tree.doubleClicked.connect(self.tree_selected)
        left.addWidget(self.tree, 1)
        self.settings_button = QPushButton("⚙  Баптаулар")
        self.settings_button.clicked.connect(self.settings_dialog)
        left.addWidget(self.settings_button)
        self.clear_button = QPushButton("Әңгіме тарихын өшіру")
        self.clear_button.clicked.connect(self.clear_history)
        left.addWidget(self.clear_button)
        hint = QLabel("Таңдалған папкаға қолжетімділік.\nФайл өзгерісін сіз растайсыз.")
        hint.setWordWrap(True)
        hint.setObjectName("sub")
        left.addWidget(hint)
        layout.addWidget(side)
        center = QWidget()
        center.setObjectName("panel")
        body = QVBoxLayout(center)
        label = QLabel("02 / INTELLIGENCE CORE")
        label.setObjectName("section")
        body.addWidget(label)
        self.reactor = Reactor()
        body.addWidget(self.reactor, 1)
        self.status = QLabel("Дайын. Папканы және AI қызметін таңдаңыз.")
        self.status.setWordWrap(True)
        body.addWidget(self.status)
        voice = QHBoxLayout()
        self.mic_button = QPushButton("● Дауыспен айту")
        self.mic_button.clicked.connect(self.toggle_recording)
        voice.addWidget(self.mic_button)
        self.stop_button = QPushButton("■ Тоқтату")
        self.stop_button.clicked.connect(self.stop)
        voice.addWidget(self.stop_button)
        body.addLayout(voice)
        self.speak_check = QCheckBox("Жауапты дауыстап оқу")
        self.speak_check.setChecked(prefs.get("speak", True))
        body.addWidget(self.speak_check)
        self.test_voice_button = QPushButton("♫ Дыбысты тексеру")
        self.test_voice_button.clicked.connect(self.test_voice)
        body.addWidget(self.test_voice_button)
        self.input = QPlainTextEdit()
        self.input.setMaximumHeight(100)
        self.input.setPlaceholderText(
            "Тапсырма беріңіз…\nМысалы: PDF-ті оқып, қорытындысын summary.md файлына жаз"
        )
        body.addWidget(self.input)
        self.send_button = QPushButton("ТАПСЫРМАНЫ ОРЫНДА  →")
        self.send_button.setObjectName("send")
        self.send_button.clicked.connect(self.submit)
        body.addWidget(self.send_button)
        layout.addWidget(center, 5)
        right = QWidget()
        right.setObjectName("panel")
        right.setMinimumWidth(290)
        log = QVBoxLayout(right)
        label = QLabel("03 / СЕАНС ЖУРНАЛЫ")
        label.setObjectName("section")
        log.addWidget(label)
        tabs = QTabWidget()
        self.chat = QTextBrowser()
        self.chat.setOpenExternalLinks(False)
        tabs.addTab(self.chat, "Әңгіме")
        self.events = QPlainTextEdit()
        self.events.setReadOnly(True)
        self.events.setPlaceholderText("Орындалған әрекеттер осы жерде көрсетіледі")
        tabs.addTab(self.events, "Әрекеттер")
        log.addWidget(tabs)
        layout.addWidget(right, 4)
        footer = QLabel("FRIDAY  /  ДАУЫС · ФАЙЛДАР · ҚОЛДАНБАЛАР")
        footer.setObjectName("sub")
        outer.addWidget(footer)
        self.provider = (
            prefs.get("provider", "ollama")
            if prefs.get("provider") in ("ollama", "openai")
            else "ollama"
        )
        self.model_name = prefs.get("model") or (
            "qwen3:4b" if self.provider == "ollama" else "gpt-4o-mini"
        )
        self.language = (
            prefs.get("language", "kk")
            if prefs.get("language") in ("kk", "ru", "en")
            else "kk"
        )
        self.service_label.setText(self.provider.upper() + "  /  " + self.model_name)
        self.key = ""
        folder = prefs.get("folder")
        if isinstance(folder, str) and Path(folder).is_dir():
            try:
                self.set_folder(folder)
            except ValueError:
                self.folder_label.setText("Жұмыс папкасын қайта таңдаңыз.")
        self.render_history()
        if not self.history:
            self.add_message(
                "assistant",
                "Сәлем! Мен Friday. Папканы таңдаңыз, содан кейін файлды талдау, нәтиже жазу немесе қолданба ашу туралы тапсырма беріңіз. Жергілікті AI үшін Ollama-да qwen3:4b моделін жүктеңіз. Дауыс тану моделі бірінші рет жүктеледі.",
            )
        self.voice_monitor = QTimer(self)
        self.voice_monitor.setInterval(100)
        self.voice_monitor.timeout.connect(self.monitor_recording)
        self.record_timer = QTimer(self)
        self.record_timer.setSingleShot(True)
        self.record_timer.timeout.connect(self.toggle_recording)
        self.speak_check.toggled.connect(self.persist)

    def settings(self):
        return {
            "provider": self.provider,
            "model": self.model_name,
            "language": self.language,
            "folder": str(self.workspace.root) if self.workspace.root else "",
            "speak": self.speak_check.isChecked(),
        }

    def persist(self):
        try:
            storage.save(self.settings(), self.history)
        except OSError:
            self.status.setText("Тарихты сақтау мүмкін болмады.")

    def set_folder(self, path):
        if not isinstance(path, (str, Path)) or not str(path).strip():
            raise ValueError("Жұмыс папкасы таңдалмаған. Папканы қайта таңдаңыз.")
        self.workspace = Workspace(path)
        self.folder_label.setText(str(self.workspace.root))
        self.fs.setRootPath(str(self.workspace.root))
        self.tree.setRootIndex(self.fs.index(str(self.workspace.root)))
        self.persist()

    def pick_folder(self):
        path = QFileDialog.getExistingDirectory(
            self, "Friday жұмыс папкасы", str(self.workspace.root or Path.home())
        )
        if path:
            try:
                self.set_folder(path)
            except ValueError as exc:
                self.failed(str(exc))

    def open_finder(self):
        try:
            self.workspace.open_folder(".")
            self.progress("Finder папканы ашты.")
        except Exception as exc:
            self.failed(friendly_error(exc))

    def pick_app(self):
        names = sorted(applications())
        if not names:
            return self.failed("Mac қолданбалары табылмады.")
        name, ok = QInputDialog.getItem(
            self, "Қолданбаны ашу", "Қолданба", names, editable=False
        )
        if ok:
            try:
                open_application(name)
                self.progress("Ашылды: " + name)
            except Exception as exc:
                self.failed(friendly_error(exc))

    def pick_file(self):
        if not self.workspace.root:
            return self.pick_folder()
        file, _ = QFileDialog.getOpenFileName(
            self,
            "Талдауға файл таңдау",
            str(self.workspace.root),
            "Documents (*.txt *.md *.pdf *.docx *.csv *.json *.py *.js *.swift);;All files (*)",
        )
        if file:
            self.select_file(file)

    def tree_selected(self, index):
        path = self.fs.filePath(index)
        if Path(path).is_file():
            self.select_file(path)

    def select_file(self, path):
        try:
            relative = self.workspace.path(path).relative_to(self.workspace.root)
        except ValueError as exc:
            return self.failed(str(exc))
        self.input.setPlainText(f"Осы файлды оқып, мазмұнын талда: {relative}")

    def add_message(self, role, text):
        name = "Сіз" if role == "user" else "Friday"
        color = "#9bc5e7" if role == "user" else "#a3eed7"
        escaped = html.escape(text).replace("\n", "<br>")
        self.chat.append(
            f'<p style="color:{color};font-weight:bold">{name}</p><p>{escaped}</p><hr>'
        )
        self.chat.verticalScrollBar().setValue(self.chat.verticalScrollBar().maximum())

    def render_history(self):
        self.chat.clear()
        for message in self.history:
            self.add_message(message["role"], message["content"])

    def set_busy(self, value):
        self.busy = value
        for widget in (
            self.send_button,
            self.mic_button,
            self.folder_button,
            self.finder_button,
            self.apps_button,
            self.file_button,
            self.settings_button,
            self.clear_button,
        ):
            widget.setEnabled(not value)

    def emit(self, signal, *args):
        if not self.closing:
            try:
                signal.emit(*args)
            except RuntimeError:
                pass

    def submit(self):
        if self.busy:
            return
        prompt = self.input.toPlainText().strip()
        if not prompt:
            return
        if self.recording:
            return self.failed("Алдымен дыбыс жазуды тоқтатыңыз.")
        self.stop_speech()
        self.input.clear()
        self.add_message("user", prompt)
        history = list(self.history)
        self.history.append({"role": "user", "content": prompt})
        self.persist()
        self.cancel = threading.Event()
        self.set_busy(True)
        self.progress("Friday тапсырманы зерттеуде…")
        workspace = self.workspace
        model = Model(self.provider, self.model_name, self.key)
        cancel = self.cancel

        def task():
            try:
                agent = Agent(
                    workspace,
                    model,
                    self.approve,
                    lambda value: self.emit(self.bridge.progress, value),
                    cancel,
                )
                answer = agent.run(prompt, history)
                self.emit(self.bridge.answer, prompt, answer)
            except Exception as exc:
                self.emit(self.bridge.failure, friendly_error(exc))

        threading.Thread(target=task, daemon=True).start()

    def approve(self, proposal):
        request = ApprovalRequest(proposal)
        self.pending_approval = request
        self.emit(self.bridge.approval, request)
        deadline = time.monotonic() + 180
        while not request.event.wait(0.2):
            if self.cancel.is_set() or self.closing or time.monotonic() > deadline:
                return False
        return request.accepted

    def show_approval(self, request):
        if self.cancel.is_set() or self.closing:
            request.event.set()
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Файл өзгерісін растау")
        dialog.resize(850, 620)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Файл: " + request.proposal.path))
        tabs = QTabWidget()
        for label, text in [
            ("Өзгерістер", request.proposal.preview()),
            ("Ұсынылған толық мәтін", request.proposal.content),
            ("Қазіргі мәтін", request.proposal.previous or "(Жаңа файл)"),
        ]:
            view = QPlainTextEdit()
            view.setReadOnly(True)
            view.setPlainText(text)
            tabs.addTab(view, label)
        layout.addWidget(tabs)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(
            "Осы өзгерісті сақтау"
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        request.accepted = (
            dialog.exec() == QDialog.DialogCode.Accepted and not self.cancel.is_set()
        )
        request.event.set()
        self.pending_approval = None

    def received(self, prompt, answer):
        if self.cancel.is_set():
            self.set_busy(False)
            self.progress("Тапсырма тоқтатылды.")
            return
        self.history.append({"role": "assistant", "content": answer})
        self.add_message("assistant", answer)
        self.persist()
        self.set_busy(False)
        self.progress("Тапсырма аяқталды.")
        if self.speak_check.isChecked():
            self.say(answer)

    def failed(self, message):
        self.set_busy(False)
        self.progress("Қате: " + message)

    def progress(self, message):
        self.status.setText(message)
        self.events.appendPlainText(message)
        state = "listening" if self.recording else "thinking" if self.busy else "idle"
        if message.startswith("Қате:"):
            state = "error"
        elif message == "Жауап дауыстап оқылуда.":
            state = "speaking"
        self.reactor.set_state(state)

    def settings_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Friday баптаулары")
        dialog.resize(500, 380)
        layout = QVBoxLayout(dialog)
        provider = QComboBox()
        provider.addItem("Жергілікті Ollama (кілтсіз)", "ollama")
        provider.addItem("OpenAI (бұлт)", "openai")
        provider.setCurrentIndex(0 if self.provider == "ollama" else 1)
        model = QLineEdit(self.model_name)
        key = QLineEdit(self.key)
        key.setEchoMode(QLineEdit.EchoMode.Password)
        key.setPlaceholderText("API кілті тек осы сеансқа сақталады")
        language = QComboBox()
        language.addItem("Қазақша", "kk")
        language.addItem("Русский", "ru")
        language.addItem("English", "en")
        language.setCurrentIndex(("kk", "ru", "en").index(self.language))
        for label, widget in [
            ("AI қызметі", provider),
            ("Модель", model),
            ("OpenAI API кілті", key),
            ("Дауыс тану тілі", language),
        ]:
            layout.addWidget(QLabel(label))
            layout.addWidget(widget)
        provider.currentIndexChanged.connect(
            lambda index: model.setText("qwen3:4b" if index == 0 else "gpt-4o-mini")
        )
        note = QLabel(
            "Ollama: файл мәтіні жергілікті модельге жіберіледі.\nOpenAI: файл мәтіні мен дыбыс OpenAI-ға жіберіледі.\nЖергілікті дауыс тану моделі бірінші рет интернеттен жүктеледі."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.provider = provider.currentData()
            self.model_name = model.text().strip() or (
                "qwen3:4b" if self.provider == "ollama" else "gpt-4o-mini"
            )
            self.key = key.text().strip()
            self.language = language.currentData()
            self.service_label.setText(
                self.provider.upper() + "  /  " + self.model_name
            )
            self.persist()

    def toggle_recording(self):
        if self.busy:
            return
        if not self.recording:
            self.stop_speech()
            try:
                self.microphone.start()
            except Exception as exc:
                return self.failed(friendly_error(exc))
            for widget in (
                self.folder_button,
                self.finder_button,
                self.apps_button,
                self.file_button,
                self.settings_button,
                self.clear_button,
            ):
                widget.setEnabled(False)
            self.recording = True
            self.mic_button.setText("■ Жазуды тоқтатып жіберу")
            self.send_button.setEnabled(False)
            self.record_timer.start(60000)
            self.voice_monitor.start()
            self.progress(
                "Тыңдап тұрмын. Бұйрықты айтыңыз; сөйлеу аяқталғанда автоматты жіберіледі."
            )
            return
        self.record_timer.stop()
        self.voice_monitor.stop()
        self.recording = False
        self.mic_button.setText("● Дауыспен айту")
        try:
            audio = self.microphone.stop()
        except Exception as exc:
            return self.failed(friendly_error(exc))
        self.set_busy(True)
        self.cancel = threading.Event()
        cancel = self.cancel
        provider, key, language = self.provider, self.key, self.language
        self.progress("Дыбыс мәтінге айналуда. Бірінші рет модель жүктелуі мүмкін…")

        def task():
            try:
                text = self.transcriber.transcribe(audio, provider, key, language)
                if not cancel.is_set():
                    self.emit(self.bridge.transcript, text)
                else:
                    self.emit(self.bridge.failure, "Тоқтатылды.")
            except Exception as exc:
                self.emit(self.bridge.failure, "Дауыс тану: " + friendly_error(exc))

        threading.Thread(target=task, daemon=True).start()

    def monitor_recording(self):
        if not self.recording:
            self.voice_monitor.stop()
            return
        state = self.microphone.recording_state()
        if state == "complete":
            self.toggle_recording()
        elif state == "silent":
            self.stop()
            self.failed(
                "Микрофон дыбыс қабылдамады. System Settings → Sound → Input ішінде микрофонды таңдаңыз және Privacy & Security → Microphone рұқсатын тексеріңіз."
            )

    def transcribed(self, text):
        self.set_busy(False)
        self.input.setPlainText(text)
        self.progress("Танылған бұйрық: " + text)
        if text.casefold().strip(" .!?") in ("тоқта", "стоп", "stop"):
            self.stop()
            return
        self.submit()

    def test_voice(self):
        if self.recording or self.busy:
            return self.progress("Алдымен жазбаны немесе тапсырманы тоқтатыңыз.")
        self.say("Сәлем! Friday дауысы жұмыс істейді.")

    def say(self, text):
        if platform.system() != "Darwin":
            return self.progress("Жүйелік дауыс тек Mac-та қолжетімді.")
        self.stop_speech()
        self.progress("Жауап дауыстап оқылуда.")
        epoch = self.speech_epoch
        language = self.language

        def task():
            try:
                from mac_speech import select_voice

                voice, locale = select_voice(
                    {"kk": "kk-KZ", "ru": "ru-RU", "en": "en-US"}[language]
                )
                if locale[:2] != language:
                    self.emit(
                        self.bridge.progress,
                        "Таңдалған тілде жүйелік дауыс жоқ; қолданылатын дауыс: "
                        + locale,
                    )
                with tempfile.TemporaryDirectory(prefix="friday-say-") as directory:
                    file = Path(directory) / "text.txt"
                    file.write_text(text, encoding="utf-8")
                    with self.speech_lock:
                        if self.closing or epoch != self.speech_epoch:
                            return
                        process = subprocess.Popen(
                            ["/usr/bin/say", "-v", voice, "-f", str(file)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                        self.speech_process = process
                    try:
                        code = process.wait(timeout=180)
                        if code:
                            raise ValueError(
                                "Mac say дыбыстай алмады (код "
                                + str(code)
                                + "). System Settings → Sound → Output құрылғысы мен дыбыс деңгейін тексеріңіз."
                            )
                    finally:
                        if process.poll() is None:
                            process.kill()
                            process.wait()
                        with self.speech_lock:
                            if self.speech_process is process:
                                self.speech_process = None
                if epoch == self.speech_epoch:
                    self.emit(self.bridge.speech_done)
            except Exception as exc:
                self.emit(
                    self.bridge.progress, "Дыбыстау қатесі: " + friendly_error(exc)
                )

        threading.Thread(target=task, daemon=True).start()

    def stop_speech(self):
        with self.speech_lock:
            self.speech_epoch += 1
            process = self.speech_process
            self.speech_process = None
        if process and process.poll() is None:
            process.terminate()

    def stop(self):
        self.cancel.set()
        self.stop_speech()
        if self.pending_approval:
            self.pending_approval.event.set()
        if self.recording:
            self.microphone.close()
            self.recording = False
            self.record_timer.stop()
            self.voice_monitor.stop()
            self.mic_button.setText("● Дауыспен айту")
            self.set_busy(False)
        self.progress("Тоқтату сұралды. Орындалған өзгерістер автоматты қайтарылмайды.")

    def clear_history(self):
        if (
            QMessageBox.question(self, "Тарих", "Әңгіме тарихын өшіру керек пе?")
            == QMessageBox.StandardButton.Yes
        ):
            self.history = []
            self.render_history()
            self.persist()

    def closeEvent(self, event):
        self.closing = True
        self.voice_monitor.stop()
        self.record_timer.stop()
        self.cancel.set()
        self.microphone.close()
        self.stop_speech()
        if self.pending_approval:
            self.pending_approval.event.set()
        self.persist()
        event.accept()


def main():
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("Friday")
    app.setStyleSheet(STYLE)
    window = Window()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
