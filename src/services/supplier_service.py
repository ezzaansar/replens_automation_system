"""Supplier domain service functions."""

from typing import Optional, List

from sqlalchemy.orm import Session

from src.database import Supplier, ProductSupplier


def add_supplier(session: Session, name: str, **kwargs) -> Supplier:
    """Add a new supplier to the database."""
    supplier = Supplier(name=name, **kwargs)
    session.add(supplier)
    session.commit()
    return supplier


def get_supplier(session: Session, supplier_id: int) -> Optional[Supplier]:
    """Get a supplier by ID."""
    return session.query(Supplier).filter(Supplier.supplier_id == supplier_id).first()


def get_product_suppliers(session: Session, asin: str) -> List[ProductSupplier]:
    """Get all suppliers for a product, sorted by profitability."""
    return session.query(ProductSupplier)\
        .filter(ProductSupplier.asin == asin)\
        .order_by(ProductSupplier.profit_margin.desc())\
        .all()
