"""Product ORM model."""

from datetime import datetime

from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, Numeric, Text, Index
from sqlalchemy.orm import relationship

from src.models.base import Base


class Product(Base):
    """
    Represents an Amazon product (ASIN) being tracked for Replens opportunities.
    """
    __tablename__ = "products"

    asin = Column(String(10), primary_key=True, index=True)
    upc = Column(String(14), nullable=True, index=True)
    sku = Column(String(40), nullable=True, index=True)
    title = Column(String(500))
    category = Column(String(200))

    # Current Metrics
    current_price = Column(Numeric(10, 2))
    sales_rank = Column(Integer, nullable=True)
    estimated_monthly_sales = Column(Integer, default=0)
    profit_potential = Column(Numeric(10, 2), default=0)

    # Competition Metrics
    num_sellers = Column(Integer, default=0)
    num_fba_sellers = Column(Integer, default=0)
    buy_box_owner = Column(String(200), nullable=True)

    # Price History
    price_history_avg = Column(Numeric(10, 2), nullable=True)
    price_stability = Column(Numeric(10, 2), nullable=True)

    # Classification
    is_underserved = Column(Boolean, default=False, index=True)
    opportunity_score = Column(Float, default=0.0)  # 0-100

    # Status
    status = Column(String(20), default="active", index=True)  # active, archived, rejected
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    suppliers = relationship("ProductSupplier", back_populates="product", cascade="all, delete-orphan")
    inventory = relationship("Inventory", back_populates="product", uselist=False, cascade="all, delete-orphan")
    purchase_orders = relationship("PurchaseOrder", back_populates="product", cascade="all, delete-orphan")
    performance = relationship("Performance", back_populates="product", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_status_score', 'status', 'opportunity_score'),
        Index('idx_underserved', 'is_underserved'),
    )
