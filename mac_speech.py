"""macOS local speech synthesis. No shell execution or external services."""
import platform
import re
import subprocess
import tempfile
from pathlib import Path


def available():
    return platform.system() == 'Darwin' and Path('/usr/bin/say').is_file() and Path('/usr/bin/afconvert').is_file()


def synthesize(text, language):
    if not available():
        raise RuntimeError('Mac дауысы тек macOS-та қолжетімді.')
    if not isinstance(text, str) or not text.strip() or len(text) > 12000:
        raise ValueError('Дыбысталатын мәтін бос немесе тым ұзын.')
    if language not in ('kk-KZ', 'ru-RU', 'en-US'):
        raise ValueError('Дауыс тілі қате.')
    listing = subprocess.run(['/usr/bin/say', '-v', '?'], capture_output=True, text=True, check=True, timeout=10).stdout
    voices = []
    for line in listing.splitlines():
        match = re.match(r'^(.+?)\s+([a-z]{2}_[A-Z]{2})\s+', line)
        if match:
            voices.append((match.group(1).strip(), match.group(2)))
    desired = language.replace('-', '_')
    selected = next((voice for voice in voices if voice[1] == desired), None)
    if selected is None:
        selected = next((v for v in voices if v[1] == 'ru_RU'), None) if language == 'kk-KZ' else None
        selected = selected or next((v for v in voices if v[1] == 'en_US'), None)
    if selected is None:
        raise RuntimeError('Mac-та дауыс табылмады. System Settings → Accessibility → Spoken Content бөлімінен дауыс орнатыңыз.')
    voice, locale = selected
    with tempfile.TemporaryDirectory(prefix='friday-speech-') as directory:
        path = Path(directory)
        source, aiff, wav = path/'input.txt', path/'speech.aiff', path/'speech.wav'
        source.write_text(text, encoding='utf-8')
        subprocess.run(['/usr/bin/say', '-v', voice, '-f', str(source), '-o', str(aiff)], check=True, capture_output=True, timeout=90)
        subprocess.run(['/usr/bin/afconvert', '-f', 'WAVE', '-d', 'LEI16', str(aiff), str(wav)], check=True, capture_output=True, timeout=20)
        audio = wav.read_bytes()
    if not audio.startswith(b'RIFF') or len(audio) < 44:
        raise RuntimeError('Mac дыбыс файлын жасай алмады.')
    return audio, locale
