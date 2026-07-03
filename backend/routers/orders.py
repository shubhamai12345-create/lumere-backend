"""
Order Router — The core Lumère checkout flow

Customer journey:
  1. POST /api/orders/           → create order record + Razorpay order
  2. [Frontend: customer pays on Razorpay checkout]
  3. POST /api/payments/verify   → verify payment, mark paid
  4. POST /api/shipping/create   → book Shiprocket courier, get AWB
  5. POST /api/invoices/create   → create Odoo invoice, email customer
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional

from database import get_db
from models.order import Order, OrderStatus, PaymentMethod
from services import razorpay_service

router = APIRouter()

# ─── Request / Response schemas ──────────────────────────────────────
class OrderItem(BaseModel):
    product_id: str
    name:       str
    qty:        int
    price:      float

class CreateOrderRequest(BaseModel):
    customer_name:  str
    customer_email: str
    customer_phone: str
    address_line1:  str
    address_line2:  Optional[str] = None
    city:           str
    state:          str
    pincode:        str
    items:          List[OrderItem]
    payment_method: PaymentMethod

class OrderResponse(BaseModel):
    order_id:          str
    razorpay_order_id: Optional[str]
    total:             float
    status:            str

# ─── Generate order ID ────────────────────────────────────────────────
def generate_order_id() -> str:
    """Generates e.g. LUM-2026-A3F2"""
    return f"LUM-2026-{uuid.uuid4().hex[:6].upper()}"

# ─── Routes ───────────────────────────────────────────────────────────
@router.post("/", response_model=OrderResponse)
async def create_order(req: CreateOrderRequest, db: AsyncSession = Depends(get_db)):
    """
    Step 1 of checkout: create the Lumère order record.
    For prepaid orders, also creates a Razorpay order.
    Returns the order ID and Razorpay order ID to the frontend.
    """
    order_id = generate_order_id()
    
    # Calculate totals
    subtotal  = sum(i.price * i.qty for i in req.items)
    gst_rate  = 0.18
    gst_amt   = round(subtotal * gst_rate, 2)
    shipping  = 0.0   # free shipping at launch; calculate by pincode later
    total     = round(subtotal + gst_amt + shipping, 2)
    
    # Create Razorpay order for prepaid
    rzp_order_id = None
    if req.payment_method == PaymentMethod.PREPAID:
        rzp = razorpay_service.create_razorpay_order(total, order_id, req.customer_email)
        rzp_order_id = rzp["id"]
    
    # Save to DB
    order = Order(
        id                = order_id,
        razorpay_order_id = rzp_order_id,
        customer_name     = req.customer_name,
        customer_email    = req.customer_email,
        customer_phone    = req.customer_phone,
        address_line1     = req.address_line1,
        address_line2     = req.address_line2,
        city              = req.city,
        state             = req.state,
        pincode           = req.pincode,
        items             = [i.dict() for i in req.items],
        subtotal          = subtotal,
        gst_amount        = gst_amt,
        shipping_charge   = shipping,
        total             = total,
        payment_method    = req.payment_method,
        status            = OrderStatus.PENDING,
    )
    db.add(order)
    await db.flush()
    
    return OrderResponse(
        order_id          = order_id,
        razorpay_order_id = rzp_order_id,
        total             = total,
        status            = OrderStatus.PENDING
    )

@router.get("/{order_id}")
async def get_order(order_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order  = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order
