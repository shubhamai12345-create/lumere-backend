"""
Odoo Invoicing Service for Lumère
===================================
Uses Odoo's standard JSON-RPC API (same API for both
odoo.com hosted free plan AND self-hosted Community Edition).

HOW TO SET UP ODOO (free one-user plan):
1. Go to odoo.com → Start for free
2. During setup: select ONLY the "Invoicing" app
   (selecting more than one app ends the free tier)
3. Go to Settings → Technical → API Keys → Create API key
4. Set these env vars in Railway:
   ODOO_URL      = https://yourcompany.odoo.com
   ODOO_DB       = yourcompany
   ODOO_USERNAME = your@email.com
   ODOO_API_KEY  = the key you just created
"""

import os
import xmlrpc.client
from datetime import datetime

ODOO_URL      = os.getenv("ODOO_URL", "https://yourcompany.odoo.com")
ODOO_DB       = os.getenv("ODOO_DB", "yourcompany")
ODOO_USERNAME = os.getenv("ODOO_USERNAME")
ODOO_API_KEY  = os.getenv("ODOO_API_KEY")   # API key (safer than password)

def _get_odoo_uid() -> int:
    """Authenticate with Odoo and return user ID."""
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
    uid = common.authenticate(ODOO_DB, ODOO_USERNAME, ODOO_API_KEY, {})
    if not uid:
        raise Exception("Odoo authentication failed — check ODOO credentials in env")
    return uid

def _get_odoo_models():
    """Return Odoo models proxy (used for all CRUD operations)."""
    return xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")

def create_invoice(order: dict) -> str:
    """
    Create a GST-compliant invoice in Odoo for a confirmed Lumère order.
    Returns the Odoo invoice ID.

    order dict should contain:
    - id, customer_name, customer_email, customer_phone
    - items: [{name, qty, price, hsn_code, gst_rate}]
    - total, gst_amount, shipping_charge
    - address_line1, city, state, pincode
    """
    uid    = _get_odoo_uid()
    models = _get_odoo_models()

    # --- Step 1: Find or create the customer (res.partner) ---
    partner_ids = models.execute_kw(
        ODOO_DB, uid, ODOO_API_KEY,
        "res.partner", "search",
        [[["email", "=", order["customer_email"]]]]
    )
    if partner_ids:
        partner_id = partner_ids[0]
    else:
        partner_id = models.execute_kw(
            ODOO_DB, uid, ODOO_API_KEY,
            "res.partner", "create",
            [{
                "name":   order["customer_name"],
                "email":  order["customer_email"],
                "phone":  order["customer_phone"],
                "street": order["address_line1"],
                "city":   order["city"],
                "zip":    order["pincode"],
                "country_id": 105,  # India
            }]
        )

    # --- Step 2: Build invoice lines ---
    invoice_lines = []
    for item in order["items"]:
        invoice_lines.append((0, 0, {
            "name":        item["name"],
            "quantity":    item["qty"],
            "price_unit":  item["price"],
            "tax_ids":     [(6, 0, [])],  # GST taxes — configure in Odoo dashboard
        }))

    # Add shipping as a line if charged
    if order.get("shipping_charge", 0) > 0:
        invoice_lines.append((0, 0, {
            "name":       "Shipping",
            "quantity":   1,
            "price_unit": order["shipping_charge"],
            "tax_ids":    [(6, 0, [])],
        }))

    # --- Step 3: Create the invoice (account.move) ---
    invoice_id = models.execute_kw(
        ODOO_DB, uid, ODOO_API_KEY,
        "account.move", "create",
        [{
            "move_type":        "out_invoice",    # customer invoice
            "partner_id":       partner_id,
            "invoice_date":     datetime.today().strftime("%Y-%m-%d"),
            "ref":              order["id"],       # Lumère order ID as reference
            "invoice_line_ids": invoice_lines,
            "narration":        f"Lumère Order {order['id']}",
        }]
    )

    # --- Step 4: Confirm (post) the invoice so it gets a number ---
    models.execute_kw(
        ODOO_DB, uid, ODOO_API_KEY,
        "account.move", "action_post",
        [[invoice_id]]
    )

    # --- Step 5: Send invoice by email ---
    models.execute_kw(
        ODOO_DB, uid, ODOO_API_KEY,
        "account.move", "action_invoice_sent",
        [[invoice_id]]
    )

    return str(invoice_id)

def get_invoice_pdf_url(invoice_id: str) -> str:
    """Return Odoo's PDF download URL for an invoice."""
    return f"{ODOO_URL}/report/pdf/account.report_invoice/{invoice_id}"
