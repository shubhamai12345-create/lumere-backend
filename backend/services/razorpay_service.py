import os, hmac, hashlib
import razorpay

client = razorpay.Client(
    auth=(os.getenv("RAZORPAY_KEY_ID"), os.getenv("RAZORPAY_KEY_SECRET"))
)

def create_razorpay_order(amount_inr: float, order_id: str, customer_email: str) -> dict:
    """
    Create a Razorpay order. amount_inr is the total in rupees.
    Returns the Razorpay order object with id, amount, currency.
    """
    return client.order.create({
        "amount":   int(amount_inr * 100),   # Razorpay takes paise
        "currency": "INR",
        "receipt":  order_id,
        "notes": {
            "lumere_order_id": order_id,
            "customer_email":  customer_email,
        }
    })

def verify_payment_signature(
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str
) -> bool:
    """
    Verify Razorpay webhook/checkout signature.
    Called after the customer completes payment on the frontend.
    Returns True if signature is valid (payment is genuine).
    """
    secret = os.getenv("RAZORPAY_KEY_SECRET", "").encode()
    body   = f"{razorpay_order_id}|{razorpay_payment_id}".encode()
    digest = hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, razorpay_signature)

def get_payment_details(payment_id: str) -> dict:
    """Fetch full payment details from Razorpay."""
    return client.payment.fetch(payment_id)

def initiate_refund(payment_id: str, amount_inr: float) -> dict:
    """Refund a payment. amount_inr = amount to refund (can be partial)."""
    return client.payment.refund(payment_id, {
        "amount": int(amount_inr * 100),
        "speed":  "normal"
    })
