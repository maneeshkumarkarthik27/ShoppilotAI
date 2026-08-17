import os
import uuid
import requests
from requests.auth import HTTPBasicAuth
from gtts import gTTS
from google import genai
from config.settings import GEMINI_API_KEY, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN

ai_client = genai.Client(api_key=GEMINI_API_KEY)

# Ensure static/audio folder exists to serve audio files
AUDIO_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

def transcribe_whatsapp_audio(media_url: str) -> str:
    """Downloads voice notes and transcribes native regional languages."""
    try:
        if not media_url:
            return ""
        response = requests.get(media_url, auth=HTTPBasicAuth(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
        if response.status_code != 200:
            return ""

        audio_bytes = response.content
        result = ai_client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[
                {
                    "inline_data": {
                        "mime_type": "audio/ogg",
                        "data": audio_bytes
                    }
                },
                "Transcribe this voice message accurately into text. "
                "The user is speaking an Indian regional language (Tamil, Hindi, Telugu, etc.) or English. "
                "Output ONLY the transcribed text."
            ]
        )
        return result.text.strip()
    except Exception as e:
        print(f"❌ Audio transcription error: {e}")
        return ""

def text_to_audio_file(text: str, lang_code: str = "ta") -> str:
    """Converts native script text into an MP3 file and returns the filename."""
    try:
        # Supported gTTS codes: 'ta', 'hi', 'te', 'kn', 'ml', 'en'
        valid_lang = lang_code if lang_code in ["ta", "hi", "te", "kn", "ml", "en"] else "en"
        filename = f"reply_{uuid.uuid4().hex[:8]}.mp3"
        filepath = os.path.join(AUDIO_DIR, filename)
        
        tts = gTTS(text=text, lang=valid_lang, slow=False)
        tts.save(filepath)
        return filename
    except Exception as e:
        print(f"❌ TTS Error: {e}")
        return ""