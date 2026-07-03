from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models.product import Product

router = APIRouter()

@router.get("/")
async def list_products(db: AsyncSession = Depends(get_db)):
    result   = await db.execute(select(Product).where(Product.is_active == True))
    products = result.scalars().all()
    return products

@router.get("/{slug}")
async def get_product(slug: str, db: AsyncSession = Depends(get_db)):
    result  = await db.execute(select(Product).where(Product.slug == slug))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
