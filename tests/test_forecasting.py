"""
Tests for Phase 5: Inventory Forecasting Engine

Covers:
- Tier selection based on data-point count
- Forecasting: Tier 1 (Keepa), Tier 2 (exponential smoothing), Tier 3 fallback
- Inventory forecast field calculations
- Auto-PO generation (created, skipped in dry_run, skipped when active PO exists)
- Integration: full single-product workflow, SP-API 403 handling

Uses in-memory SQLite via conftest fixtures + mocked dependencies.
"""

import math
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.database import (
    Base, Product, Supplier, ProductSupplier, Inventory, PurchaseOrder, Performance,
)
from src.api_wrappers.amazon_sp_api import AmazonSPAPI
from src.phases.phase_5_forecasting import ForecastingEngine, _MIN_DAILY_DEMAND


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_forecastable_product(session, sample_product_data, sample_supplier_data,
                                  current_stock=100):
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

    inv = Inventory(asin=product.asin, current_stock=current_stock, available=current_stock)
    session.add(inv)

    session.commit()
    return product


def _make_history(n_days, units_per_day=5):
    """Generate *n_days* of synthetic daily sales history."""
    base = datetime.utcnow() - timedelta(days=n_days)
    return [(base + timedelta(days=i), units_per_day) for i in range(n_days)]


# ---------------------------------------------------------------------------
# Tier selection tests
# ---------------------------------------------------------------------------

class TestTierSelection:

    def test_tier_selection_below_14(self, db_session):
        engine = ForecastingEngine(session=db_session)
        assert engine._select_tier(0) == 1
        assert engine._select_tier(13) == 1

    def test_tier_selection_14_to_59(self, db_session):
        engine = ForecastingEngine(session=db_session)
        assert engine._select_tier(14) == 2
        assert engine._select_tier(59) == 2

    def test_tier_selection_60_plus(self, db_session):
        engine = ForecastingEngine(session=db_session)
        assert engine._select_tier(60) == 3
        assert engine._select_tier(200) == 3


# ---------------------------------------------------------------------------
# Forecasting tests
# ---------------------------------------------------------------------------

class TestForecasting:

    def test_tier1_uses_estimated_monthly_sales(
        self, db_session, sample_product_data, sample_supplier_data
    ):
        """60 monthly sales → 2.0 daily demand."""
        data = dict(sample_product_data, estimated_monthly_sales=60)
        product = _create_forecastable_product(db_session, data, sample_supplier_data)
        engine = ForecastingEngine(session=db_session)

        # No history → Tier 1
        demand, tier = engine.forecast_daily_demand(product, [])
        assert tier == 1
        assert demand == pytest.approx(2.0)

    def test_tier1_zero_sales_clamped(
        self, db_session, sample_product_data, sample_supplier_data
    ):
        """0 monthly sales → clamped to _MIN_DAILY_DEMAND after forecast_daily_demand."""
        data = dict(sample_product_data, estimated_monthly_sales=0)
        product = _create_forecastable_product(db_session, data, sample_supplier_data)
        engine = ForecastingEngine(session=db_session)

        demand, tier = engine.forecast_daily_demand(product, [])
        assert tier == 1
        assert demand == _MIN_DAILY_DEMAND

    def test_tier2_exponential_smoothing(
        self, db_session, sample_product_data, sample_supplier_data
    ):
        """20 data points of constant 5/day → ~5.0 daily demand."""
        product = _create_forecastable_product(db_session, sample_product_data, sample_supplier_data)
        engine = ForecastingEngine(session=db_session)

        history = _make_history(20, units_per_day=5)
        demand, tier = engine.forecast_daily_demand(product, history)
        assert tier == 2
        assert demand == pytest.approx(5.0, abs=0.5)

    def test_tier3_falls_back_to_tier2_on_import_error(
        self, db_session, sample_product_data, sample_supplier_data
    ):
        """When Prophet import fails, Tier 3 falls back to Tier 2 and still returns valid result."""
        product = _create_forecastable_product(db_session, sample_product_data, sample_supplier_data)
        engine = ForecastingEngine(session=db_session)

        history = _make_history(70, units_per_day=5)

        with patch.dict("sys.modules", {"prophet": None}):
            demand, tier = engine.forecast_daily_demand(product, history)

        # Should have attempted Tier 3 but selected it regardless of fallback
        assert tier == 3
        assert demand > 0


