"""Supplier and ProductSupplier ORM models."""

from datetime import datetime

from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, ForeignKey, Numeric, Text
from sqlalchemy.orm import relationship

from src.models.base import Base


class Supplier(Base):
    """
    Represents a supplier/vendor for sourcing products.
    """
    __tablename__ = "suppliers"

    supplier_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), unique=True, index=True)
    website = Column(String(500), nullable=True)
    contact_email = Column(String(200), nullable=True)

    # Order Terms
    min_order_qty = Column(Integer, default=1)
    lead_time_days = Column(Integer, default=7)

    # Performance
    reliability_score = Column(Float, default=0.0)  # 0-100
    last_order_date = Column(DateTime, nullable=True)
    total_orders = Column(Integer, default=0)
    on_time_delivery_rate = Column(Float, default=1.0)  # 0-1

    # Status
    status = Column(String(20), default="active", index=True)  # active, inactive, blacklisted
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    product_suppliers = relationship("ProductSupplier", back_populates="supplier", cascade="all, delete-orphan")
    purchase_orders = relationship("PurchaseOrder", back_populates="supplier")


class ProductSupplier(Base):
    """
    Junction table linking products to suppliers with pricing information.
    """
    __tablename__ = "product_suppliers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    asin = Column(String(10), ForeignKey("products.asin"), index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.supplier_id"), index=True)

    # Pricing
    supplier_cost = Column(Numeric(10, 2))  # Cost per unit from supplier
    shipping_cost = Column(Numeric(10, 2), default=0)  # Shipping per unit
    total_cost = Column(Numeric(10, 2))  # Total landed cost

    # Profitability
    estimated_profit = Column(Numeric(10, 2))
    profit_margin = Column(Float)  # 0-1 (e.g., 0.25 = 25%)
    roi = Column(Float)  # Return on investment

    # Status
    is_preferred = Column(Boolean, default=False)
    status = Column(String(20), default="active")

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    product = relationship("Product", back_populates="suppliers")
    supplier = relationship("Supplier", back_populates="product_suppliers")
