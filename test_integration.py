from core.ai_engine import extract_retail_intent
from database.db import deduct_stock_and_log_sale, get_all_inventory

print("🔍 1. Testing Gemini AI Multilingual Parsing...")
sample_inputs = [
    "Sold 2 Marie Gold and 1 Good Day",
    "2 maggi kuduthen",  # Tanglish/Tamil test
    "stock enna iruku?"
]

for text in sample_inputs:
    parsed = extract_retail_intent(text)
    print(f"Input: '{text}' -> Intent: {parsed.get('intent')}, Items: {parsed.get('items')}")

print("\n📦 2. Testing Supabase Stock Deduction & Alert...")
res, err = deduct_stock_and_log_sale("Marie Gold", 2)
if res:
    print(f"✅ Marie Gold stock updated: {res['new_stock']} units remaining (Low stock alert: {res['is_low_stock']})")
else:
    print(f"❌ Error: {err}")

print("\n📊 3. Current Live Supabase Inventory:")
items = get_all_inventory()
for it in items:
    print(f"• {it['name']} ({it['brand']}): {it['current_stock']} units | Threshold: {it['threshold']}")