# ---------------------------------------------------------------------------
# Inventory update tests
# ---------------------------------------------------------------------------

class TestUpdateInventoryForecast:

    def test_update_inventory_forecast_calculations(
        self, db_session, sample_product_data, sample_supplier_data
    ):
        """stock=100, demand=3.0 → verify all computed fields."""
        product = _create_forecastable_product(db_session, sample_product_data, sample_supplier_data,
                                                current_stock=100)
        engine = ForecastingEngine(session=db_session)

        with patch("src.phases.phase_5_forecasting.settings") as mock_settings:
            mock_settings.safety_stock_days = 7
            mock_settings.reorder_point_multiplier = 1.5

            result = engine.update_inventory_forecast(product, daily_demand=3.0)

        assert result["forecasted_stock_30d"] == 100 - math.ceil(3.0 * 30)  # 100 - 90 = 10
        assert result["forecasted_stock_60d"] == 100 - math.ceil(3.0 * 60)  # 100 - 180 = -80
        assert result["days_of_supply"] == pytest.approx(33.3, abs=0.1)
        assert result["safety_stock"] == math.ceil(3.0 * 7)  # 21
        assert result["reorder_point"] == math.ceil(3.0 * 7 * 1.5)  # 32
        assert result["needs_reorder"] is False  # 100 > 32

    def test_update_inventory_triggers_needs_reorder(
        self, db_session, sample_product_data, sample_supplier_data
    ):
        """stock=10, demand=3.0 → needs_reorder=True."""
        product = _create_forecastable_product(db_session, sample_product_data, sample_supplier_data,
                                                current_stock=10)
        engine = ForecastingEngine(session=db_session)

        with patch("src.phases.phase_5_forecasting.settings") as mock_settings:
            mock_settings.safety_stock_days = 7
            mock_settings.reorder_point_multiplier = 1.5

            result = engine.update_inventory_forecast(product, daily_demand=3.0)

        # reorder_point = ceil(3.0 * 7 * 1.5) = 32;  10 <= 32 → True
        assert result["needs_reorder"] is True


# ---------------------------------------------------------------------------
# Auto-PO tests
# ---------------------------------------------------------------------------

