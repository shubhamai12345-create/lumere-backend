# Lumère — D2C Brand Backend

> Skincare named after what's in it. No Shopify. Full control.

## Project structure

```
lumere/
├── backend/                   ← FastAPI (Python) — deploy to Railway
│   ├── main.py                ← App entry point, routes registered here
│   ├── database.py            ← PostgreSQL connection + session
│   ├── requirements.txt
│   ├── .env.example           ← Copy to .env, fill in all keys
│   ├── models/
│   │   ├── order.py           ← Order, OrderStatus, PaymentMethod
│   │   └── product.py         ← Product with INCI, concentration, stock
│   ├── routers/
│   │   ├── products.py        ← GET /api/products, /api/products/:slug
│   │   ├── orders.py          ← POST /api/orders  (create order + Razorpay)
│   │   ├── payments.py        ← POST /api/payments/verify + /webhook
│   │   ├── shipping.py        ← GET  /api/shipping/estimate/:pincode
│   │   │                         GET  /api/shipping/track/:awb
│   │   └── invoices.py        ← POST /api/invoices/:order_id
│   └── services/
│       ├── razorpay_service.py  ← Create order, verify signature, refund
│       ├── shiprocket_service.py← Create shipment, get AWB, track
│       └── odoo_service.py      ← Create invoice via Odoo JSON-RPC API
│
└── frontend/                  ← Next.js 14 — deploy to Vercel
    (to be built next)
```

---

## The complete order flow

```
Customer hits "Place Order"
        ↓
POST /api/orders/
  → Creates Order record in PostgreSQL (status: PENDING)
  → If PREPAID: calls Razorpay to create a payment order
  → Returns: { order_id, razorpay_order_id, total }
        ↓
Frontend opens Razorpay checkout
Customer pays (UPI / card / net banking)
Razorpay calls the success callback on frontend
        ↓
POST /api/payments/verify
  → Verifies HMAC signature (proves payment is genuine)
  → Marks order status: PAID
  → Background: calls Shiprocket → gets AWB number
  → Background: calls Odoo → creates GST invoice, emails customer
  → Returns: { status: "payment_verified", order_id }
        ↓
Frontend shows Order Confirmed page
Customer receives:
  - Email with order confirmation + AWB tracking link (Shiprocket)
  - Email with GST invoice PDF (Odoo)
        ↓
GET /api/shipping/track/:awb
  → Customer visits /track/[awb] on the website
  → Returns real-time courier status
```

---

## Environment variables (all required)

Copy `.env.example` to `.env` and fill in every value.

| Variable | Where to get it |
|---|---|
| `DATABASE_URL` | Railway → Your PostgreSQL service → Connect tab |
| `RAZORPAY_KEY_ID` | dashboard.razorpay.com → Settings → API Keys |
| `RAZORPAY_KEY_SECRET` | Same as above |
| `RAZORPAY_WEBHOOK_SECRET` | Razorpay → Webhooks → Create → note the secret |
| `SHIPROCKET_EMAIL` | Your shiprocket.in login email |
| `SHIPROCKET_PASSWORD` | Your shiprocket.in login password |
| `ODOO_URL` | https://yourcompany.odoo.com |
| `ODOO_DB` | The database name shown in Odoo URL |
| `ODOO_USERNAME` | Your Odoo login email |
| `ODOO_API_KEY` | Odoo → Settings → Technical → API Keys → Create |

---

## Local development

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # fill in your keys
uvicorn main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

---

## Deploy to Railway

1. Push this repo to GitHub
2. Railway → New Project → Deploy from GitHub
3. Select the `backend/` folder as the root
4. Add all env vars from `.env.example` in Railway's Variables tab
5. Railway auto-detects FastAPI and runs `uvicorn main:app`

---

## Setting up Odoo (free, 5 minutes)

1. Go to [odoo.com](https://odoo.com) → Start for free
2. During setup, select **only** the **Invoicing** app
   *(selecting more than one app activates the paid tier)*
3. Inside Odoo: Settings → Technical → API Keys → Create API Key
4. Copy the key into your `.env` as `ODOO_API_KEY`
5. In Odoo's Invoicing settings, configure your GST tax rates (18%) and company GSTIN

---

## Setting up Razorpay (10 minutes)

1. Register at [razorpay.com](https://razorpay.com)
2. Complete KYC (business documents, bank account)
3. Settings → API Keys → Generate Key Pair (live or test)
4. Webhooks → Add endpoint: `https://your-backend.railway.app/api/payments/webhook`
   Select event: `payment.captured`

---

## Setting up Shiprocket (15 minutes)

1. Register at [shiprocket.in](https://shiprocket.in)
2. Add your warehouse address (Delhi) under Settings → Pickup Locations
3. Name it "Primary" — this matches the `pickup_location` in the service file
4. Enable cash on delivery in your Shiprocket account settings
