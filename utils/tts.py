import pyttsx3
import uuid

def text_to_speech(text):
    engine = pyttsx3.init()
    audio_filename = f"static/audio/{uuid.uuid4()}.mp3"
    engine.save_to_file(text, audio_filename)
    engine.runAndWait()
    return f"/{audio_filename}"