class TestAutoPO:

    def test_auto_po_created(
        self, db_session, sample_product_data, sample_supplier_data
    ):
        """needs_reorder + no active PO → PO created."""
        product = _create_forecastable_product(db_session, sample_product_data, sample_supplier_data,
                                                current_stock=5)
        engine = ForecastingEngine(session=db_session)

        # Set needs_reorder via update
        with patch("src.phases.phase_5_forecasting.settings") as mock_settings:
            mock_settings.safety_stock_days = 7
            mock_settings.reorder_point_multiplier = 1.5
            mock_settings.forecast_days_ahead = 30
            mock_settings.dry_run = False

            engine.update_inventory_forecast(product, daily_demand=3.0)
            db_session.commit()

            po_id = engine._generate_auto_po(product, daily_demand=3.0)

        assert po_id is not None
        assert po_id.startswith("PO-")

        # Verify PO exists in DB
        po = db_session.query(PurchaseOrder).filter(PurchaseOrder.po_id == po_id).first()
        assert po is not None
        assert po.quantity == max(10, math.ceil(3.0 * 30))  # max(min_order_qty=10, 90) = 90

    def test_auto_po_skipped_dry_run(
        self, db_session, sample_product_data, sample_supplier_data
    ):
        """dry_run=True → no PO created."""
        product = _create_forecastable_product(db_session, sample_product_data, sample_supplier_data,
                                                current_stock=5)
        engine = ForecastingEngine(session=db_session)

        with patch("src.phases.phase_5_forecasting.settings") as mock_settings:
            mock_settings.safety_stock_days = 7
            mock_settings.reorder_point_multiplier = 1.5
            mock_settings.forecast_days_ahead = 30
            mock_settings.dry_run = True

            engine.update_inventory_forecast(product, daily_demand=3.0)
            db_session.commit()

            po_id = engine._generate_auto_po(product, daily_demand=3.0)

        assert po_id is None
        assert db_session.query(PurchaseOrder).count() == 0

    def test_auto_po_skipped_existing_po(
        self, db_session, sample_product_data, sample_supplier_data
    ):
        """Active PO exists → no new PO created."""
        product = _create_forecastable_product(db_session, sample_product_data, sample_supplier_data,
                                                current_stock=5)
        engine = ForecastingEngine(session=db_session)

        # Create an existing active PO
        ps = product.suppliers[0]
        existing_po = PurchaseOrder(
            po_id="PO-EXISTING-1",
            asin=product.asin,
            supplier_id=ps.supplier_id,
            quantity=50,
            unit_cost=Decimal("8.00"),
            total_cost=Decimal("400.00"),
            status="pending",
        )
        db_session.add(existing_po)
        db_session.commit()

        with patch("src.phases.phase_5_forecasting.settings") as mock_settings:
            mock_settings.safety_stock_days = 7
            mock_settings.reorder_point_multiplier = 1.5
            mock_settings.forecast_days_ahead = 30
            mock_settings.dry_run = False

            engine.update_inventory_forecast(product, daily_demand=3.0)
            db_session.commit()

            po_id = engine._generate_auto_po(product, daily_demand=3.0)

        assert po_id is None
        # Only the original PO should exist
        assert db_session.query(PurchaseOrder).count() == 1


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

class TestIntegration:

    def test_forecast_product_full_workflow(
        self, db_session, sample_product_data, sample_supplier_data
    ):
        """End-to-end single product forecast."""
        product = _create_forecastable_product(db_session, sample_product_data, sample_supplier_data,
                                                current_stock=100)
        engine = ForecastingEngine(session=db_session)

        # Patch settings and disable SP-API
        with patch("src.phases.phase_5_forecasting.settings") as mock_settings:
            mock_settings.safety_stock_days = 7
            mock_settings.reorder_point_multiplier = 1.5
            mock_settings.forecast_days_ahead = 30
            mock_settings.dry_run = False

            result = engine.forecast_product(product)

        assert result["action"] == "forecasted"
        assert result["tier"] == 1  # no history → Tier 1
        assert result["daily_demand"] is not None
        assert result["error"] is None

        # Inventory fields should be updated
        inv = product.inventory
        assert inv.forecasted_stock_30d is not None
        assert inv.safety_stock > 0
        assert inv.reorder_point > 0

    def test_sp_api_403_disables_orders(
        self, db_session, sample_product_data, sample_supplier_data
    ):
        """403 from SP-API sets flag; second call skips SP-API."""
        product = _create_forecastable_product(db_session, sample_product_data, sample_supplier_data)

        # Build a mock SP-API that raises 403
        mock_sp = MagicMock(spec=AmazonSPAPI)
        exc = Exception("Forbidden")
        mock_response = MagicMock()
        mock_response.status_code = 403
        exc.response = mock_response
        mock_sp.get_orders.side_effect = exc

        engine = ForecastingEngine(session=db_session, sp_api=mock_sp)

        # First call triggers 403
        history1 = engine._get_historical_sales(product.asin)
        assert engine._sp_api_orders_available is False

        # Second call should not hit SP-API
        mock_sp.get_orders.reset_mock()
        history2 = engine._get_historical_sales(product.asin)
        mock_sp.get_orders.assert_not_called()
