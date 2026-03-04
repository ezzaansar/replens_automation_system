"""Performance metrics domain service functions."""

from decimal import Decimal

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
