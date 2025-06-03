import speech_recognition as sr
from pydub import AudioSegment
import tempfile
import os

def speech_to_text(audio_file):
    # Save uploaded file to a temporary file (e.g., webm/ogg)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_audio:
        audio_file.save(temp_audio.name)
        temp_audio_path = temp_audio.name

    # Convert to WAV using pydub
    audio = AudioSegment.from_file(temp_audio_path)
    wav_path = tempfile.mktemp(suffix=".wav")
    audio.export(wav_path, format="wav")

    recognizer = sr.Recognizer()

    try:
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            try:
                return recognizer.recognize_google(audio_data)
            except sr.UnknownValueError:
                return "Sorry, I couldn't understand."
    finally:
        for f in [temp_audio_path, wav_path]:
            try:
                os.remove(f)
            except OSError:
                pass  # Ignore if already deleted or error

