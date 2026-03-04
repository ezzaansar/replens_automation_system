"""PurchaseOrder ORM model."""

from datetime import datetime

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.orm import relationship

from src.models.base import Base


class PurchaseOrder(Base):
    """
    Tracks purchase orders for inventory replenishment.
    """
    __tablename__ = "purchase_orders"

    po_id = Column(String(50), primary_key=True, index=True)
    asin = Column(String(10), ForeignKey("products.asin"), index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.supplier_id"), index=True)

    # Order Details
    quantity = Column(Integer)
    unit_cost = Column(Numeric(10, 2))
    total_cost = Column(Numeric(10, 2))

    # Status & Tracking
    status = Column(String(20), default="pending", index=True)  # pending, confirmed, shipped, received, cancelled
    order_date = Column(DateTime, default=datetime.utcnow)
    expected_delivery = Column(DateTime, nullable=True)
    actual_delivery = Column(DateTime, nullable=True)

    # Notes
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    product = relationship("Product", back_populates="purchase_orders")
    supplier = relationship("Supplier", back_populates="purchase_orders")
