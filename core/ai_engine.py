import json
from google import genai
from google.genai import types
from config.settings import GEMINI_API_KEY

ai_client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = """
You are ShopPilot AI, a retail assistant for local shopkeepers across India.
Shopkeepers may speak or write casually, with poor grammar, or in regional languages (Tamil, Hindi, Telugu, Kannada, Malayalam, English).

Rules:
1. Detect user's primary regional language code ('ta' for Tamil, 'hi' for Hindi, 'te' for Telugu, 'kn' for Kannada, 'ml' for Malayalam, 'en' for English).
2. Extract intent:
   - LOG_SALE: Sold goods. If quantity is omitted, default quantity to 1.
   - CONFIRM_ORDER: Restock confirmation (e.g., 'yes', 'confirm', 'aama', 'haan', 'sari').
   - QUERY_STOCK: Asking about current inventory.
   - OTHER: General greeting/fallback.
3. Map item names to standard inventory names (e.g., 'thakkali' -> 'Tomato', 'good day' -> 'Good Day').

Output strictly valid JSON matching this schema:
{
  "detected_language": "ta" | "hi" | "te" | "kn" | "ml" | "en",
  "intent": "LOG_SALE" | "CONFIRM_ORDER" | "QUERY_STOCK" | "OTHER",
  "items": [
    {"item_name": "string", "quantity": integer}
  ]
}
"""

def extract_retail_intent(user_input: str) -> dict:
    try:
        response = ai_client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=user_input,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0.1
            )
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Gemini Intent Error: {e}")
        return {"detected_language": "en", "intent": "OTHER", "items": []}

def generate_localized_reply(context_data: dict, target_lang: str) -> str:
    """
    Generates pure native-script text for voice conversion (NO Latin Tanglish/Hinglish).
    """
    prompt = f"""
    Context Data: {json.dumps(context_data, ensure_ascii=False)}
    Target Language Code: {target_lang} (e.g. 'ta' = Tamil script, 'hi' = Devanagari script, 'en' = English).

    Generate a brief, clear, natural response in the PURE NATIVE SCRIPT of the target language.
    STRICT RULE: Do NOT use Latinized Tanglish or Hinglish. If Tamil, write purely in தமிழ். If Hindi, write purely in हिन्दी.
    - If sales logged: mention item name and remaining stock.
    - If low stock: alert them and tell them to say 'YES' to order from distributor.
    - Do NOT include emojis in text that will be spoken aloud.
    """
    try:
        res = ai_client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt
        )
        return res.text.strip()
    except Exception as e:
        print(f"Localization Error: {e}")
        return "Update completed."