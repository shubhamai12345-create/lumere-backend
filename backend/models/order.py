from sqlalchemy import Column, String, Float, Integer, DateTime, JSON, Enum
from sqlalchemy.sql import func
import enum
from database import Base

class OrderStatus(str, enum.Enum):
    PENDING       = "pending"       # COD order placed, not yet paid
    PAID          = "paid"          # Razorpay payment confirmed
    PROCESSING    = "processing"    # Being packed
    SHIPPED       = "shipped"       # AWB generated, handed to courier
    OUT_FOR_DEL   = "out_for_delivery"
    DELIVERED     = "delivered"
    CANCELLED     = "cancelled"
    RTO           = "rto"           # Return to origin

class PaymentMethod(str, enum.Enum):
    PREPAID = "prepaid"
    COD     = "cod"

class Order(Base):
    __tablename__ = "orders"

    id                = Column(String, primary_key=True)        # e.g. LUM-2026-0001
    razorpay_order_id = Column(String, nullable=True)           # from Razorpay
    razorpay_payment_id = Column(String, nullable=True)
    
    # Customer
    customer_name     = Column(String, nullable=False)
    customer_email    = Column(String, nullable=False)
    customer_phone    = Column(String, nullable=False)
    
    # Shipping address
    address_line1     = Column(String, nullable=False)
    address_line2     = Column(String, nullable=True)
    city              = Column(String, nullable=False)
    state             = Column(String, nullable=False)
    pincode           = Column(String, nullable=False)
    
    # Items: [{"product_id": "NIA-10", "name": "Niacinamide 10%", "qty": 1, "price": 699}]
    items             = Column(JSON, nullable=False)
    
    subtotal          = Column(Float, nullable=False)
    shipping_charge   = Column(Float, default=0.0)
    gst_amount        = Column(Float, nullable=False)
    total             = Column(Float, nullable=False)
    
    payment_method    = Column(Enum(PaymentMethod), nullable=False)
    status            = Column(Enum(OrderStatus), default=OrderStatus.PENDING)
    
    # Shipping
    awb_number        = Column(String, nullable=True)           # courier tracking ID
    courier_name      = Column(String, nullable=True)
    shiprocket_order_id = Column(String, nullable=True)
    
    # Odoo
    odoo_invoice_id   = Column(String, nullable=True)
    
    created_at        = Column(DateTime(timezone=True), server_default=func.now())
    updated_at        = Column(DateTime(timezone=True), onupdate=func.now())
