from sqlalchemy import Column, String, Float, Integer, Boolean, JSON
from database import Base

class Product(Base):
    __tablename__ = "products"

    id            = Column(String, primary_key=True)   # e.g. "NIA-10-30ML"
    slug          = Column(String, unique=True)         # e.g. "niacinamide-10-zinc-1"
    name          = Column(String, nullable=False)      # "Niacinamide 10% + Zinc 1%"
    tagline       = Column(String)                      # "Oil control · Pore minimising"
    description   = Column(String)
    
    # Ingredient transparency — the whole point
    active_inci   = Column(String)                      # "Niacinamide, Zinc PCA"
    concentration = Column(String)                      # "10% + 1%"
    full_inci     = Column(String)                      # Full INCI list for label
    ph_range      = Column(String)                      # "5.5 – 6.5"
    
    price         = Column(Float, nullable=False)
    mrp           = Column(Float, nullable=False)
    hsn_code      = Column(String, default="3304")      # GST HSN for cosmetics
    gst_rate      = Column(Float, default=18.0)
    
    volume_ml     = Column(Integer)
    weight_grams  = Column(Integer)                     # for shipping calculation
    
    stock         = Column(Integer, default=0)
    low_stock_alert = Column(Integer, default=50)       # alert when stock < this
    
    images        = Column(JSON, default=list)           # list of image URLs
    skin_types    = Column(JSON, default=list)           # ["oily", "combination"]
    concerns      = Column(JSON, default=list)           # ["acne", "pores"]
    
    is_active     = Column(Boolean, default=True)
