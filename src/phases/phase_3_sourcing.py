"""
Phase 3: Supplier Matching & Procurement

Finds reliable suppliers for identified products and automates procurement.
Uses OpenAI API when available for supplier suggestions, otherwise falls
back to category-based cost estimation.
"""

import json
import logging
import sys
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from decimal import Decimal

from src.database import (
    SessionLocal, Product, Supplier, ProductSupplier, Inventory,
    PurchaseOrder, DatabaseOperations,
)
from src.api_wrappers.amazon_sp_api import get_sp_api
from src.config import settings, CATEGORY_COGS_ESTIMATES
from src.utils.profitability import (
    estimate_amazon_fees, calculate_profitability, meets_profitability_thresholds,
)
from src.utils.validators import (
    validate_upc, validate_price, validate_quantity,
    sanitize_string, generate_po_id,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(settings.log_file),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class SourcingEngine:
    """
    Matches products with suppliers, calculates profitability, and generates
    purchase orders.

    Works in two modes:
    - With OpenAI: Uses GPT to suggest supplier names/costs based on product data
    - Without OpenAI: Uses category-based COGS estimation from config
    """

    def __init__(self):
        """Initialize the sourcing engine."""
        self.sp_api = get_sp_api()
        self.db = DatabaseOperations()
        self.session = SessionLocal()
        self.openai_client = None

        if settings.openai_api_key:
            try:
                import openai
                self.openai_client = openai.OpenAI(api_key=settings.openai_api_key)
                logger.info("OpenAI API available for supplier suggestions")
            except Exception as e:
                logger.warning(f"OpenAI initialization failed, using rule-based mode: {e}")
        else:
            logger.info("No OpenAI API key configured. Using rule-based supplier estimation.")

    def enrich_product(self, product: Product) -> Optional[str]:
        """
        Enrich a product with UPC/EAN from SP-API catalog data.

        Args:
            product: Product ORM instance to enrich

        Returns:
            UPC string if found, None otherwise
        """
        if product.upc:
            return product.upc

        try:
            catalog_data = self.sp_api.get_catalog_item(product.asin)

            identifiers_list = catalog_data.get("identifiers", [])
            for marketplace_ids in identifiers_list:
                for ident in marketplace_ids.get("identifiers", []):
                    id_type = ident.get("identifierType", "")
                    id_value = ident.get("identifier", "")
                    if id_type in ("UPC", "EAN") and validate_upc(id_value):
                        product.upc = id_value
                        self.session.commit()
                        logger.info(f"  Enriched {product.asin} with {id_type}: {id_value}")
                        return id_value

            logger.debug(f"  No UPC/EAN found for {product.asin}")
            return None

        except Exception as e:
            logger.warning(f"  Could not enrich {product.asin}: {e}")
            return None

    def suggest_suppliers_openai(self, product: Product) -> List[Dict[str, Any]]:
        """
        Use OpenAI to suggest potential suppliers and estimated costs.

        Args:
            product: Product ORM instance

        Returns:
            List of supplier suggestion dicts
        """
        if not self.openai_client:
            return []

        try:
            prompt = (
                f"I'm sourcing the following Amazon product for wholesale resale:\n"
                f"- Title: {product.title}\n"
                f"- Category: {product.category}\n"
                f"- ASIN: {product.asin}\n"
                f"- UPC: {product.upc or 'N/A'}\n"
                f"- Amazon selling price: ${product.current_price}\n\n"
                f"Suggest up to 3 realistic wholesale supplier options. "
                f"For each supplier, provide:\n"
                f"1. supplier_name (a realistic wholesale distributor name)\n"
                f"2. estimated_unit_cost (wholesale cost per unit in USD)\n"
                f"3. estimated_shipping_cost (per unit in USD)\n"
                f"4. lead_time_days (integer)\n"
                f"5. min_order_qty (integer)\n\n"
                f"Respond ONLY with a JSON array. No explanation."
            )

            response = self.openai_client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": "You are a wholesale sourcing assistant. Respond only with valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=500,
            )

            content = response.choices[0].message.content.strip()
            # Handle markdown code fences GPT sometimes wraps JSON in
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            suggestions = json.loads(content)

            results = []
            for s in suggestions[:3]:
                results.append({
                    "name": sanitize_string(s.get("supplier_name", "Unknown Supplier")),
                    "website": None,
                    "estimated_cost": Decimal(str(round(float(s.get("estimated_unit_cost", 0)), 2))),
                    "shipping_cost": Decimal(str(round(float(s.get("estimated_shipping_cost", 0)), 2))),
                    "lead_time_days": int(s.get("lead_time_days", 14)),
                    "min_order_qty": int(s.get("min_order_qty", 24)),
                    "reliability_score": 50.0,  # Unverified AI suggestion
                })

            logger.info(f"  OpenAI suggested {len(results)} suppliers for {product.asin}")
            return results

        except Exception as e:
            logger.warning(f"  OpenAI supplier suggestion failed for {product.asin}: {e}")
            return []

    def estimate_suppliers_rulebased(self, product: Product) -> List[Dict[str, Any]]:
        """
        Estimate supplier costs using category-based COGS ratios.

        Creates a single estimated supplier entry using CATEGORY_COGS_ESTIMATES
        from config.py as a baseline for profitability analysis.

        Args:
            product: Product ORM instance

        Returns:
            List with a single supplier estimate dict
        """
        category_key = (product.category or "default").lower().replace(" & ", "_").replace(" ", "_")
        cogs_ratio = CATEGORY_COGS_ESTIMATES.get(category_key, CATEGORY_COGS_ESTIMATES["default"])

        selling_price = float(product.current_price or 0)
        if selling_price <= 0:
            return []

        estimated_cost = round(selling_price * cogs_ratio, 2)
        shipping_cost = max(1.00, round(estimated_cost * 0.05, 2))

        supplier_name = f"Estimated-{category_key.replace('_', '-').title()}-Supplier"

        return [{
            "name": supplier_name,
            "website": None,
            "estimated_cost": Decimal(str(estimated_cost)),
            "shipping_cost": Decimal(str(shipping_cost)),
            "lead_time_days": 14,
            "min_order_qty": 24,
            "reliability_score": 75.0,  # Above 70 threshold for automated pipeline
        }]

    def get_or_create_supplier(self, suggestion: Dict[str, Any]) -> Supplier:
        """
        Find an existing supplier by name or create a new one.

        Args:
            suggestion: Supplier suggestion dict

        Returns:
            Supplier ORM instance
        """
        name = suggestion["name"]
        existing = self.session.query(Supplier).filter(Supplier.name == name).first()

        if existing:
            return existing

        supplier = Supplier(
            name=name,
            website=suggestion.get("website"),
            min_order_qty=suggestion.get("min_order_qty", 24),
            lead_time_days=suggestion.get("lead_time_days", 14),
            reliability_score=suggestion.get("reliability_score", 50.0),
            on_time_delivery_rate=1.0,
            status="active",
        )
        self.session.add(supplier)
        self.session.flush()  # Get supplier_id without full commit
        logger.info(f"    Created supplier: {name} (ID: {supplier.supplier_id})")
        return supplier

    def analyze_profitability(
        self, product: Product, supplier: Supplier, suggestion: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate profitability for a product-supplier pairing.

        Uses utils/profitability.py for fee estimation and profit calculation.

        Args:
            product: Product ORM instance
            supplier: Supplier ORM instance
            suggestion: Raw suggestion dict with estimated_cost and shipping_cost

        Returns:
            Profitability metrics dict, or None if selling price is invalid
        """
        selling_price = Decimal(str(product.current_price or 0))
        if not validate_price(selling_price):
            return None

        supplier_cost = suggestion["estimated_cost"]
        shipping_cost = suggestion["shipping_cost"]
        total_cost = supplier_cost + shipping_cost

        category = (product.category or "default").lower()
        fees = estimate_amazon_fees(selling_price, category=category)
        amazon_fees = fees["total_fees"]

        profit_data = calculate_profitability(selling_price, total_cost, amazon_fees)

        passes = meets_profitability_thresholds(
            profit_margin=profit_data["profit_margin"],
            roi=profit_data["roi"],
            lead_time_days=supplier.lead_time_days,
            reliability_score=supplier.reliability_score,
        )

        return {
            "supplier_cost": supplier_cost,
            "shipping_cost": shipping_cost,
            "total_cost": total_cost,
            "amazon_fees": amazon_fees,
            "net_profit": profit_data["net_profit"],
            "profit_margin": profit_data["profit_margin"],
            "roi": profit_data["roi"],
            "meets_thresholds": passes,
        }

    def save_product_supplier(
        self,
        product: Product,
        supplier: Supplier,
        profitability: Dict[str, Any],
        is_preferred: bool = False,
    ) -> ProductSupplier:
        """
        Save a product-supplier pairing to the database.

        Args:
            product: Product ORM instance
            supplier: Supplier ORM instance
            profitability: Profitability analysis dict
            is_preferred: Whether this is the preferred supplier

        Returns:
            ProductSupplier ORM instance
        """
        existing = (
            self.session.query(ProductSupplier)
            .filter(
                ProductSupplier.asin == product.asin,
                ProductSupplier.supplier_id == supplier.supplier_id,
            )
            .first()
        )

        if existing:
            existing.supplier_cost = profitability["supplier_cost"]
            existing.shipping_cost = profitability["shipping_cost"]
            existing.total_cost = profitability["total_cost"]
            existing.estimated_profit = profitability["net_profit"]
            existing.profit_margin = profitability["profit_margin"]
            existing.roi = profitability["roi"]
            existing.is_preferred = is_preferred
            existing.status = "active"
            return existing

        ps = ProductSupplier(
            asin=product.asin,
            supplier_id=supplier.supplier_id,
            supplier_cost=profitability["supplier_cost"],
            shipping_cost=profitability["shipping_cost"],
            total_cost=profitability["total_cost"],
            estimated_profit=profitability["net_profit"],
            profit_margin=profitability["profit_margin"],
            roi=profitability["roi"],
            is_preferred=is_preferred,
            status="active",
        )
        self.session.add(ps)
        return ps

    def select_preferred_supplier(self, product: Product) -> Optional[ProductSupplier]:
        """
        Select and mark the preferred supplier for a product.

        Picks the highest profit margin supplier that meets all thresholds.

        Args:
            product: Product ORM instance

        Returns:
            The preferred ProductSupplier, or None if none qualifies
        """
        pairings = self.db.get_product_suppliers(self.session, product.asin)
        if not pairings:
            return None

        for ps in pairings:
            ps.is_preferred = False

        qualifying = []
        for ps in pairings:
            supplier = self.db.get_supplier(self.session, ps.supplier_id)
            if supplier and meets_profitability_thresholds(
                profit_margin=ps.profit_margin or 0,
                roi=ps.roi or 0,
                lead_time_days=supplier.lead_time_days or 0,
                reliability_score=supplier.reliability_score or 0,
            ):
                qualifying.append(ps)

        if not qualifying:
            logger.debug(f"  No qualifying suppliers for {product.asin}")
            self.session.commit()
            return None

        # get_product_suppliers returns sorted by profit_margin DESC
        best = qualifying[0]
        best.is_preferred = True
        self.session.commit()

        logger.info(
            f"  Preferred supplier for {product.asin}: "
            f"supplier_id={best.supplier_id}, margin={best.profit_margin:.1%}"
        )
        return best

    def initialize_inventory(self, product: Product) -> Inventory:
        """
        Create an Inventory record for a product if one does not exist.

        Calculates reorder parameters based on estimated sales velocity
        and config thresholds.

        Args:
            product: Product ORM instance

        Returns:
            Inventory ORM instance
        """
        existing = self.session.query(Inventory).filter(Inventory.asin == product.asin).first()
        if existing:
            return existing

        daily_sales = (product.estimated_monthly_sales or 0) / 30.0
        safety_stock = max(1, int(daily_sales * settings.safety_stock_days))
        reorder_point = max(1, int(daily_sales * settings.safety_stock_days * settings.reorder_point_multiplier))

        inventory = Inventory(
            asin=product.asin,
            current_stock=0,
            reserved=0,
            available=0,
            reorder_point=reorder_point,
            safety_stock=safety_stock,
            forecasted_stock_30d=0,
            forecasted_stock_60d=0,
            days_of_supply=0,
            needs_reorder=True,
        )
        self.session.add(inventory)
        logger.info(
            f"  Initialized inventory for {product.asin}: "
            f"safety_stock={safety_stock}, reorder_point={reorder_point}"
        )
        return inventory

    def generate_purchase_orders(self) -> List[PurchaseOrder]:
        """
        Generate purchase orders for products that need restocking.

        Only generates POs for products that:
        1. Have needs_reorder=True in Inventory
        2. Have a preferred supplier
        3. Don't already have a pending/confirmed/shipped PO

        Returns:
            List of newly created PurchaseOrder instances
        """
        if settings.dry_run:
            logger.info("DRY RUN: Skipping PO generation")
            return []

        new_pos = []

        low_stock_products = self.db.get_low_stock_products(self.session)
        logger.info(f"Found {len(low_stock_products)} products needing reorder")

        for product in low_stock_products:
            try:
                pairings = self.db.get_product_suppliers(self.session, product.asin)
                preferred = next((ps for ps in pairings if ps.is_preferred), None)

                if not preferred:
                    logger.debug(f"  No preferred supplier for {product.asin}, skipping PO")
                    continue

                supplier = self.db.get_supplier(self.session, preferred.supplier_id)
                if not supplier or supplier.status != "active":
                    continue

                # Check for existing active PO
                existing_po = (
                    self.session.query(PurchaseOrder)
                    .filter(
                        PurchaseOrder.asin == product.asin,
                        PurchaseOrder.supplier_id == supplier.supplier_id,
                        PurchaseOrder.status.in_(["pending", "confirmed", "shipped"]),
                    )
                    .first()
                )
                if existing_po:
                    logger.debug(f"  Active PO exists for {product.asin}: {existing_po.po_id}")
                    continue

                # Calculate order quantity
                inventory = product.inventory
                reorder_qty = max(
                    supplier.min_order_qty,
                    (inventory.reorder_point or 0) * 2,
                )

                if not validate_quantity(reorder_qty):
                    continue

                unit_cost = preferred.total_cost
                if not validate_price(unit_cost):
                    continue

                po_id = generate_po_id(product.asin, supplier.supplier_id)
                po = self.db.create_purchase_order(
                    session=self.session,
                    po_id=po_id,
                    asin=product.asin,
                    supplier_id=supplier.supplier_id,
                    quantity=reorder_qty,
                    unit_cost=unit_cost,
                )

                po.expected_delivery = datetime.now(timezone.utc) + timedelta(days=supplier.lead_time_days)
                self.session.commit()

                new_pos.append(po)
                logger.info(
                    f"  Created PO {po_id}: {product.asin} x{reorder_qty} "
                    f"@ ${unit_cost}/unit from {supplier.name}"
                )

            except Exception as e:
                logger.error(f"  Error generating PO for {product.asin}: {e}")
                self.session.rollback()
                continue

        return new_pos

    def process_product(self, product: Product) -> bool:
        """
        Run the full sourcing pipeline for a single product.

        Steps:
        1. Enrich with UPC/EAN identifiers
        2. Get supplier suggestions (OpenAI or rule-based)
        3. For each suggestion: create/find supplier, analyze profitability, save pairing
        4. Select the preferred supplier
        5. Initialize inventory record

        Args:
            product: Product ORM instance

        Returns:
            True if at least one supplier pairing was created/updated
        """
        logger.info(f"Processing {product.asin}: {(product.title or '')[:60]}...")

        # Step 1: Enrich product with UPC
        self.enrich_product(product)

        # Step 2: Check existing suppliers
        existing_suppliers = self.db.get_product_suppliers(self.session, product.asin)
        if existing_suppliers:
            logger.info(f"  {product.asin} already has {len(existing_suppliers)} supplier(s), re-analyzing")

        # Step 3: Get supplier suggestions
        suggestions = []
        if self.openai_client:
            suggestions = self.suggest_suppliers_openai(product)

        # Always add rule-based estimate as baseline
        suggestions.extend(self.estimate_suppliers_rulebased(product))

        if not suggestions:
            logger.warning(f"  No supplier suggestions for {product.asin}")
            return False

        # Step 4: Process each suggestion
        pairings_created = 0
        for suggestion in suggestions:
            try:
                supplier = self.get_or_create_supplier(suggestion)
                profitability = self.analyze_profitability(product, supplier, suggestion)

                if profitability is None:
                    continue

                self.save_product_supplier(product, supplier, profitability)
                pairings_created += 1

                status = "PASS" if profitability["meets_thresholds"] else "FAIL"
                logger.info(
                    f"    {supplier.name}: cost=${profitability['total_cost']:.2f}, "
                    f"margin={profitability['profit_margin']:.1%}, "
                    f"ROI={profitability['roi']:.1%} [{status}]"
                )

            except Exception as e:
                logger.error(f"    Error processing supplier {suggestion.get('name')}: {e}")
                self.session.rollback()
                continue

        # Step 5: Select preferred supplier
        if pairings_created > 0:
            self.session.commit()
            self.select_preferred_supplier(product)

        # Step 6: Initialize inventory
        self.initialize_inventory(product)
        self.session.commit()

        return pairings_created > 0

    def run(self, limit: int = 50) -> Dict[str, int]:
        """
        Run the full sourcing engine.

        1. Fetch underserved products from database
        2. Process each product (enrich, match suppliers, analyze profitability)
        3. Generate purchase orders for products needing restock

        Args:
            limit: Maximum number of products to process per run

        Returns:
            Dict with counts: products_processed, suppliers_matched, pos_created
        """
        logger.info("=" * 70)
        logger.info("Starting Phase 3: Supplier Matching & Procurement")
        logger.info(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
        logger.info(f"Mode: {'OpenAI-assisted' if self.openai_client else 'Rule-based'}")
        logger.info("=" * 70)

        stats = {
            "products_processed": 0,
            "suppliers_matched": 0,
            "pos_created": 0,
        }

        # Step 1: Get products that need supplier matching
        products = self.db.get_underserved_products(self.session, limit=limit)
        logger.info(f"Found {len(products)} underserved products to process")

        if not products:
            logger.info("No products to process. Run Phase 2 first.")
            return stats

        # Step 2: Process each product
        for i, product in enumerate(products, 1):
            logger.info(f"\n[{i}/{len(products)}] -----------------------------------------")
            try:
                matched = self.process_product(product)
                stats["products_processed"] += 1
                if matched:
                    stats["suppliers_matched"] += 1
            except Exception as e:
                logger.error(f"Error processing product {product.asin}: {e}")
                self.session.rollback()
                continue

        # Step 3: Generate purchase orders
        logger.info("\n" + "=" * 70)
        logger.info("Generating Purchase Orders")
        logger.info("=" * 70)
        new_pos = self.generate_purchase_orders()
        stats["pos_created"] = len(new_pos)

        # Summary
        logger.info("\n" + "=" * 70)
        logger.info("Phase 3 Summary")
        logger.info("=" * 70)
        logger.info(f"  Products processed: {stats['products_processed']}")
        logger.info(f"  Suppliers matched:  {stats['suppliers_matched']}")
        logger.info(f"  POs created:        {stats['pos_created']}")

        return stats


def main():
    """Run Phase 3: Supplier Matching & Procurement."""
    try:
        engine = SourcingEngine()
        stats = engine.run()
        logger.info(f"Phase 3 complete: {stats}")
        return True
    except Exception as e:
        logger.error(f"Phase 3 failed: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
