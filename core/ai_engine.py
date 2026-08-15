import json
from google import genai
from google.genai import types
from config.settings import GEMINI_API_KEY

ai_client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = """
You are ShopPilot AI, a retail copilot for local shopkeepers.
Parse the shopkeeper's casual input (English, Tanglish, Tamil, or Hinglish) into structured JSON.

Classify into one of these intents:
1. LOG_SALE: Shopkeeper sold items (e.g. 'Sold 2 Marie Gold', '2 good day kuduthen', '5 maggi bik gaya').
2. CONFIRM_ORDER: Confirming a restock order (e.g. 'yes', 'confirm', 'order pannu', 'haan bhej do', 'ok').
3. QUERY_STOCK: Asking about current inventory (e.g. 'How many biscuits left?', 'stock enna iruku?').
4. OTHER: Conversational fallback or greeting.

Output ONLY valid JSON matching this schema:
{
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
        print(f"Gemini Extraction Error: {e}")
        return {"intent": "OTHER", "items": []}