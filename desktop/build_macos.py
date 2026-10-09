"""Build an actual native .app on the user's Mac; does not install or publish it."""

from pathlib import Path
import platform
import shutil


def build():
    if platform.system() != "Darwin":
        raise SystemExit("Mac-та жинаңыз: bash make-mac-app.command")
    import PyInstaller.__main__

    root = Path(__file__).resolve().parent.parent
    stage = root / ".desktop-build" / "source"
    stage.mkdir(parents=True, exist_ok=True)
    # Exclude stale committed Python/PortAudio artifacts from PyInstaller's search path.
    for name in ("desktop_entry.py", "ai_core.py", "mac_speech.py"):
        shutil.copy2(root / name, stage / name)
    shutil.copytree(
        root / "desktop",
        stage / "desktop",
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    spec = root / ".desktop-build" / "Friday.spec"
    spec.write_text(
        f"""from PyInstaller.utils.hooks import collect_all
packages = ['faster_whisper', 'ctranslate2', 'av', 'tokenizers', 'sounddevice', '_sounddevice_data', 'onnxruntime', 'pypdf']
datas, binaries, hiddenimports = [], [], []
for package in packages:
    data, binary, hidden = collect_all(package)
    datas += data; binaries += binary; hiddenimports += hidden
a = Analysis([{str(stage / "desktop_entry.py")!r}], pathex=[{str(stage)!r}], binaries=binaries, datas=datas, hiddenimports=hiddenimports, hookspath=[], hooksconfig={{}}, runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Friday', debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Friday')
app = BUNDLE(coll, name='Friday.app', bundle_identifier='kz.friday.assistant', info_plist={{'NSMicrophoneUsageDescription':'Friday uses the microphone only when you press the recording button.', 'LSMinimumSystemVersion':'12.0', 'NSHighResolutionCapable':True}})
""",
        encoding="utf-8",
    )
    PyInstaller.__main__.run(
        [
            "--noconfirm",
            "--clean",
            "--distpath",
            str(root / "dist"),
            "--workpath",
            str(root / ".desktop-build" / "work"),
            str(spec),
        ]
    )
    bundle = root / "dist" / "Friday.app"
    if not bundle.is_dir():
        raise SystemExit("Friday.app жасалмады.")
    print("Дайын:", bundle)
    print("Finder арқылы ашыңыз. Қалауыңызша Applications папкасына көшіріңіз.")


if __name__ == "__main__":
    build()
