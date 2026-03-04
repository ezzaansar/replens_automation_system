"""
Tests for src/utils/profitability.py

Covers:
- estimate_amazon_fees: normal prices, zero, negative, category lookup, weight tiers
- calculate_profitability: normal inputs, zero cost, zero price, edge cases
- meets_profitability_thresholds: passing/failing thresholds, exact boundary values
- calculate_min_price: normal, edge cases
"""

from decimal import Decimal
from unittest.mock import patch, MagicMock

import pytest

from src.utils.profitability import (
    estimate_amazon_fees,
    calculate_profitability,
    meets_profitability_thresholds,
    calculate_min_price,
)
from src.config import AMAZON_REFERRAL_FEES, AMAZON_FBA_FEES


# ============================================================================
# estimate_amazon_fees tests
# ============================================================================
class TestEstimateAmazonFees:
    """Tests for Amazon fee estimation."""

    def test_default_category_referral_fee(self):
        """Default category should use 15% referral rate."""
        result = estimate_amazon_fees(Decimal("100.00"))
        assert result["referral_fee"] == Decimal("100.00") * Decimal("0.15")

    def test_apparel_category_referral_fee(self):
        """Apparel category should use 17% referral rate."""
        result = estimate_amazon_fees(Decimal("100.00"), category="apparel")
        assert result["referral_fee"] == Decimal("100.00") * Decimal("0.17")

    def test_electronics_category_referral_fee(self):
        result = estimate_amazon_fees(Decimal("50.00"), category="electronics")
        assert result["referral_fee"] == Decimal("50.00") * Decimal("0.15")

    def test_unknown_category_falls_back_to_default(self):
        """Unknown categories should use the default referral rate."""
        result = estimate_amazon_fees(Decimal("100.00"), category="nonexistent_category")
        default_rate = Decimal(str(AMAZON_REFERRAL_FEES["default"]))
        assert result["referral_fee"] == Decimal("100.00") * default_rate

    def test_case_insensitive_category(self):
        """Category lookup should be case-insensitive."""
        result_lower = estimate_amazon_fees(Decimal("100.00"), category="apparel")
        result_upper = estimate_amazon_fees(Decimal("100.00"), category="APPAREL")
        assert result_lower["referral_fee"] == result_upper["referral_fee"]

    def test_small_standard_fba_fee_tier(self):
        """Weight <= 1.0 lbs should use small_standard fee ($2.50)."""
        result = estimate_amazon_fees(Decimal("20.00"), weight_lbs=0.5)
        assert result["fba_fee"] == Decimal("2.50")

    def test_large_standard_fba_fee_tier(self):
        """Weight between 1.0 and 20.0 lbs should use large_standard ($3.50)."""
        result = estimate_amazon_fees(Decimal("20.00"), weight_lbs=5.0)
        assert result["fba_fee"] == Decimal("3.50")

    def test_small_oversize_fba_fee_tier(self):
        """Weight between 20.0 and 70.0 lbs should use small_oversize ($5.00)."""
        result = estimate_amazon_fees(Decimal("20.00"), weight_lbs=50.0)
        assert result["fba_fee"] == Decimal("5.00")

    def test_large_oversize_fba_fee_tier(self):
        """Weight between 70.0 and 150.0 lbs should use large_oversize ($8.00)."""
        result = estimate_amazon_fees(Decimal("20.00"), weight_lbs=100.0)
        assert result["fba_fee"] == Decimal("8.00")

    def test_weight_exactly_one_lb(self):
        """Weight exactly at 1.0 lb should be small_standard ($2.50)."""
        result = estimate_amazon_fees(Decimal("20.00"), weight_lbs=1.0)
        assert result["fba_fee"] == Decimal("2.50")

    def test_total_fees_is_sum(self):
        """total_fees should be referral_fee + fba_fee."""
        result = estimate_amazon_fees(Decimal("100.00"), weight_lbs=0.5)
        assert result["total_fees"] == result["referral_fee"] + result["fba_fee"]

    def test_zero_price(self):
        """Zero price should produce zero referral fee."""
        result = estimate_amazon_fees(Decimal("0.00"))
        assert result["referral_fee"] == Decimal("0.00")
        # fba_fee is still based on weight
        assert result["fba_fee"] > 0

    def test_negative_price(self):
        """Negative price produces negative referral fee (no input validation)."""
        result = estimate_amazon_fees(Decimal("-10.00"))
        assert result["referral_fee"] < 0

    def test_high_price(self):
        """Large price should scale referral fee proportionally."""
        result = estimate_amazon_fees(Decimal("1000.00"))
        assert result["referral_fee"] == Decimal("1000.00") * Decimal("0.15")

    def test_return_dict_keys(self):
        """Return dict should have exactly 3 keys."""
        result = estimate_amazon_fees(Decimal("50.00"))
        assert set(result.keys()) == {"referral_fee", "fba_fee", "total_fees"}

    def test_all_values_are_decimal(self):
        """All returned values should be Decimal type."""
        result = estimate_amazon_fees(Decimal("50.00"))
        for key, value in result.items():
            assert isinstance(value, Decimal), f"{key} is {type(value)}, expected Decimal"


