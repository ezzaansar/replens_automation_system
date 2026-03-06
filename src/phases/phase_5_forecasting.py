"""
Phase 5: Inventory Forecasting & Replenishment

Predicts future demand per product using a tiered approach, updates inventory
forecast fields, and auto-generates purchase orders when reorder points are
breached.

Tier selection:
  - < 14 data points  → Tier 1: Keepa estimated_monthly_sales / 30
  - 14–59 data points → Tier 2: Exponential smoothing (α=0.3)
  - 60+ data points   → Tier 3: Prophet (falls back to Tier 2 on failure)
"""

import logging
import math
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from src.config import settings
from src.database import SessionLocal, Product, ProductSupplier, PurchaseOrder
from src.services import (
    get_forecastable_products,
    get_sales_history,
    create_purchase_order,
)
from src.api_wrappers.amazon_sp_api import AmazonSPAPI, get_sp_api
from src.utils.logger import setup_logging
from src.utils.validators import generate_po_id

setup_logging()
logger = logging.getLogger(__name__)

# Minimum daily demand to avoid division-by-zero
_MIN_DAILY_DEMAND = 0.01


class ForecastingEngine:
    """Predicts demand per product and triggers reorder when needed.

    For each eligible product the engine:
    1. Gathers historical sales data (Performance table + optional SP-API).
    2. Selects a forecasting tier based on data availability.
    3. Computes daily demand and updates inventory forecast fields.
    4. Generates a purchase order when the reorder point is breached
       (unless ``dry_run`` mode is active).
    """

    def __init__(self, session=None, sp_api: Optional[AmazonSPAPI] = None):
        self._owns_session = session is None
        self.session = session or SessionLocal()
        self.sp_api = sp_api
        self._sp_api_orders_available = True

    def close(self):
        if self._owns_session:
            self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    # ------------------------------------------------------------------
    # Data gathering
    # ------------------------------------------------------------------

    def _get_historical_sales(self, asin: str) -> List[Tuple[datetime, int]]:
        """Combine Performance-table history with optional SP-API orders."""
        history = get_sales_history(self.session, asin)

        # Attempt to supplement with SP-API order data
        sp_history = self._fetch_sp_api_orders(asin)
        if sp_history:
            # Merge, preferring existing dates from Performance table
            existing_dates = {h[0].date() for h in history}
            for date, units in sp_history:
                if date.date() not in existing_dates:
                    history.append((date, units))
            history.sort(key=lambda x: x[0])

        return history

    def _fetch_sp_api_orders(self, asin: str) -> List[Tuple[datetime, int]]:
        """Fetch order-based sales from SP-API.  Gracefully handles 403."""
        if self.sp_api is None or not self._sp_api_orders_available:
            return []

        try:
            orders = self.sp_api.get_orders(
                created_after=datetime.utcnow() - timedelta(days=90),
                order_statuses=["Shipped"],
            )
            # Aggregate units per day for the requested ASIN
            daily: Dict[datetime, int] = {}
            for order in orders:
                order_date = order.get("PurchaseDate")
                if not order_date:
                    continue
                try:
                    items = self.sp_api.get_order_items(order["AmazonOrderId"])
                except Exception:
                    continue
                for item in items:
                    if item.get("ASIN") == asin:
                        qty = int(item.get("QuantityOrdered", 0))
                        dt = datetime.fromisoformat(order_date.replace("Z", "+00:00")).replace(tzinfo=None)
                        day_key = dt.replace(hour=0, minute=0, second=0, microsecond=0)
                        daily[day_key] = daily.get(day_key, 0) + qty
            return sorted(daily.items())
        except Exception as exc:
            status = getattr(exc, "code", None) or getattr(getattr(exc, "response", None), "status_code", None)
            if status == 403 or "403" in str(exc):
                logger.warning("SP-API returned 403 on orders — disabling order fetching for this run")
                self._sp_api_orders_available = False
            else:
                logger.warning("Failed to fetch SP-API orders for %s: %s", asin, exc)
            return []

    # ------------------------------------------------------------------
    # Tier selection & forecasting
    # ------------------------------------------------------------------

    def _select_tier(self, data_points: int) -> int:
        """Return the forecasting tier (1, 2, or 3) based on data availability."""
        if data_points >= 60:
            return 3
        if data_points >= 14:
            return 2
        return 1

    def _forecast_tier1(self, product: Product) -> float:
        """Tier 1: Keepa estimated_monthly_sales / 30."""
        monthly = product.estimated_monthly_sales or 0
        return monthly / 30.0

    def _forecast_tier2(self, history: List[Tuple[datetime, int]]) -> float:
        """Tier 2: Exponential smoothing (SimpleExpSmoothing, α=0.3)."""
        from statsmodels.tsa.holtwinters import SimpleExpSmoothing

        values = [float(units) for _, units in history]
        model = SimpleExpSmoothing(values).fit(smoothing_level=0.3, optimized=False)
        return float(model.forecast(1)[0])

    def _forecast_tier3(self, history: List[Tuple[datetime, int]]) -> float:
        """Tier 3: Prophet with weekly seasonality.  Falls back to Tier 2."""
        try:
            import pandas as pd
            from prophet import Prophet

            df = pd.DataFrame(history, columns=["ds", "y"])
            df["y"] = df["y"].astype(float)

            m = Prophet(
                weekly_seasonality=True,
                daily_seasonality=False,
                yearly_seasonality=False,
                changepoint_prior_scale=0.01,  # conservative
            )
            m.fit(df)

            future = m.make_future_dataframe(periods=1, freq="D")
            forecast = m.predict(future)
            return max(float(forecast["yhat"].iloc[-1]), 0.0)
        except Exception as exc:
            logger.warning("Prophet forecast failed, falling back to Tier 2: %s", exc)
            return self._forecast_tier2(history)

    def forecast_daily_demand(
        self, product: Product, history: List[Tuple[datetime, int]]
    ) -> Tuple[float, int]:
        """Compute daily demand and the tier used.

        Returns ``(daily_demand, tier)``.  Demand is clamped to
        ``_MIN_DAILY_DEMAND`` to avoid division by zero downstream.
        """
        tier = self._select_tier(len(history))

        try:
            if tier == 3:
                demand = self._forecast_tier3(history)
            elif tier == 2:
                demand = self._forecast_tier2(history)
            else:
                demand = self._forecast_tier1(product)
        except Exception as exc:
            logger.warning(
                "Tier %d forecast failed for %s, falling back to Tier 1: %s",
                tier, product.asin, exc,
            )
            demand = self._forecast_tier1(product)
            tier = 1

        demand = max(demand, _MIN_DAILY_DEMAND)
        return demand, tier

    # ------------------------------------------------------------------
    # Inventory update
    # ------------------------------------------------------------------

    def update_inventory_forecast(
        self, product: Product, daily_demand: float
    ) -> Dict[str, Any]:
        """Update the inventory forecast fields for *product*.

        Returns a dict of the computed values.
        """
        inv = product.inventory
        current_stock = inv.current_stock or 0

        forecasted_30 = current_stock - math.ceil(daily_demand * 30)
        forecasted_60 = current_stock - math.ceil(daily_demand * 60)
        days_of_supply = current_stock / daily_demand
        safety_stock = math.ceil(daily_demand * settings.safety_stock_days)
        reorder_point = math.ceil(
            daily_demand * settings.safety_stock_days * settings.reorder_point_multiplier
        )
        needs_reorder = current_stock <= reorder_point

        inv.forecasted_stock_30d = forecasted_30
        inv.forecasted_stock_60d = forecasted_60
        inv.days_of_supply = round(days_of_supply, 1)
        inv.safety_stock = safety_stock
        inv.reorder_point = reorder_point
        inv.needs_reorder = needs_reorder
        self.session.add(inv)

        return {
            "forecasted_stock_30d": forecasted_30,
            "forecasted_stock_60d": forecasted_60,
            "days_of_supply": round(days_of_supply, 1),
            "safety_stock": safety_stock,
            "reorder_point": reorder_point,
            "needs_reorder": needs_reorder,
        }

    # ------------------------------------------------------------------
    # Auto-PO generation
    # ------------------------------------------------------------------

    def _get_preferred_supplier(self, product: Product) -> Optional[ProductSupplier]:
        for ps in product.suppliers:
            if ps.is_preferred:
                return ps
        return None

    def _has_active_po(self, asin: str) -> bool:
        active_statuses = ("pending", "confirmed", "shipped")
        return (
            self.session.query(PurchaseOrder)
            .filter(
                PurchaseOrder.asin == asin,
                PurchaseOrder.status.in_(active_statuses),
            )
            .first()
            is not None
        )

    def _generate_auto_po(
        self, product: Product, daily_demand: float
    ) -> Optional[str]:
        """Create a PO if reorder is needed and no active PO exists.

        Returns the PO ID or None.
        """
        inv = product.inventory
        if not inv.needs_reorder:
            return None

        if self._has_active_po(product.asin):
            logger.info("%s: active PO already exists — skipping auto-PO", product.asin)
            return None

        ps = self._get_preferred_supplier(product)
        if ps is None:
            return None

        quantity = max(
            ps.supplier.min_order_qty or 1,
            math.ceil(daily_demand * settings.forecast_days_ahead),
        )
        po_id = generate_po_id(product.asin, ps.supplier_id)

        if settings.dry_run:
            logger.info(
                "[DRY RUN] %s: would create PO %s for %d units",
                product.asin, po_id, quantity,
            )
            return None

        po = create_purchase_order(
            session=self.session,
            po_id=po_id,
            asin=product.asin,
            supplier_id=ps.supplier_id,
            quantity=quantity,
            unit_cost=ps.supplier_cost,
        )

        # Set expected delivery
        lead_days = ps.supplier.lead_time_days or 7
        po.expected_delivery = datetime.utcnow() + timedelta(days=lead_days)
        self.session.add(po)
        self.session.commit()

        logger.info(
            "%s: auto-PO %s created — %d units, expected in %d days",
            product.asin, po_id, quantity, lead_days,
        )
        return po_id

    # ------------------------------------------------------------------
    # Per-product workflow
    # ------------------------------------------------------------------

    def forecast_product(self, product: Product) -> Dict[str, Any]:
        """Run the full forecasting workflow for a single product."""
        result: Dict[str, Any] = {
            "asin": product.asin,
            "action": "forecasted",
            "tier": None,
            "daily_demand": None,
            "po_id": None,
            "error": None,
        }

        try:
            history = self._get_historical_sales(product.asin)
            daily_demand, tier = self.forecast_daily_demand(product, history)
            result["tier"] = tier
            result["daily_demand"] = round(daily_demand, 4)

            self.update_inventory_forecast(product, daily_demand)
            self.session.commit()

            po_id = self._generate_auto_po(product, daily_demand)
            result["po_id"] = po_id

        except Exception as exc:
            self.session.rollback()
            result["action"] = "error"
            result["error"] = str(exc)
            logger.exception("Error forecasting %s: %s", product.asin, exc)

        return result

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self, limit: int = 100) -> Dict[str, Any]:
        """Run the forecasting engine across eligible products."""
        logger.info(
            "Phase 5: Inventory Forecasting — starting (dry_run=%s)", settings.dry_run
        )

        products = get_forecastable_products(self.session, limit=limit)
        logger.info("Found %d forecastable products", len(products))

        summary: Dict[str, Any] = {
            "total": len(products),
            "forecasted": 0,
            "skipped": 0,
            "errors": 0,
            "pos_created": 0,
            "tier_counts": {1: 0, 2: 0, 3: 0},
        }

        for product in products:
            result = self.forecast_product(product)
            if result["action"] == "forecasted":
                summary["forecasted"] += 1
                tier = result["tier"]
                if tier in summary["tier_counts"]:
                    summary["tier_counts"][tier] += 1
                if result["po_id"]:
                    summary["pos_created"] += 1
            elif result["action"] == "error":
                summary["errors"] += 1
            else:
                summary["skipped"] += 1

        logger.info(
            "Phase 5 complete — forecasted=%d, errors=%d, POs=%d, tiers=%s",
            summary["forecasted"],
            summary["errors"],
            summary["pos_created"],
            summary["tier_counts"],
        )
        return summary


def main() -> bool:
    """Entry point for Phase 5 (matches the pattern used by other phases)."""
    try:
        with ForecastingEngine() as engine:
            summary = engine.run()
        return summary["errors"] == 0
    except Exception:
        logger.exception("Phase 5 failed")
        return False


if __name__ == "__main__":
    success = main()
    raise SystemExit(0 if success else 1)
