import os
from flask import Flask, request, send_from_directory
from twilio.twiml.messaging_response import MessagingResponse
from core.ai_engine import extract_retail_intent, generate_localized_reply
from core.voice_processor import transcribe_whatsapp_audio, text_to_audio_file
from database.db import (
    get_all_inventory,
    deduct_stock_and_log_sale,
    create_draft_order,
    get_latest_draft_order,
    mark_order_as_dispatched
)
from services.whatsapp_service import send_distributor_purchase_order

app = Flask(__name__, static_folder="static")

@app.route("/static/audio/<filename>")
def serve_audio(filename):
    return send_from_directory(os.path.join(app.root_path, "static", "audio"), filename)

@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.values.get("Body", "").strip()
    num_media = int(request.values.get("NumMedia", 0))
    media_url = request.values.get("MediaUrl0", "")

    is_voice_input = num_media > 0 and media_url

    if is_voice_input:
        print("🎙️ Audio note received, transcribing...")
        incoming_msg = transcribe_whatsapp_audio(media_url)
        print(f"Transcribed Text: {incoming_msg}")

    if not incoming_msg and not is_voice_input:
        return ("", 204)

    resp = MessagingResponse()
    reply = resp.message()

    if not incoming_msg:
        reply.body("குரலை அடையாளம் காண முடியவில்லை. மீண்டும் முயற்சிக்கவும்.")
        return str(resp)

    # 1. Parse Intent & Regional Language
    parsed = extract_retail_intent(incoming_msg)
    intent = parsed.get("intent", "OTHER")
    items = parsed.get("items", [])
    lang = parsed.get("detected_language", "ta")  # Default to Tamil

    reply_text = ""

    # 2. Process Intent
    if intent == "LOG_SALE" and items:
        processed_items = []
        critical_alerts = []

        for it in items:
            name = it.get("item_name", "")
            qty = it.get("quantity", 1)
            res, err = deduct_stock_and_log_sale(name, qty)
            if res:
                processed_items.append({"name": res["name"], "deducted": qty, "remaining": res["new_stock"]})
                if res["is_low_stock"]:
                    critical_alerts.append(res)
            else:
                processed_items.append({"name": name, "deducted": qty, "status": "Not found"})

        draft_summary = ""
        if critical_alerts:
            first_alert = critical_alerts[0]
            dist = first_alert.get("distributor") or {}
            moq = dist.get("moq_units", 24)
            dist_id = dist.get("id", 1)
            draft_summary = f"1 Crate ({moq} units) {first_alert['name']} ({first_alert.get('brand', '')})"
            create_draft_order(dist_id, {"summary": draft_summary, "item": first_alert["name"]})

        context_data = {
            "type": "SALE_LOGGED",
            "items": processed_items,
            "critical_alert": bool(critical_alerts),
            "order_draft": draft_summary
        }
        reply_text = generate_localized_reply(context_data, lang)

    elif intent == "CONFIRM_ORDER":
        pending_order = get_latest_draft_order()
        if pending_order:
            order_text = pending_order.get("order_details", {}).get("summary", "Restock Order")
            dist_phone = pending_order.get("distributors", {}).get("phone_number")
            mark_order_as_dispatched(pending_order["id"])
            send_distributor_purchase_order(order_text, dist_phone)

            context_data = {
                "type": "ORDER_DISPATCHED",
                "order_summary": order_text
            }
            reply_text = generate_localized_reply(context_data, lang)
        else:
            reply_text = "நிலுவையில் உள்ள ஆர்டர்கள் எதுவும் இல்லை." if lang == "ta" else "No pending draft orders found."

    elif intent == "QUERY_STOCK":
        inventory_items = get_all_inventory()
        context_data = {
            "type": "STOCK_QUERY",
            "inventory": [{"name": i["name"], "stock": i["current_stock"]} for i in inventory_items]
        }
        reply_text = generate_localized_reply(context_data, lang)

    else:
        context_data = {"type": "GREETING", "text": "Help with sales logging, stock query, or distributor orders."}
        reply_text = generate_localized_reply(context_data, lang)

    # 3. If the user sent a voice message, reply with a Native Audio Note
    if is_voice_input:
        audio_filename = text_to_audio_file(reply_text, lang)
        if audio_filename:
            # Ngrok public base URL
            base_url = request.host_url.rstrip("/")
            audio_url = f"{base_url}/static/audio/{audio_filename}"
            reply.media(audio_url)

    # Attach text response
    reply.body(reply_text)
    return str(resp)

if __name__ == "__main__":
    app.run(port=5000, debug=True)