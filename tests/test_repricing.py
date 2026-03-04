"""
Tests for Phase 4: Dynamic Repricing Engine

Covers:
- determine_new_price: undercut, clamped-to-floor, own-buy-box, already-below, no-data
- calculate_price_floor: with and without preferred supplier
- reprice_product: dry_run vs live mode
- run: 403 handling disables pricing for rest of run

Uses in-memory SQLite via conftest fixtures + mocked SP-API.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.database import (
    Base, Product, Supplier, ProductSupplier, Inventory, Performance,
)
from src.api_wrappers.amazon_sp_api import AmazonSPAPI
from src.phases.phase_4_repricing import RepricingEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_repriceable_product(session, sample_product_data, sample_supplier_data):
    """Insert a product with inventory and a preferred supplier."""
    product = Product(**sample_product_data)
    session.add(product)
    session.flush()

    supplier = Supplier(**sample_supplier_data)
    session.add(supplier)
    session.flush()

    ps = ProductSupplier(
        asin=product.asin,
        supplier_id=supplier.supplier_id,
        supplier_cost=Decimal("8.00"),
        shipping_cost=Decimal("2.00"),
        total_cost=Decimal("10.00"),
        estimated_profit=Decimal("12.00"),
        profit_margin=0.40,
        roi=1.20,
        is_preferred=True,
    )
    session.add(ps)

    inv = Inventory(asin=product.asin, current_stock=50, available=50)
    session.add(inv)

    session.commit()
    return product


# ---------------------------------------------------------------------------
# determine_new_price tests
# ---------------------------------------------------------------------------

class TestDetermineNewPrice:

    def test_undercut_buy_box(self, db_session, sample_product_data, sample_supplier_data):
        """When our price > Buy Box, target = BB - $0.01."""
        product = _create_repriceable_product(db_session, sample_product_data, sample_supplier_data)
        engine = RepricingEngine(session=db_session)

        competitor_data = {
            "buy_box_price": Decimal("25.00"),
            "our_price": Decimal("29.99"),
            "buy_box_is_ours": False,
        }
        price_floor = Decimal("15.00")

        new_price = engine.determine_new_price(product, competitor_data, price_floor)
        assert new_price == Decimal("24.99")

    def test_clamped_to_floor(self, db_session, sample_product_data, sample_supplier_data):
        """When BB - $0.01 is below floor, use floor instead."""
        product = _create_repriceable_product(db_session, sample_product_data, sample_supplier_data)
        engine = RepricingEngine(session=db_session)

        competitor_data = {
            "buy_box_price": Decimal("15.00"),
            "our_price": Decimal("29.99"),
            "buy_box_is_ours": False,
        }
        price_floor = Decimal("20.00")

        new_price = engine.determine_new_price(product, competitor_data, price_floor)
        assert new_price == Decimal("20.00")

    def test_own_buy_box(self, db_session, sample_product_data, sample_supplier_data):
        """When we own the Buy Box, no price change."""
        product = _create_repriceable_product(db_session, sample_product_data, sample_supplier_data)
        engine = RepricingEngine(session=db_session)

        competitor_data = {
            "buy_box_price": Decimal("29.99"),
            "our_price": Decimal("29.99"),
            "buy_box_is_ours": True,
        }

        new_price = engine.determine_new_price(product, competitor_data, Decimal("15.00"))
        assert new_price is None

    def test_already_below_buy_box(self, db_session, sample_product_data, sample_supplier_data):
        """When our price <= Buy Box, don't undercut further (anti-race-to-bottom)."""
        product = _create_repriceable_product(db_session, sample_product_data, sample_supplier_data)
        engine = RepricingEngine(session=db_session)

        competitor_data = {
            "buy_box_price": Decimal("30.00"),
            "our_price": Decimal("29.99"),
            "buy_box_is_ours": False,
        }

        new_price = engine.determine_new_price(product, competitor_data, Decimal("15.00"))
        assert new_price is None

    def test_no_competitor_data(self, db_session, sample_product_data, sample_supplier_data):
        """When competitor data is None, return None."""
        product = _create_repriceable_product(db_session, sample_product_data, sample_supplier_data)
        engine = RepricingEngine(session=db_session)

        new_price = engine.determine_new_price(product, None, Decimal("15.00"))
        assert new_price is None


# ---------------------------------------------------------------------------
# calculate_price_floor tests
# ---------------------------------------------------------------------------

