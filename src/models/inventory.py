"""Inventory ORM model."""

from datetime import datetime

from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from src.models.base import Base


class Inventory(Base):
    """
    Tracks current and forecasted inventory levels.
    """
    __tablename__ = "inventory"

    asin = Column(String(10), ForeignKey("products.asin"), primary_key=True)

    # Current Levels
    current_stock = Column(Integer, default=0)
    reserved = Column(Integer, default=0)
    available = Column(Integer, default=0)

    # Reorder Parameters
    reorder_point = Column(Integer, default=0)
    safety_stock = Column(Integer, default=0)

    # Forecasts
    forecasted_stock_30d = Column(Integer, nullable=True)
    forecasted_stock_60d = Column(Integer, nullable=True)

    # Timing
    last_restock_date = Column(DateTime, nullable=True)
    days_of_supply = Column(Float, default=0)  # Days until stockout

    # Status
    needs_reorder = Column(Boolean, default=False, index=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    product = relationship("Product", back_populates="inventory")
