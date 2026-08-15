from twilio.rest import Client
from config.settings import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER, DISTRIBUTOR_DEMO_PHONE

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

def send_distributor_purchase_order(order_text: str, distributor_phone: str = None) -> bool:
    target_phone = distributor_phone or DISTRIBUTOR_DEMO_PHONE
    if not target_phone:
        print("⚠️ No distributor phone number configured.")
        return False
    try:
        msg = twilio_client.messages.create(
            from_=TWILIO_WHATSAPP_NUMBER,
            to=target_phone,
            body=f"📦 *NEW PURCHASE ORDER — ShopPilot AI*\n----------------------------------\n{order_text}\n\n📍 *Delivery Location:* Main Branch Store\n⏱️ *Expected Fulfillment:* Next Business Day"
        )
        print(f"✅ Dispatched PO to distributor: {msg.sid}")
        return True
    except Exception as e:
        print(f"❌ Failed to dispatch WhatsApp PO: {e}")
        return False