# ============================================================================
# calculate_profitability tests
# ============================================================================
class TestCalculateProfitability:
    """Tests for profitability calculation."""

    def test_normal_profitable_case(self):
        """Standard profitable scenario."""
        result = calculate_profitability(
            selling_price=Decimal("50.00"),
            total_cost=Decimal("15.00"),
            amazon_fees=Decimal("10.00"),
        )
        assert result["net_profit"] == Decimal("25.00")
        assert result["profit_margin"] == pytest.approx(0.50)  # 25/50
        assert result["roi"] == pytest.approx(25.0 / 15.0)  # ~1.667

    def test_break_even(self):
        """When selling price equals cost + fees, profit should be zero."""
        result = calculate_profitability(
            selling_price=Decimal("25.00"),
            total_cost=Decimal("15.00"),
            amazon_fees=Decimal("10.00"),
        )
        assert result["net_profit"] == Decimal("0.00")
        assert result["profit_margin"] == pytest.approx(0.0)
        assert result["roi"] == pytest.approx(0.0)

    def test_losing_money(self):
        """When cost + fees exceed price, profit should be negative."""
        result = calculate_profitability(
            selling_price=Decimal("20.00"),
            total_cost=Decimal("15.00"),
            amazon_fees=Decimal("10.00"),
        )
        assert result["net_profit"] == Decimal("-5.00")
        assert result["profit_margin"] < 0

    def test_zero_selling_price(self):
        """Zero selling price should result in 0 margin (avoid division by zero)."""
        result = calculate_profitability(
            selling_price=Decimal("0.00"),
            total_cost=Decimal("10.00"),
            amazon_fees=Decimal("5.00"),
        )
        assert result["profit_margin"] == 0.0

    def test_zero_total_cost(self):
        """Zero total cost should result in 0 ROI (avoid division by zero)."""
        result = calculate_profitability(
            selling_price=Decimal("50.00"),
            total_cost=Decimal("0.00"),
            amazon_fees=Decimal("10.00"),
        )
        assert result["roi"] == 0.0
        assert result["net_profit"] == Decimal("40.00")

    def test_zero_fees(self):
        """Zero Amazon fees."""
        result = calculate_profitability(
            selling_price=Decimal("50.00"),
            total_cost=Decimal("20.00"),
            amazon_fees=Decimal("0.00"),
        )
        assert result["net_profit"] == Decimal("30.00")
        assert result["profit_margin"] == pytest.approx(0.60)

    def test_very_small_margin(self):
        """Very small profit scenario."""
        result = calculate_profitability(
            selling_price=Decimal("100.00"),
            total_cost=Decimal("85.00"),
            amazon_fees=Decimal("14.00"),
        )
        assert result["net_profit"] == Decimal("1.00")
        assert result["profit_margin"] == pytest.approx(0.01)

    def test_return_dict_keys(self):
        result = calculate_profitability(
            Decimal("50.00"), Decimal("20.00"), Decimal("10.00")
        )
        assert set(result.keys()) == {"net_profit", "profit_margin", "roi"}

    def test_margin_is_float(self):
        result = calculate_profitability(
            Decimal("50.00"), Decimal("20.00"), Decimal("10.00")
        )
        assert isinstance(result["profit_margin"], float)

    def test_roi_is_float(self):
        result = calculate_profitability(
            Decimal("50.00"), Decimal("20.00"), Decimal("10.00")
        )
        assert isinstance(result["roi"], float)


