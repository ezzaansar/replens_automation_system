"""Performance metrics domain service functions."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple

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


def get_sales_history(
    session: Session, asin: str, lookback_days: int = 90
) -> List[Tuple[datetime, int]]:
    """Return daily (date, units_sold) tuples for *asin*.

    Only rows where ``units_sold > 0`` are included (excludes repricing-only
    records).  Results are ordered by date ascending and limited to the last
    *lookback_days* days.  Uses the composite ``idx_asin_date`` index.
    """
    cutoff = datetime.utcnow() - timedelta(days=lookback_days)
    rows = (
        session.query(Performance.date, Performance.units_sold)
        .filter(
            Performance.asin == asin,
            Performance.units_sold > 0,
            Performance.date >= cutoff,
        )
        .order_by(Performance.date.asc())
        .all()
    )
    return [(row.date, row.units_sold) for row in rows]
