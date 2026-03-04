"""
Profitability calculation utilities.

Shared by Phase 2 (discovery), Phase 3 (sourcing), and Phase 4 (repricing).
Extracts and centralizes the fee estimation and profit math.
"""

from decimal import Decimal
from typing import Dict, Any

from src.config import settings, AMAZON_REFERRAL_FEES, AMAZON_FBA_FEES


def estimate_amazon_fees(
    price: Decimal, category: str = "default", weight_lbs: float = 1.0
) -> Dict[str, Decimal]:
    """
    Estimate Amazon fees for a product based on price, category, and weight.

    Args:
        price: Selling price
        category: Product category for referral fee lookup
        weight_lbs: Product weight in pounds for FBA fee tier

    Returns:
        Dict with referral_fee, fba_fee, total_fees
    """
    # Referral fee
    referral_rate = Decimal(
        str(AMAZON_REFERRAL_FEES.get(category.lower(), AMAZON_REFERRAL_FEES["default"]))
    )
    referral_fee = price * referral_rate

    # FBA fee based on weight tier
    fba_fee = Decimal("3.50")  # default: large_standard
    for tier_name, tier_data in AMAZON_FBA_FEES.items():
        if weight_lbs <= tier_data["weight_limit"]:
            fba_fee = Decimal(str(tier_data["fee"]))
            break

    return {
        "referral_fee": referral_fee,
        "fba_fee": fba_fee,
        "total_fees": referral_fee + fba_fee,
    }


def calculate_profitability(
    selling_price: Decimal, total_cost: Decimal, amazon_fees: Decimal
) -> Dict[str, Any]:
    """
    Calculate profit metrics given price, cost, and fees.

    Args:
        selling_price: Amazon selling price
        total_cost: Total landed cost (supplier cost + shipping)
        amazon_fees: Total Amazon fees (referral + FBA)

    Returns:
        Dict with net_profit, profit_margin, roi
    """
    net_profit = selling_price - total_cost - amazon_fees
    profit_margin = float(net_profit / selling_price) if selling_price > 0 else 0.0
    roi = float(net_profit / total_cost) if total_cost > 0 else 0.0

    return {
        "net_profit": net_profit,
        "profit_margin": profit_margin,
        "roi": roi,
    }


def meets_profitability_thresholds(
    profit_margin: float,
    roi: float,
    lead_time_days: int = 0,
    reliability_score: float = 100.0,
) -> bool:
    """
    Check if a product-supplier combination meets all profitability thresholds.

    Thresholds from config:
        - Margin >= 25% (settings.min_profit_margin)
        - ROI >= 100% (settings.min_roi)
        - Lead time <= 30 days
        - Supplier reliability >= 70 (out of 100)

    Args:
        profit_margin: 0-1 float (e.g., 0.25 = 25%)
        roi: 0+ float (e.g., 1.0 = 100%)
        lead_time_days: Supplier lead time in days
        reliability_score: Supplier reliability 0-100

    Returns:
        True if all thresholds are met
    """
    return (
        profit_margin >= settings.min_profit_margin
        and roi >= settings.min_roi
        and lead_time_days <= 30
        and reliability_score >= 70.0
    )


def calculate_min_price(total_cost: Decimal, category: str = "default") -> Decimal:
    """
    Calculate the minimum selling price to meet profit margin thresholds.

    Used by the repricing engine to set price floors.

    Args:
        total_cost: Total landed cost (supplier + shipping)
        category: Product category for fee calculation

    Returns:
        Minimum selling price
    """
    # min_price = (total_cost + fba_fee) / (1 - referral_rate - min_margin)
    referral_rate = Decimal(
        str(AMAZON_REFERRAL_FEES.get(category.lower(), AMAZON_REFERRAL_FEES["default"]))
    )
    min_margin = Decimal(str(settings.min_profit_margin))
    fba_fee = Decimal("3.50")  # default tier

    denominator = Decimal("1") - referral_rate - min_margin
    if denominator <= 0:
        # Edge case: fees + margin exceed 100%, return a safe fallback
        return total_cost * Decimal("3")

    return (total_cost + fba_fee) / denominator
