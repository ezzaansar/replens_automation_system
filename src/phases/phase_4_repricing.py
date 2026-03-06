"""
Phase 4: Dynamic Repricing Engine

Monitors competitor prices, adjusts our prices to win the Buy Box, and
enforces a cost-based price floor so we never sell below minimum margin.
"""

import logging
from decimal import Decimal
from typing import Optional, Dict, Any

from src.database import SessionLocal, Product, ProductSupplier
from src.services import get_repriceable_products, record_repricing_action
from src.api_wrappers.amazon_sp_api import AmazonSPAPI, get_sp_api
from src.config import settings
from src.utils.profitability import calculate_min_price
from src.utils.validators import validate_price
from src.utils.logger import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


class RepricingEngine:
    """
    Adjusts product prices to win the Buy Box while respecting a cost-based
    price floor.

    For each eligible product the engine:
    1. Calculates the minimum viable price from the preferred supplier cost.
    2. Fetches competitor / Buy Box pricing from SP-API.
    3. Decides whether to undercut, hold, or skip.
    4. Optionally applies the new price via SP-API (unless dry_run).
    5. Records the observation to the Performance table.
    """

    def __init__(self, session=None, sp_api: Optional[AmazonSPAPI] = None):
        self._owns_session = session is None
        self.session = session or SessionLocal()
        self.sp_api = sp_api
        self._sp_api_pricing_available = True

    def close(self):
        if self._owns_session:
            self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_preferred_supplier(self, product: Product) -> Optional[ProductSupplier]:
        """Return the preferred ProductSupplier for *product*, or None."""
        for ps in product.suppliers:
            if ps.is_preferred:
                return ps
        return None

    def calculate_price_floor(self, product: Product) -> Optional[Decimal]:
        """Return the minimum selling price, or None if no preferred supplier."""
        ps = self._get_preferred_supplier(product)
        if ps is None or ps.total_cost is None:
            return None
        return calculate_min_price(ps.total_cost, product.category or "default")

    def get_competitor_pricing(self, asin: str) -> Optional[Dict[str, Any]]:
        """Fetch Buy Box / competitor pricing from SP-API.

        Returns a dict with keys ``buy_box_price``, ``our_price``,
        ``buy_box_is_ours``, or *None* when pricing data is unavailable.
        """
        if self.sp_api is None or not self._sp_api_pricing_available:
            return None

        try:
            comp_data = self.sp_api.get_product_pricing(asin)
            my_data = self.sp_api.get_my_price(asin)
        except Exception as exc:
            # A 403 means the SP-API pricing role is not enabled — disable
            # pricing calls for the remainder of this run.
            status = getattr(exc, "code", None) or getattr(getattr(exc, "response", None), "status_code", None)
            if status == 403 or "403" in str(exc):
                logger.warning("SP-API returned 403 on pricing — disabling pricing calls for this run")
                self._sp_api_pricing_available = False
            else:
                logger.warning("Failed to fetch pricing for %s: %s", asin, exc)
            return None

        # Parse Buy Box price from competitive pricing response
        # comp_data is the payload list directly (not wrapped in {"payload": ...})
        buy_box_price = None
        try:
            items = comp_data if isinstance(comp_data, list) else [comp_data]
            for item in items:
                for comp_price in item.get("Product", {}).get("CompetitivePricing", {}).get("CompetitivePrices", []):
                    if comp_price.get("CompetitivePriceId") == "1":  # Buy Box
                        amount = comp_price.get("Price", {}).get("LandedPrice", {}).get("Amount")
                        if amount is not None:
                            buy_box_price = Decimal(str(amount))
                            break
        except (KeyError, TypeError, ValueError):
            pass

        # Parse our price
        our_price = None
        buy_box_is_ours = False
        try:
            items = my_data if isinstance(my_data, list) else [my_data]
            for item in items:
                offers = item.get("Product", {}).get("Offers", [])
                if offers:
                    amount = offers[0].get("RegularPrice", {}).get("Amount")
                    if amount is not None:
                        our_price = Decimal(str(amount))
                    buy_box_is_ours = offers[0].get("IsBuyBoxWinner", False)
        except (KeyError, TypeError, ValueError):
            pass

        if buy_box_price is None and our_price is None:
            return None

        return {
            "buy_box_price": buy_box_price,
            "our_price": our_price,
            "buy_box_is_ours": buy_box_is_ours,
        }

    def determine_new_price(
        self,
        product: Product,
        competitor_data: Optional[Dict[str, Any]],
        price_floor: Optional[Decimal],
    ) -> Optional[Decimal]:
        """Decide what our new price should be, or None to keep current.

        Decision rules:
        - We own the Buy Box → no change.
        - Our price is already at or below Buy Box → no change (seller-metrics
          issue; undercutting further won't help and risks a race to the bottom).
        - Our price > Buy Box → target = buy_box_price - adjustment amount.
        - Clamp to price floor (never go below).
        """
        if competitor_data is None:
            return None

        if competitor_data.get("buy_box_is_ours"):
            return None

        buy_box_price = competitor_data.get("buy_box_price")
        our_price = competitor_data.get("our_price")

        if buy_box_price is None:
            return None

        # If we don't know our price, use product.current_price
        if our_price is None:
            our_price = product.current_price
        if our_price is None:
            return None

        # Already at or below Buy Box → don't undercut further
        if our_price <= buy_box_price:
            return None

        # Target: just below Buy Box
        target = buy_box_price - settings.price_adjustment_amount

        # Clamp to price floor
        if price_floor is not None and target < price_floor:
            target = price_floor

        # Validate the final price
        if not validate_price(target):
            return None

        # Don't bother if target equals current price
        if target == our_price:
            return None

        return target

    def reprice_product(self, product: Product) -> Dict[str, Any]:
        """Run the repricing workflow for a single product.

        Returns a result dict with keys: ``asin``, ``action``, ``old_price``,
        ``new_price``, ``buy_box_price``, ``error``.
        """
        result: Dict[str, Any] = {
            "asin": product.asin,
            "action": "skipped",
            "old_price": product.current_price,
            "new_price": None,
            "buy_box_price": None,
            "error": None,
        }

        try:
            price_floor = self.calculate_price_floor(product)
            competitor_data = self.get_competitor_pricing(product.asin)

            buy_box_price = None
            buy_box_is_ours = False
            competitor_price = None
            if competitor_data:
                buy_box_price = competitor_data.get("buy_box_price")
                buy_box_is_ours = competitor_data.get("buy_box_is_ours", False)
                competitor_price = buy_box_price
                result["buy_box_price"] = buy_box_price

            new_price = self.determine_new_price(product, competitor_data, price_floor)

            if new_price is not None:
                if settings.dry_run:
                    result["action"] = "dry_run"
                    result["new_price"] = new_price
                    logger.info(
                        "[DRY RUN] %s: would reprice $%s → $%s (BB=$%s, floor=$%s)",
                        product.asin, product.current_price, new_price,
                        buy_box_price, price_floor,
                    )
                else:
                    # Apply price via SP-API
                    sku = product.sku or product.asin
                    if self.sp_api is not None:
                        self.sp_api.update_price(sku, new_price)

                    product.current_price = new_price
                    self.session.add(product)
                    result["action"] = "repriced"
                    result["new_price"] = new_price
                    logger.info(
                        "%s: repriced $%s → $%s (BB=$%s, floor=$%s)",
                        product.asin, result["old_price"], new_price,
                        buy_box_price, price_floor,
                    )
            else:
                result["action"] = "no_change"

            # Record observation regardless of action
            record_repricing_action(
                session=self.session,
                asin=product.asin,
                our_price=new_price or product.current_price or Decimal("0"),
                competitor_price=competitor_price,
                buy_box_owned=buy_box_is_ours,
            )

        except Exception as exc:
            self.session.rollback()
            result["action"] = "error"
            result["error"] = str(exc)
            logger.exception("Error repricing %s: %s", product.asin, exc)

        return result

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self, limit: int = 100) -> Dict[str, Any]:
        """Run the repricing engine across eligible products.

        Returns summary statistics.
        """
        logger.info("Phase 4: Dynamic Repricing — starting (dry_run=%s)", settings.dry_run)

        products = get_repriceable_products(self.session, limit=limit)
        logger.info("Found %d repriceable products", len(products))

        summary: Dict[str, Any] = {
            "total": len(products),
            "repriced": 0,
            "no_change": 0,
            "dry_run": 0,
            "skipped": 0,
            "errors": 0,
        }

        for product in products:
            result = self.reprice_product(product)
            action = result["action"]
            if action == "repriced":
                summary["repriced"] += 1
            elif action == "no_change":
                summary["no_change"] += 1
            elif action == "dry_run":
                summary["dry_run"] += 1
            elif action == "error":
                summary["errors"] += 1
            else:
                summary["skipped"] += 1

        logger.info(
            "Phase 4 complete — repriced=%d, no_change=%d, dry_run=%d, skipped=%d, errors=%d",
            summary["repriced"], summary["no_change"], summary["dry_run"],
            summary["skipped"], summary["errors"],
        )
        return summary


def main() -> bool:
    """Entry point for Phase 4 (matches the pattern used by other phases)."""
    try:
        with RepricingEngine() as engine:
            summary = engine.run()
        return summary["errors"] == 0
    except Exception:
        logger.exception("Phase 4 failed")
        return False


if __name__ == "__main__":
    success = main()
    raise SystemExit(0 if success else 1)
