from supabase import create_client, Client
from config.settings import SUPABASE_URL, SUPABASE_KEY

# Connect to Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_all_inventory():
    """Retrieve all stock items with connected distributor details."""
    response = supabase.table("inventory").select("*, distributors(*)").execute()
    return response.data

def deduct_stock_and_log_sale(item_query: str, quantity: int):
    """
    Finds item using fuzzy matching, decrements stock in Supabase,
    and returns low-stock alerts if threshold is crossed.
    """
    res = supabase.table("inventory").select("*, distributors(*)").ilike("name", f"%{item_query}%").execute()
    
    if not res.data:
        return None, f"Item '{item_query}' not found in inventory."

    item = res.data[0]
    updated_stock = max(0, item["current_stock"] - quantity)

    # Update inventory table
    supabase.table("inventory").update({"current_stock": updated_stock}).eq("id", item["id"]).execute()

    # Log sale transaction
    supabase.table("sales_log").insert({
        "item_name": item["name"],
        "quantity": quantity
    }).execute()

    is_low_stock = updated_stock <= item["threshold"]
    
    return {
        "id": item["id"],
        "name": item["name"],
        "brand": item["brand"],
        "new_stock": updated_stock,
        "threshold": item["threshold"],
        "pack_size": item.get("pack_size", 24),
        "is_low_stock": is_low_stock,
        "distributor": item.get("distributors")
    }, None

def create_draft_order(distributor_id: int, details: dict):
    """Saves a draft PO."""
    res = supabase.table("purchase_orders").insert({
        "distributor_id": distributor_id,
        "status": "DRAFT",
        "order_details": details
    }).execute()
    return res.data[0] if res.data else None

def get_latest_draft_order():
    """Fetches the newest unconfirmed draft PO."""
    res = supabase.table("purchase_orders")\
        .select("*, distributors(*)")\
        .eq("status", "DRAFT")\
        .order("created_at", desc=True)\
        .limit(1)\
        .execute()
    return res.data[0] if res.data else None

def mark_order_as_dispatched(order_id: int):
    """Updates order status to DISPATCHED."""
    supabase.table("purchase_orders").update({"status": "DISPATCHED"}).eq("id", order_id).execute()