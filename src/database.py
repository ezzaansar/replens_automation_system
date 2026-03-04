"""
Database engine, session, and operations for Amazon Replens Automation System.

ORM model definitions live in ``src.models``.  This module re-exports them
for backward compatibility so existing ``from src.database import Product``
statements continue to work.
"""

from decimal import Decimal
from typing import Optional, List

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from src.config import settings

# Re-export all models for backward compatibility
from src.models import (  # noqa: F401
    Base,
    Product,
    Supplier,
    ProductSupplier,
    Inventory,
    PurchaseOrder,
    Performance,
)

# Database Configuration
DATABASE_TYPE = settings.database_type
DATABASE_URL = settings.database_url

# Create engine based on database type
if DATABASE_TYPE == "sqlite":
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
else:  # PostgreSQL
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        echo=False
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================
def init_db():
    """Create all tables in the database."""
    Base.metadata.create_all(bind=engine)
    print("✓ Database initialized successfully")


def get_db() -> Session:
    """Get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# DATABASE OPERATIONS
# ============================================================================
class DatabaseOperations:
    """Thin facade that delegates to domain service modules.

    Kept for backward compatibility — callers can also import functions
    directly from ``src.services``.
    """

    @staticmethod
    def get_session() -> Session:
        """Get a new database session."""
        return SessionLocal()

    @staticmethod
    def add_product(session: Session, asin: str, title: str, category: str, **kwargs) -> Product:
        from src.services.product_service import add_product
        return add_product(session, asin, title, category, **kwargs)

    @staticmethod
    def get_product(session: Session, asin: str) -> Optional[Product]:
        from src.services.product_service import get_product
        return get_product(session, asin)

    @staticmethod
    def get_underserved_products(session: Session, limit: int = 50) -> List[Product]:
        from src.services.product_service import get_underserved_products
        return get_underserved_products(session, limit)

    @staticmethod
    def get_low_stock_products(session: Session) -> List[Product]:
        from src.services.product_service import get_low_stock_products
        return get_low_stock_products(session)

    @staticmethod
    def add_supplier(session: Session, name: str, **kwargs) -> Supplier:
        from src.services.supplier_service import add_supplier
        return add_supplier(session, name, **kwargs)

    @staticmethod
    def get_supplier(session: Session, supplier_id: int) -> Optional[Supplier]:
        from src.services.supplier_service import get_supplier
        return get_supplier(session, supplier_id)

    @staticmethod
    def get_product_suppliers(session: Session, asin: str) -> List[ProductSupplier]:
        from src.services.supplier_service import get_product_suppliers
        return get_product_suppliers(session, asin)

    @staticmethod
    def create_purchase_order(session: Session, po_id: str, asin: str, supplier_id: int,
                              quantity: int, unit_cost: Decimal) -> PurchaseOrder:
        from src.services.order_service import create_purchase_order
        return create_purchase_order(session, po_id, asin, supplier_id, quantity, unit_cost)

    @staticmethod
    def record_performance(session: Session, asin: str, units_sold: int, revenue: Decimal,
                           cost_of_goods: Decimal, amazon_fees: Decimal,
                           buy_box_owned: bool = False) -> Performance:
        from src.services.performance_service import record_performance
        return record_performance(session, asin, units_sold, revenue, cost_of_goods,
                                  amazon_fees, buy_box_owned)


if __name__ == "__main__":
    init_db()
