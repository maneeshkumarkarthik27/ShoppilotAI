from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from core.ai_engine import extract_retail_intent, generate_localized_reply
from core.voice_processor import transcribe_whatsapp_audio
from database.db import (
    get_all_inventory,
    deduct_stock_and_log_sale,
    create_draft_order,
    get_latest_draft_order,
    mark_order_as_dispatched
)
from services.whatsapp_service import send_distributor_purchase_order

app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.values.get("Body", "").strip()
    num_media = int(request.values.get("NumMedia", 0))
    media_url = request.values.get("MediaUrl0", "")

    if not incoming_msg and num_media == 0:
        return ("", 204)

    # 1. Voice transcription if audio sent
    if num_media > 0 and media_url:
        incoming_msg = transcribe_whatsapp_audio(media_url)

    resp = MessagingResponse()
    reply = resp.message()

    if not incoming_msg:
        reply.body("Could not process voice. Please try again.")
        return str(resp)

    # 2. Extract Intent & Detect Language
    parsed = extract_retail_intent(incoming_msg)
    intent = parsed.get("intent", "OTHER")
    items = parsed.get("items", [])
    lang = parsed.get("detected_language", "en")

    # 3. Handle Sales Logging
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
                processed_items.append({"name": name, "deducted": qty, "status": "Not found in DB"})

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
        
        reply_message = generate_localized_reply(context_data, lang)
        reply.body(reply_message)

    # 4. Handle Restock Confirmation
    elif intent == "CONFIRM_ORDER":
        pending_order = get_latest_draft_order()
        if pending_order:
            order_text = pending_order.get("order_details", {}).get("summary", "Restock Order")
            dist_phone = pending_order.get("distributors", {}).get("phone_number")

            mark_order_as_dispatched(pending_order["id"])
            send_distributor_purchase_order(order_text, dist_phone)

            context_data = {
                "type": "ORDER_DISPATCHED",
                "order_summary": order_text,
                "message": "Purchase order has been sent to the distributor."
            }
            reply_message = generate_localized_reply(context_data, lang)
            reply.body(reply_message)
        else:
            reply.body("No pending draft orders found.")

    # 5. Handle Inventory Query
    elif intent == "QUERY_STOCK":
        inventory_items = get_all_inventory()
        context_data = {
            "type": "STOCK_QUERY",
            "inventory": [{"name": i["name"], "stock": i["current_stock"], "threshold": i["threshold"]} for i in inventory_items]
        }
        reply_message = generate_localized_reply(context_data, lang)
        reply.body(reply_message)

    # 6. Fallback
    else:
        fallback = parsed.get("localized_fallback_message", "Hello! How can I assist you with your shop inventory?")
        reply.body(fallback)

    return str(resp)

if __name__ == "__main__":
    app.run(port=5000, debug=True)