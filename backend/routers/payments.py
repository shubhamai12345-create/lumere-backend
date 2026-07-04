"""
Payment Router — Odoo errors are caught and logged, never crash the order
"""
import hmac, hashlib, os
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from database import get_db
from models.order import Order, OrderStatus
from services import razorpay_service, shiprocket_service

router = APIRouter()

class VerifyPaymentRequest(BaseModel):
    order_id: str
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

async def _post_payment_tasks(order: Order, db: AsyncSession):
    """Background tasks after payment — each step is independent, failures are non-fatal."""
    order_dict = {
        "id": order.id, "customer_name": order.customer_name,
        "customer_email": order.customer_email, "customer_phone": order.customer_phone,
        "address_line1": order.address_line1, "city": order.city,
        "state": order.state, "pincode": order.pincode,
        "items": order.items, "subtotal": order.subtotal,
        "total": order.total, "shipping_charge": order.shipping_charge,
        "payment_method": order.payment_method,
    }

    # Step 1: Book courier (Shiprocket)
    try:
        shipment = await shiprocket_service.create_shipment(order_dict)
        order.awb_number = shipment["awb_number"]
        order.courier_name = shipment["courier_name"]
        order.shiprocket_order_id = shipment["shiprocket_order_id"]
        order.status = OrderStatus.SHIPPED
        await db.commit()
        print(f"[Shiprocket] ✅ AWB {order.awb_number} for {order.id}")
    except Exception as e:
        print(f"[Shiprocket] ⚠️ Skipped for {order.id}: {e}")

    # Step 2: Create Odoo invoice (optional — fails gracefully)
    try:
        odoo_key = os.getenv("ODOO_API_KEY", "")
        if odoo_key and odoo_key != "REPLACE_WITH_API_KEY":
            from services import odoo_service
            invoice_id = odoo_service.create_invoice(order_dict)
            order.odoo_invoice_id = invoice_id
            await db.commit()
            print(f"[Odoo] ✅ Invoice {invoice_id} for {order.id}")
        else:
            print(f"[Odoo] ⏭️ Skipped — API key not configured yet")
    except Exception as e:
        print(f"[Odoo] ⚠️ Invoice skipped for {order.id}: {e}")

@router.post("/verify")
async def verify_payment(
    req: VerifyPaymentRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    valid = razorpay_service.verify_payment_signature(
        req.razorpay_order_id, req.razorpay_payment_id, req.razorpay_signature
    )
    if not valid:
        raise HTTPException(status_code=400, detail="Invalid payment signature")

    result = await db.execute(select(Order).where(Order.id == req.order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order.razorpay_payment_id = req.razorpay_payment_id
    order.status = OrderStatus.PAID
    await db.commit()

    background_tasks.add_task(_post_payment_tasks, order, db)
    return {"status": "payment_verified", "order_id": req.order_id}

@router.post("/webhook")
async def razorpay_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "").encode()
    if secret:
        digest = hmac.new(secret, body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(digest, signature):
            raise HTTPException(status_code=400, detail="Invalid webhook signature")

    payload = await request.json()
    event = payload.get("event")
    if event == "payment.captured":
        payment = payload["payload"]["payment"]["entity"]
        order_id = payment["notes"].get("lumere_order_id")
        if order_id:
            result = await db.execute(select(Order).where(Order.id == order_id))
            order = result.scalar_one_or_none()
            if order and order.status == OrderStatus.PENDING:
                order.razorpay_payment_id = payment["id"]
                order.status = OrderStatus.PAID
                await db.commit()
    return {"received": True}
