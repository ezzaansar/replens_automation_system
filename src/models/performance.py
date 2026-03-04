"""Performance ORM model."""

from datetime import datetime

from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, ForeignKey, Numeric, Index
from sqlalchemy.orm import relationship

from src.models.base import Base


class Performance(Base):
    """
    Daily performance metrics for each product.
    """
    __tablename__ = "performance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    asin = Column(String(10), ForeignKey("products.asin"), index=True)
    date = Column(DateTime, default=datetime.utcnow, index=True)

    # Sales Metrics
    units_sold = Column(Integer, default=0)
    revenue = Column(Numeric(10, 2), default=0)
    cost_of_goods = Column(Numeric(10, 2), default=0)
    amazon_fees = Column(Numeric(10, 2), default=0)
    net_profit = Column(Numeric(10, 2), default=0)

    # Buy Box Metrics
    buy_box_owned = Column(Boolean, default=False)
    buy_box_percentage = Column(Float, default=0.0)  # 0-1

    # Pricing & Competition
    price = Column(Numeric(10, 2), nullable=True)
    competitor_price = Column(Numeric(10, 2), nullable=True)
    sales_rank = Column(Integer, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    product = relationship("Product", back_populates="performance")

    # Indexes
    __table_args__ = (
        Index('idx_asin_date', 'asin', 'date'),
    )
