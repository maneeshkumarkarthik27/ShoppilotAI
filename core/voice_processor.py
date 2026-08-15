import os
import requests
from requests.auth import HTTPBasicAuth
from google import genai
from config.settings import GEMINI_API_KEY, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN

ai_client = genai.Client(api_key=GEMINI_API_KEY)

def transcribe_whatsapp_audio(media_url: str) -> str:
    """
    Downloads audio from Twilio using Basic Auth and sends 
    the raw audio bytes to Gemini to transcribe multilingual speech.
    """
    try:
        if not media_url:
            return ""

        # 1. Download WhatsApp voice recording (.ogg / .amr)
        response = requests.get(
            media_url, 
            auth=HTTPBasicAuth(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        )
        
        if response.status_code != 200:
            print(f"❌ Failed to download Twilio media file: Status {response.status_code}")
            return ""

        audio_bytes = response.content

        # 2. Transcribe voice directly using Gemini multimodal capabilities
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
                "The speaker might be using English, Tanglish, Tamil, or Hinglish. "
                "Output ONLY the transcribed text."
            ]
        )
        return result.text.strip()
    except Exception as e:
        print(f"❌ Error processing voice note: {e}")
        return ""