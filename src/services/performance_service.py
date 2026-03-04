"""Performance metrics domain service functions."""

from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from src.models import Performance


def record_performance(session: Session, asin: str, units_sold: int, revenue: Decimal,
                       cost_of_goods: Decimal, amazon_fees: Decimal,
                       buy_box_owned: bool = False) -> Performance:
    """Record daily performance metrics."""
    net_profit = revenue - cost_of_goods - amazon_fees
    perf = Performance(
        asin=asin,
        units_sold=units_sold,
        revenue=revenue,
        cost_of_goods=cost_of_goods,
        amazon_fees=amazon_fees,
        net_profit=net_profit,
        buy_box_owned=buy_box_owned,
    )
    session.add(perf)
    session.commit()
    return perf


def record_repricing_action(
    session: Session,
    asin: str,
    our_price: Decimal,
    competitor_price: Optional[Decimal] = None,
    buy_box_owned: bool = False,
    buy_box_percentage: float = 0.0,
) -> Performance:
    """Record a repricing observation/action to the Performance table.

    Unlike ``record_performance`` (which records daily sales metrics), this
    function captures a point-in-time pricing snapshot used by the repricing
    engine.
    """
    perf = Performance(
        asin=asin,
        price=our_price,
        competitor_price=competitor_price,
        buy_box_owned=buy_box_owned,
        buy_box_percentage=buy_box_percentage,
    )
    session.add(perf)
    session.commit()
    return perf
