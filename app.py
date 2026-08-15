import os
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from core.ai_engine import extract_retail_intent
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

    # Ignore empty status pings
    if not incoming_msg and num_media == 0:
        return ("", 204)

    # 1. Process Voice Note if sent
    if num_media > 0 and media_url:
        print("🎙️ Audio note received, transcribing...")
        incoming_msg = transcribe_whatsapp_audio(media_url)
        print(f"Transcribed Text: {incoming_msg}")

    print(f"📩 Incoming command: '{incoming_msg}'")

    resp = MessagingResponse()
    reply = resp.message()

    if not incoming_msg:
        reply.body("🏪 ShopPilot AI: Could not recognize speech. Please retry.")
        return str(resp)

    # 2. Extract Intent with Gemini
    parsed = extract_retail_intent(incoming_msg)
    intent = parsed.get("intent", "OTHER")
    items = parsed.get("items", [])

    # 3. Handle Sales Logging
    if intent == "LOG_SALE" and items:
        lines = ["✅ *Sales Logged:*"]
        critical_alerts = []

        for it in items:
            name = it.get("item_name", "")
            qty = it.get("quantity", 1)
            res, err = deduct_stock_and_log_sale(name, qty)

            if res:
                lines.append(f"• {res['name']}: -{qty} (Stock: {res['new_stock']})")
                if res["is_low_stock"]:
                    critical_alerts.append(res)
            else:
                lines.append(f"• {name.title()}: -{qty} (Not in DB)")

        # Trigger Restock Draft if threshold crossed
        if critical_alerts:
            first_alert = critical_alerts[0]
            dist = first_alert.get("distributor") or {}
            moq = dist.get("moq_units", 24)
            dist_id = dist.get("id", 1)

            order_summary = f"• 1 Crate ({moq} units) {first_alert['name']} ({first_alert['brand']})"
            
            # Save draft in Supabase
            draft = create_draft_order(dist_id, {"summary": order_summary, "item": first_alert["name"]})

            alert_text = (
                f"\n\n⚠️ *CRITICAL STOCK ALERT:*\n"
                f"• *{first_alert['name']}* has only {first_alert['new_stock']} units left!\n\n"
                f"📝 *Draft Purchase Order Created ({first_alert['brand']} Distributor):*\n"
                f"{order_summary}\n\n"
                f"👉 Reply *YES* to dispatch this PO directly to the distributor."
            )
            lines.append(alert_text)

        reply.body("\n".join(lines))

    # 4. Handle Restock Confirmation
    elif intent == "CONFIRM_ORDER":
        pending_order = get_latest_draft_order()
        if pending_order:
            order_text = pending_order.get("order_details", {}).get("summary", "Restock Order")
            dist_phone = pending_order.get("distributors", {}).get("phone_number")

            # Update Supabase status
            mark_order_as_dispatched(pending_order["id"])

            # Send outbound PO to distributor
            send_distributor_purchase_order(order_text, dist_phone)

            reply.body(
                f"🚀 *Purchase Order Dispatched!*\n\n"
                f"{order_text}\n\n"
                f"Distributor notified via WhatsApp. Delivery expected tomorrow."
            )
        else:
            reply.body("ℹ️ There are no pending draft purchase orders right now.")

    # 5. Handle Inventory Query
    elif intent == "QUERY_STOCK":
        inventory_items = get_all_inventory()
        lines = ["📊 *Current Live Inventory:*"]
        for it in inventory_items:
            status = "🟢" if it["current_stock"] > it["threshold"] else "🔴 LOW"
            lines.append(f"• {it['name']} ({it['brand']}): {it['current_stock']} left [{status}]")
        reply.body("\n".join(lines))

    # 6. Default Fallback
    else:
        reply.body(
            "🏪 *ShopPilot AI Copilot Active*\n\n"
            "Try messaging:\n"
            "• *'Sold 2 Marie Gold'* (or Tanglish: *'2 Marie Gold kuduthen'*)\n"
            "• *'Stock enna iruku?'* (check inventory)\n"
            "• *'Yes'* (to confirm restock order)"
        )

    return str(resp)

if __name__ == "__main__":
    app.run(port=5000, debug=True)