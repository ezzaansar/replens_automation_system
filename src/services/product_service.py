"""Product domain service functions."""

from typing import Optional, List

from sqlalchemy.orm import Session

from src.models import Product, Inventory, ProductSupplier


def add_product(session: Session, asin: str, title: str, category: str, **kwargs) -> Product:
    """Add a new product to the database."""
    product = Product(asin=asin, title=title, category=category, **kwargs)
    session.add(product)
    session.commit()
    return product


def get_product(session: Session, asin: str) -> Optional[Product]:
    """Get a product by ASIN."""
    return session.query(Product).filter(Product.asin == asin).first()


def get_underserved_products(session: Session, limit: int = 50) -> List[Product]:
    """Get top underserved products by opportunity score."""
    return session.query(Product)\
        .filter(Product.is_underserved == True, Product.status == "active")\
        .order_by(Product.opportunity_score.desc())\
        .limit(limit)\
        .all()


def get_low_stock_products(session: Session) -> List[Product]:
    """Get products that need reordering."""
    return session.query(Product)\
        .join(Inventory)\
        .filter(Inventory.needs_reorder == True)\
        .all()


def get_repriceable_products(session: Session, limit: int = 100) -> List[Product]:
    """Get active products with inventory and a preferred supplier.

    These are products eligible for repricing — they have stock in FBA
    and a known cost basis via a preferred supplier.

    Ordered by opportunity_score descending.
    """
    return session.query(Product)\
        .join(Inventory)\
        .join(Product.suppliers)\
        .filter(
            Product.status == "active",
            Inventory.current_stock > 0,
            ProductSupplier.is_preferred == True,
        )\
        .order_by(Product.opportunity_score.desc())\
        .limit(limit)\
        .all()
