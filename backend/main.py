from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from database import create_tables
from routers import products, orders, payments, shipping, invoices

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create DB tables
    await create_tables()
    yield
    # Shutdown: cleanup if needed

app = FastAPI(
    title="Lumère API",
    description="Backend for Lumère D2C skincare brand",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://lumere.in", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router,  prefix="/api/products",  tags=["Products"])
app.include_router(orders.router,    prefix="/api/orders",    tags=["Orders"])
app.include_router(payments.router,  prefix="/api/payments",  tags=["Payments"])
app.include_router(shipping.router,  prefix="/api/shipping",  tags=["Shipping"])
app.include_router(invoices.router,  prefix="/api/invoices",  tags=["Invoices"])

@app.get("/")
async def root():
    return {"status": "Lumère API running", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "ok"}
