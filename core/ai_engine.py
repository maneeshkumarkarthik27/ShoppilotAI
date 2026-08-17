import json
from google import genai
from google.genai import types
from config.settings import GEMINI_API_KEY

ai_client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = """
You are ShopPilot AI, an intelligent retail assistant for local shopkeepers across India.
Shopkeepers may text with broken grammar, phonetic spelling, mixed languages, or local dialects:
- English / Broken English (e.g. 'tomato sold', 'give 2 parle g', 'sold marie gold')
- Tamil / Tanglish (e.g. 'thakkali vutthen', '2 good day kuduthen', 'stock enna irukku?')
- Hindi / Hinglish (e.g. 'tamatar bik gaya', '2 maggi becha', 'kitna stock hai?')
- Telugu, Kannada, Malayalam, etc.

Your Tasks:
1. Detect user's language/dialect ('ta', 'ta-Latn' (Tanglish), 'hi', 'hi-Latn' (Hinglish), 'en', etc.).
2. Extract intent:
   - LOG_SALE: Sold items. If quantity is omitted (e.g. 'tomato sold'), default quantity to 1.
   - CONFIRM_ORDER: Confirmation (e.g. 'yes', 'aama', 'haan', 'sari', 'order pannu').
   - QUERY_STOCK: Inquiring about inventory.
   - OTHER: Greetings, unclear text, or small talk.
3. Normalize item names to standard catalog names if possible (e.g. 'thakkali'/'tamatar' -> 'Tomato', 'good day' -> 'Good Day').
4. Formulate a short, natural response in the EXACT language and script/style the user used.

Output strictly valid JSON matching this schema:
{
  "detected_language": "string",
  "intent": "LOG_SALE" | "CONFIRM_ORDER" | "QUERY_STOCK" | "OTHER",
  "items": [
    {"item_name": "string", "quantity": integer}
  ],
  "localized_fallback_message": "string"
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
                temperature=0.2
            )
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Gemini Extraction Error: {e}")
        return {
            "detected_language": "en",
            "intent": "OTHER",
            "items": [],
            "localized_fallback_message": "Could not understand the message. Please try again."
        }

def generate_localized_reply(context_data: dict, detected_lang: str) -> str:
    """
    Translates inventory updates or stock alerts dynamically into the user's language/dialect.
    """
    prompt = f"""
    Context Data: {json.dumps(context_data, ensure_ascii=False)}
    Target Language / Dialect: {detected_lang}

    Create a clean, friendly WhatsApp message in the target language based on the context data.
    - If it's a sales confirmation: state item deducted and remaining stock.
    - If low stock: warn them clearly and ask to reply 'YES' to order from the distributor.
    - Keep formatting clean with emojis. Use the native script or Latin script depending on the target language style.
    """
    try:
        res = ai_client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt
        )
        return res.text.strip()
    except Exception:
        # Fallback to English summary
        return context_data.get("default_english_text", "Update completed.")