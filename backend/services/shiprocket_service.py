import os, httpx
from datetime import datetime, timedelta

SHIPROCKET_EMAIL    = os.getenv("SHIPROCKET_EMAIL")
SHIPROCKET_PASSWORD = os.getenv("SHIPROCKET_PASSWORD")
SHIPROCKET_BASE     = "https://apiv2.shiprocket.in/v1/external"

# Simple in-memory token cache (use Redis in production)
_token_cache = {"token": None, "expires_at": None}

# ─── Zone table: Delhi origin pincode prefix → zone / ETA ─────────────
# Used to show estimated delivery time BEFORE an order is placed
ZONE_TABLE = {
    "110": {"zone": "A", "days_air": "1",   "days_surface": "1",   "label": "Delhi NCR"},
    "120": {"zone": "A", "days_air": "1",   "days_surface": "1",   "label": "Delhi NCR"},
    "122": {"zone": "A", "days_air": "1",   "days_surface": "1",   "label": "Gurgaon"},
    "201": {"zone": "A", "days_air": "1",   "days_surface": "1",   "label": "Noida/Ghaziabad"},
    "301": {"zone": "B", "days_air": "1-2", "days_surface": "2-3", "label": "Rajasthan"},
    "160": {"zone": "B", "days_air": "1-2", "days_surface": "2-3", "label": "Chandigarh"},
    "226": {"zone": "B", "days_air": "1-2", "days_surface": "2-3", "label": "Lucknow"},
    "400": {"zone": "C", "days_air": "2-3", "days_surface": "3-5", "label": "Mumbai"},
    "411": {"zone": "C", "days_air": "2-3", "days_surface": "3-5", "label": "Pune"},
    "380": {"zone": "C", "days_air": "2-3", "days_surface": "3-5", "label": "Ahmedabad"},
    "700": {"zone": "D", "days_air": "2-3", "days_surface": "4-5", "label": "Kolkata"},
    "560": {"zone": "E", "days_air": "3-4", "days_surface": "5-7", "label": "Bengaluru"},
    "600": {"zone": "E", "days_air": "3-4", "days_surface": "5-7", "label": "Chennai"},
    "500": {"zone": "E", "days_air": "3-4", "days_surface": "5-7", "label": "Hyderabad"},
    "682": {"zone": "E", "days_air": "3-4", "days_surface": "5-7", "label": "Kochi"},
    "781": {"zone": "F", "days_air": "4-6", "days_surface": "7-10","label": "Guwahati"},
    "180": {"zone": "F", "days_air": "4-6", "days_surface": "7-10","label": "Jammu"},
}

def get_delivery_estimate(customer_pincode: str) -> dict:
    """
    Given a 6-digit customer pincode, return delivery estimate.
    Used on checkout page to show ETA before order is placed.
    """
    prefix = customer_pincode[:3]
    zone   = ZONE_TABLE.get(prefix, {
        "zone": "C", "days_air": "3-4",
        "days_surface": "5-7", "label": "India"
    })
    return {
        "zone":      zone["zone"],
        "location":  zone["label"],
        "air_days":  zone["days_air"],
        "surface_days": zone["days_surface"],
        "message":   f"Delivered in {zone['days_air']} business days to {zone['label']}"
    }

async def _get_token() -> str:
    """Authenticate with Shiprocket and cache the token (valid 24h)."""
    now = datetime.utcnow()
    if _token_cache["token"] and _token_cache["expires_at"] > now:
        return _token_cache["token"]
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{SHIPROCKET_BASE}/auth/login", json={
            "email":    SHIPROCKET_EMAIL,
            "password": SHIPROCKET_PASSWORD
        })
        resp.raise_for_status()
        data = resp.json()
        _token_cache["token"]      = data["token"]
        _token_cache["expires_at"] = now + timedelta(hours=23)
        return data["token"]

async def create_shipment(order: dict) -> dict:
    """
    Create a Shiprocket order + shipment after payment is confirmed.
    order dict contains all Lumère order fields.
    Returns: {"shiprocket_order_id": ..., "awb_number": ..., "courier_name": ...}
    """
    token  = await _get_token()
    headers = {"Authorization": f"Bearer {token}"}
    items  = [
        {
            "name":     item["name"],
            "sku":      item["product_id"],
            "units":    item["qty"],
            "selling_price": item["price"],
            "hsn":      334,
        }
        for item in order["items"]
    ]
    payload = {
        "order_id":          order["id"],
        "order_date":        datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
        "pickup_location":   "Primary",           # set in Shiprocket dashboard
        "channel_id":        "",
        "comment":           "Lumère skincare",
        "billing_customer_name":  order["customer_name"],
        "billing_address":        order["address_line1"],
        "billing_city":           order["city"],
        "billing_pincode":        order["pincode"],
        "billing_state":          order["state"],
        "billing_country":        "India",
        "billing_email":          order["customer_email"],
        "billing_phone":          order["customer_phone"],
        "shipping_is_billing":    True,
        "order_items":            items,
        "payment_method":         "Prepaid" if order["payment_method"] == "prepaid" else "COD",
        "sub_total":              order["subtotal"],
        "length":                 10, "breadth": 8, "height": 12, "weight": 0.3,
    }
    async with httpx.AsyncClient() as client:
        # Step 1: Create order
        r1 = await client.post(f"{SHIPROCKET_BASE}/orders/create/adhoc",
                               json=payload, headers=headers)
        r1.raise_for_status()
        sr_order = r1.json()
        sr_order_id  = sr_order["order_id"]
        sr_shipment_id = sr_order["shipment_id"]

        # Step 2: Assign courier + generate AWB
        r2 = await client.post(f"{SHIPROCKET_BASE}/courier/assign/awb",
                               json={"shipment_id": sr_shipment_id}, headers=headers)
        r2.raise_for_status()
        awb_data = r2.json()
        return {
            "shiprocket_order_id": str(sr_order_id),
            "awb_number":    awb_data["response"]["data"]["awb_code"],
            "courier_name":  awb_data["response"]["data"]["courier_name"],
        }

async def track_shipment(awb_number: str) -> dict:
    """
    Get real-time tracking status for an AWB.
    Called when a customer visits /track/{awb}
    """
    token = await _get_token()
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{SHIPROCKET_BASE}/courier/track/awb/{awb_number}",
            headers={"Authorization": f"Bearer {token}"}
        )
        r.raise_for_status()
        data = r.json()
        tracking = data["tracking_data"]
        return {
            "awb":          awb_number,
            "status":       tracking["shipment_track"][0]["current_status"],
            "courier":      tracking["shipment_track"][0]["courier_name"],
            "estimated_delivery": tracking["shipment_track"][0].get("etd"),
            "events":       tracking.get("shipment_track_activities", []),
        }
