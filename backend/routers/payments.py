"""
Payment Router
=================
Two endpoints:
  1. POST /api/payments/verify   — called by frontend after customer pays
  2. POST /api/payments/webhook  — called by Razorpay server for every event

After successful payment:
  - Order status → PAID
  - Triggers shipping creation (Shiprocket)
  - Triggers invoice creation (Odoo)
"""

import hmac, hashlib, os
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from database import get_db
from models.order import Order, OrderStatus
from services import razorpay_service, shiprocket_service, odoo_service

router = APIRouter()

class VerifyPaymentRequest(BaseModel):
    order_id:           str      # Lumère order ID
    razorpay_order_id:  str
    razorpay_payment_id:str
    razorpay_signature: str

async def _post_payment_tasks(order: Order, db: AsyncSession):
    """
    Background: runs after payment confirmed.
    1. Book Shiprocket shipment → get AWB
    2. Create Odoo invoice
    """
    order_dict = {
        "id":             order.id,
        "customer_name":  order.customer_name,
        "customer_email": order.customer_email,
        "customer_phone": order.customer_phone,
        "address_line1":  order.address_line1,
        "city":           order.city,
        "state":          order.state,
        "pincode":        order.pincode,
        "items":          order.items,
        "subtotal":       order.subtotal,
        "total":          order.total,
        "shipping_charge":order.shipping_charge,
        "payment_method": order.payment_method,
    }
    try:
        # Book courier
        shipment = await shiprocket_service.create_shipment(order_dict)
        order.awb_number          = shipment["awb_number"]
        order.courier_name        = shipment["courier_name"]
        order.shiprocket_order_id = shipment["shiprocket_order_id"]
        order.status              = OrderStatus.SHIPPED
        await db.commit()
    except Exception as e:
        print(f"[Shiprocket] Failed for {order.id}: {e}")

    try:
        # Create Odoo invoice
        invoice_id = odoo_service.create_invoice(order_dict)
        order.odoo_invoice_id = invoice_id
        await db.commit()
    except Exception as e:
        print(f"[Odoo] Invoice failed for {order.id}: {e}")

@router.post("/verify")
async def verify_payment(
    req: VerifyPaymentRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Frontend calls this immediately after Razorpay checkout completes.
    Verifies the HMAC signature — if valid, marks order as PAID.
    """
    valid = razorpay_service.verify_payment_signature(
        req.razorpay_order_id,
        req.razorpay_payment_id,
        req.razorpay_signature
    )
    if not valid:
        raise HTTPException(status_code=400, detail="Invalid payment signature")

    result = await db.execute(select(Order).where(Order.id == req.order_id))
    order  = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order.razorpay_payment_id = req.razorpay_payment_id
    order.status              = OrderStatus.PAID
    await db.commit()

    # Kick off Shiprocket + Odoo in the background (non-blocking)
    background_tasks.add_task(_post_payment_tasks, order, db)

    return {"status": "payment_verified", "order_id": req.order_id}

@router.post("/webhook")
async def razorpay_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Razorpay calls this endpoint for server-side payment events.
    Register this URL in Razorpay Dashboard → Webhooks.
    This is a backup — verify_payment above handles the primary flow.
    """
    body      = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    secret    = os.getenv("RAZORPAY_WEBHOOK_SECRET", "").encode()
    digest    = hmac.new(secret, body, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(digest, signature):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    payload = await request.json()
    event   = payload.get("event")

    if event == "payment.captured":
        payment = payload["payload"]["payment"]["entity"]
        order_id = payment["notes"].get("lumere_order_id")
        if order_id:
            result = await db.execute(select(Order).where(Order.id == order_id))
            order  = result.scalar_one_or_none()
            if order and order.status == OrderStatus.PENDING:
                order.razorpay_payment_id = payment["id"]
                order.status              = OrderStatus.PAID
                await db.commit()

    return {"received": True}
