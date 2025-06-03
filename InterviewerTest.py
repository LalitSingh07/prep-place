from flask import Flask, render_template, request, jsonify, send_from_directory
from utils.groq_llm import ask_groq
from utils.tts import text_to_speech
from utils.stt import speech_to_text
import os

app = Flask(__name__)

# Serve generated audio files from static/audio
@app.route('/static/audio/<filename>')
def serve_audio(filename):
    return send_from_directory('static/audio', filename)

# Landing page
@app.route('/')
def index():
    return render_template('index.html')

# Interviewer chat page
@app.route('/interview')
def interview():
    return render_template('interview.html')

# Handle text input in interview chat
@app.route('/send_message', methods=['POST'])
def send_message():
    user_input = request.json.get('message')

    # Get response from Groq LLM
    ai_response = ask_groq(user_input)

    # Convert response to speech
    audio_path = text_to_speech(ai_response)

    return jsonify({
        'response': ai_response,
        'audio_url': audio_path
    })


# Handle audio input in interview chat
@app.route('/audio_input', methods=['POST'])
def audio_input():
    audio_file = request.files['audio']
    
    # Convert audio to text
    user_text = speech_to_text(audio_file)

    # Get LLM response
    ai_response = ask_groq(user_text)

    # Convert response to speech
    audio_path = text_to_speech(ai_response)

    return jsonify({
        'user_text': user_text,  
        'response': ai_response,
        'audio_url': audio_path
    })

if __name__ == '__main__':
    if not os.path.exists('static/audio'):
        os.makedirs('static/audio')
    app.run(debug=True)
