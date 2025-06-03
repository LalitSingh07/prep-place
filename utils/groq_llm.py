import os
import requests

def ask_groq(prompt):
    """
    Send the prompt to Groq LLM API and return the response.
    """
    api_url = "https://api.groq.com/openai/v1/chat/completions"
    api_key = os.getenv("GROQ_API_KEY")  # Store your Groq API key in an environment variable

    if not api_key:
        return "API key not found. Please set the GROQ_API_KEY environment variable."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "llama3-8b-8192",
        "messages": [
            {"role": "system", "content": "You are a helpful and professional interviewer."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    try:
        response = requests.post(api_url, headers=headers, json=data, timeout=10)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx, 5xx)
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        return "Sorry, I couldn't generate a response at the moment due to a network error."

    try:
        result = response.json()
        return result["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, ValueError) as e:
        print(f"Parsing error: {e}")
        return "Sorry, I received an unexpected response from the server."

