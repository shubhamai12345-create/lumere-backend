from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models.order import Order
from services import odoo_service

router = APIRouter()

@router.post("/{order_id}")
async def create_invoice(order_id: str, db: AsyncSession = Depends(get_db)):
    """Manually trigger Odoo invoice creation for an order (admin use)."""
    result = await db.execute(select(Order).where(Order.id == order_id))
    order  = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.odoo_invoice_id:
        return {"status": "already_invoiced", "invoice_id": order.odoo_invoice_id}

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
    }
    invoice_id = odoo_service.create_invoice(order_dict)
    order.odoo_invoice_id = invoice_id
    await db.commit()
    return {"status": "invoiced", "invoice_id": invoice_id,
            "pdf": odoo_service.get_invoice_pdf_url(invoice_id)}
