"""Purchase order domain service functions."""

from decimal import Decimal

from sqlalchemy.orm import Session

from src.models import PurchaseOrder


def create_purchase_order(session: Session, po_id: str, asin: str, supplier_id: int,
                          quantity: int, unit_cost: Decimal) -> PurchaseOrder:
    """Create a new purchase order."""
    po = PurchaseOrder(
        po_id=po_id,
        asin=asin,
        supplier_id=supplier_id,
        quantity=quantity,
        unit_cost=unit_cost,
        total_cost=Decimal(quantity) * unit_cost,
    )
    session.add(po)
    session.commit()
    return po