class TestCalculatePriceFloor:

    def test_with_preferred_supplier(self, db_session, sample_product_data, sample_supplier_data):
        """Floor should be derived from preferred supplier total_cost."""
        product = _create_repriceable_product(db_session, sample_product_data, sample_supplier_data)
        engine = RepricingEngine(session=db_session)

        floor = engine.calculate_price_floor(product)
        assert floor is not None
        # With total_cost=10.00, category=Home (15% referral), 25% margin, $3.50 FBA:
        # floor = (10.00 + 3.50) / (1 - 0.15 - 0.25) = 13.50 / 0.60 = 22.50
        assert floor == Decimal("22.50")

    def test_no_preferred_supplier(self, db_session, sample_product_data):
        """No preferred supplier → floor is None."""
        product = Product(**sample_product_data)
        db_session.add(product)
        db_session.commit()

        engine = RepricingEngine(session=db_session)
        floor = engine.calculate_price_floor(product)
        assert floor is None


# ---------------------------------------------------------------------------
# reprice_product tests
# ---------------------------------------------------------------------------

class TestRepriceProduct:

    def test_dry_run(self, db_session, sample_product_data, sample_supplier_data):
        """In dry_run mode: no SP-API call, no DB price update."""
        product = _create_repriceable_product(db_session, sample_product_data, sample_supplier_data)
        mock_sp = MagicMock(spec=AmazonSPAPI)
        engine = RepricingEngine(session=db_session, sp_api=mock_sp)

        # Patch competitor data to trigger a reprice decision
        engine.get_competitor_pricing = MagicMock(return_value={
            "buy_box_price": Decimal("25.00"),
            "our_price": Decimal("29.99"),
            "buy_box_is_ours": False,
        })

        with patch("src.phases.phase_4_repricing.settings") as mock_settings:
            mock_settings.dry_run = True
            mock_settings.price_adjustment_amount = Decimal("0.01")
            mock_settings.min_profit_margin = 0.25

            result = engine.reprice_product(product)

        assert result["action"] == "dry_run"
        assert result["new_price"] == Decimal("24.99")
        # SP-API update_price should NOT have been called
        mock_sp.update_price.assert_not_called()
        # Product price in DB unchanged
        assert product.current_price == Decimal("29.99")

    def test_live_reprice(self, db_session, sample_product_data, sample_supplier_data):
        """In live mode: SP-API called, DB updated."""
        product = _create_repriceable_product(db_session, sample_product_data, sample_supplier_data)
        mock_sp = MagicMock(spec=AmazonSPAPI)
        engine = RepricingEngine(session=db_session, sp_api=mock_sp)

        engine.get_competitor_pricing = MagicMock(return_value={
            "buy_box_price": Decimal("25.00"),
            "our_price": Decimal("29.99"),
            "buy_box_is_ours": False,
        })

        with patch("src.phases.phase_4_repricing.settings") as mock_settings:
            mock_settings.dry_run = False
            mock_settings.price_adjustment_amount = Decimal("0.01")
            mock_settings.min_profit_margin = 0.25

            result = engine.reprice_product(product)

        assert result["action"] == "repriced"
        assert result["new_price"] == Decimal("24.99")
        mock_sp.update_price.assert_called_once_with(product.asin, Decimal("24.99"))
        assert product.current_price == Decimal("24.99")


# ---------------------------------------------------------------------------
# run / 403 handling test
# ---------------------------------------------------------------------------

class TestRunHandles403:

    def test_403_disables_pricing_for_rest_of_run(
        self, db_session, sample_product_data, sample_supplier_data
    ):
        """After a 403 from SP-API, pricing calls should be disabled for remaining products."""
        # Create two products
        p1 = _create_repriceable_product(db_session, sample_product_data, sample_supplier_data)

        p2_data = dict(sample_product_data, asin="B0SECOND01", title="Second Product")
        s2_data = dict(sample_supplier_data, name="Second Supplier")
        p2 = _create_repriceable_product(db_session, p2_data, s2_data)

        # Build a mock SP-API that raises 403 on first call
        mock_sp = MagicMock(spec=AmazonSPAPI)
        exc = Exception("Forbidden")
        mock_response = MagicMock()
        mock_response.status_code = 403
        exc.response = mock_response
        mock_sp.get_product_pricing.side_effect = exc

        engine = RepricingEngine(session=db_session, sp_api=mock_sp)

        with patch("src.phases.phase_4_repricing.settings") as mock_settings:
            mock_settings.dry_run = False
            mock_settings.price_adjustment_amount = Decimal("0.01")
            mock_settings.min_profit_margin = 0.25

            with patch("src.phases.phase_4_repricing.get_repriceable_products", return_value=[p1, p2]):
                summary = engine.run()

        # After first product triggers 403, pricing should be disabled
        assert engine._sp_api_pricing_available is False
        # get_product_pricing should have been called only once (for p1)
        assert mock_sp.get_product_pricing.call_count == 1