# ============================================================================
# meets_profitability_thresholds tests
# ============================================================================
class TestMeetsProfitabilityThresholds:
    """Tests for profitability threshold checking.

    Thresholds:
    - margin >= 0.25 (25%)
    - roi >= 1.0 (100%)
    - lead_time_days <= 30
    - reliability_score >= 70.0
    """

    def test_all_thresholds_met(self):
        """All criteria comfortably above thresholds."""
        assert meets_profitability_thresholds(
            profit_margin=0.35,
            roi=1.5,
            lead_time_days=14,
            reliability_score=90.0,
        ) is True

    def test_exact_threshold_values(self):
        """Exactly at all threshold boundaries should pass."""
        assert meets_profitability_thresholds(
            profit_margin=0.25,
            roi=1.0,
            lead_time_days=30,
            reliability_score=70.0,
        ) is True

    def test_margin_below_threshold(self):
        """Margin just below 25% should fail."""
        assert meets_profitability_thresholds(
            profit_margin=0.24,
            roi=1.5,
            lead_time_days=14,
            reliability_score=90.0,
        ) is False

    def test_roi_below_threshold(self):
        """ROI just below 100% should fail."""
        assert meets_profitability_thresholds(
            profit_margin=0.35,
            roi=0.99,
            lead_time_days=14,
            reliability_score=90.0,
        ) is False

    def test_lead_time_above_threshold(self):
        """Lead time above 30 days should fail."""
        assert meets_profitability_thresholds(
            profit_margin=0.35,
            roi=1.5,
            lead_time_days=31,
            reliability_score=90.0,
        ) is False

    def test_reliability_below_threshold(self):
        """Reliability below 70 should fail."""
        assert meets_profitability_thresholds(
            profit_margin=0.35,
            roi=1.5,
            lead_time_days=14,
            reliability_score=69.9,
        ) is False

    def test_all_thresholds_failed(self):
        """All criteria below thresholds."""
        assert meets_profitability_thresholds(
            profit_margin=0.10,
            roi=0.5,
            lead_time_days=60,
            reliability_score=50.0,
        ) is False

    def test_default_lead_time_passes(self):
        """Default lead_time_days=0 should pass the <= 30 check."""
        assert meets_profitability_thresholds(
            profit_margin=0.30,
            roi=1.5,
        ) is True

    def test_default_reliability_passes(self):
        """Default reliability_score=100.0 should pass the >= 70 check."""
        assert meets_profitability_thresholds(
            profit_margin=0.30,
            roi=1.5,
            lead_time_days=10,
        ) is True

    def test_zero_margin(self):
        assert meets_profitability_thresholds(
            profit_margin=0.0,
            roi=1.5,
            lead_time_days=14,
            reliability_score=90.0,
        ) is False

    def test_negative_margin(self):
        assert meets_profitability_thresholds(
            profit_margin=-0.10,
            roi=1.5,
            lead_time_days=14,
            reliability_score=90.0,
        ) is False

    def test_very_high_values_pass(self):
        """Extremely high values should pass."""
        assert meets_profitability_thresholds(
            profit_margin=0.90,
            roi=10.0,
            lead_time_days=1,
            reliability_score=100.0,
        ) is True

    def test_margin_slightly_above_threshold(self):
        assert meets_profitability_thresholds(
            profit_margin=0.251,
            roi=1.0,
            lead_time_days=30,
            reliability_score=70.0,
        ) is True


# ============================================================================
# calculate_min_price tests
# ============================================================================
class TestCalculateMinPrice:
    """Tests for minimum price calculation."""

    def test_normal_case(self):
        """Should return a price higher than cost."""
        min_price = calculate_min_price(Decimal("10.00"))
        assert min_price > Decimal("10.00")

    def test_zero_cost(self):
        """Zero cost should return just the FBA fee divided by denominator."""
        min_price = calculate_min_price(Decimal("0.00"))
        # (0 + 3.50) / (1 - 0.15 - 0.25) = 3.50 / 0.60 = 5.833...
        assert min_price > Decimal("0.00")

    def test_higher_cost_gives_higher_min_price(self):
        """Higher cost should produce a higher minimum price."""
        min_low = calculate_min_price(Decimal("10.00"))
        min_high = calculate_min_price(Decimal("30.00"))
        assert min_high > min_low

    def test_result_is_decimal(self):
        result = calculate_min_price(Decimal("20.00"))
        assert isinstance(result, Decimal)

    def test_apparel_category_higher_min(self):
        """Apparel (17% referral) should have a higher min price than default (15%)."""
        min_default = calculate_min_price(Decimal("20.00"), category="default")
        min_apparel = calculate_min_price(Decimal("20.00"), category="apparel")
        assert min_apparel > min_default
