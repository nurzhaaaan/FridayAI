import whisper
import pyttsx3
import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav

# Whisper модельін жүктеу
model = whisper.load_model("base")

# TTS engine
engine = pyttsx3.init()

def record_audio(filename="user_audio.wav", duration=5, fs=44100):
    print("Сөйлей беріңіз...")
    recording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
    sd.wait()
    wav.write(filename, fs, recording)
    print("Дауыс жазылды.")
    return filename

def listen(filename="user_audio.wav"):
    record_audio(filename)
    result = model.transcribe(filename)
    return result["text"]

def speak(text):
    engine.say(text)
    engine.runAndWait()
