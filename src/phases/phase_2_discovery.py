"""
Phase 2: Product Discovery Engine

Identifies high-potential replenishable products using:
1. Keepa API for product discovery and historical data
2. Machine learning scoring model
3. Profitability analysis with fee estimation fallback
"""

import logging
import math
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional
from decimal import Decimal
import numpy as np

from src.database import SessionLocal, Product, DatabaseOperations
from src.api_wrappers.keepa_api import get_keepa_api
from src.api_wrappers.amazon_sp_api import get_sp_api
from src.config import (
    settings, SALES_RANK_THRESHOLDS, SELLER_COUNT_THRESHOLDS,
    CATEGORY_COGS_ESTIMATES,
)
from src.utils.profitability import estimate_amazon_fees
from src.models.discovery_model import DiscoveryModel

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(settings.log_file),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class ProductDiscoveryEngine:
    """
    Identifies high-potential replenishable products.

    Uses machine learning to score products based on:
    - Sales velocity
    - Competition level
    - Price stability
    - Profitability potential
    """

    def __init__(self):
        """Initialize the discovery engine."""
        self.keepa_api = get_keepa_api()
        self.sp_api = get_sp_api()
        self.db = DatabaseOperations()
        self.model = DiscoveryModel()
        self.session = SessionLocal()
        self._sp_api_fees_available = True  # Turns False after first 403

    def extract_features(self, product_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract features from Keepa product data for ML model.

        Uses the pre-parsed ``product['data']`` dict provided by the keepa
        library.  Keys like ``data['NEW']``, ``data['SALES']``, and
        ``data['COUNT_NEW']`` are numpy arrays with timestamps already
        stripped and prices already converted from cents to dollars.

        Args:
            product_data: Raw product data from Keepa API

        Returns:
            Dictionary of extracted features, or None if data is insufficient
        """
        try:
            asin = product_data.get("asin", "")
            title = product_data.get("title", "")
            category = product_data.get("categoryTree", [{}])
            category_name = category[0].get("name", "Unknown") if category else "Unknown"

            # Use the pre-parsed 'data' dict from the keepa library.
            # parse_csv() separates timestamps from values and converts
            # prices from cents to dollars automatically.
            data = product_data.get("data", {})
            if not data:
                return None

            # Price history (NEW = marketplace new price, already in dollars)
            price_values = data.get("NEW")
            if price_values is None or len(price_values) == 0:
                return None

            # Sales rank history
            rank_values = data.get("SALES")
            if rank_values is None or len(rank_values) == 0:
                return None

            # Seller count history (new offer count)
            seller_values = data.get("COUNT_NEW")

            # Filter valid values (drop NaN and non-positive)
            valid_prices = price_values[~np.isnan(price_values) & (price_values > 0)]
            valid_ranks = rank_values[(rank_values > 0)]
            if seller_values is not None and len(seller_values) > 0:
                valid_sellers = seller_values[seller_values > 0]
            else:
                valid_sellers = np.array([])

            if len(valid_prices) == 0 or len(valid_ranks) == 0:
                return None

            # Calculate basic statistics (prices already in dollars)
            avg_price = float(np.mean(valid_prices))
            price_std = float(np.std(valid_prices))
            avg_sales_rank = float(np.mean(valid_ranks))
            avg_seller_count = float(np.mean(valid_sellers)) if len(valid_sellers) > 0 else 5.0

            # Sales velocity estimation using log-based model
            # Based on empirical Amazon seller data:
            # Rank 1 ~ 5000 units/mo, Rank 1000 ~ 50, Rank 10000 ~ 9, Rank 100000 ~ 1
            stats = product_data.get("stats", {})
            if stats and isinstance(stats, dict) and stats.get("salesRankDrops30"):
                estimated_monthly_sales = max(1, int(stats["salesRankDrops30"]))
            elif avg_sales_rank > 0:
                estimated_monthly_sales = max(1, int(4800 * (avg_sales_rank ** -0.75)))
            else:
                estimated_monthly_sales = 0

            # Price stability (inverse of coefficient of variation)
            if avg_price > 0:
                price_stability = 1 - min(1, price_std / avg_price)
            else:
                price_stability = 0

            features = {
                "asin": asin,
                "title": title,
                "category": category_name,
                "avg_price": avg_price,
                "price_std": price_std,
                "price_stability": float(price_stability),
                "avg_sales_rank": avg_sales_rank,
                "estimated_monthly_sales": estimated_monthly_sales,
                "avg_seller_count": avg_seller_count,
                "num_sellers_low": 1 if avg_seller_count < SELLER_COUNT_THRESHOLDS["low"] else 0,
                "sales_rank_good": 1 if avg_sales_rank < SALES_RANK_THRESHOLDS["good"] else 0,
                "price_stable": 1 if price_stability > 0.7 else 0,
            }

            return features

        except Exception as e:
            logger.error(f"✗ Error extracting features: {e}")
            return None

    def calculate_profitability(self, asin: str, price: Decimal, category: str = "default") -> Dict[str, Any]:
        """
        Estimate profitability for a product.
        Tries SP-API fees first, falls back to local estimation.

        Args:
            asin: Product ASIN
            price: Current selling price
            category: Product category for fee/COGS lookup

        Returns:
            Profitability metrics
        """
        try:
            # Try SP-API for fee estimates (skip if previously failed with 403)
            if self._sp_api_fees_available:
                try:
                    fees = self.sp_api.estimate_fees(asin, price)
                    total_fees = fees["referral_fee"] + fees["fba_fee"] + fees.get("variable_closing_fee", Decimal(0))
                    if total_fees == 0:
                        raise ValueError("SP-API returned zero fees")
                    total_fees = Decimal(str(float(total_fees)))
                except Exception as e:
                    if "403" in str(e):
                        logger.info("SP-API fees unavailable (403). Switching to local fee estimation for all products.")
                        self._sp_api_fees_available = False
                    local_fees = estimate_amazon_fees(price, category=category)
                    total_fees = local_fees["total_fees"]
            else:
                local_fees = estimate_amazon_fees(price, category=category)
                total_fees = local_fees["total_fees"]

            # Category-aware COGS estimate
            cogs_ratio = Decimal(str(
                CATEGORY_COGS_ESTIMATES.get(category.lower(), settings.discovery_cogs_ratio)
            ))
            estimated_cogs = price * cogs_ratio

            # Calculate profit
            net_profit = price - estimated_cogs - total_fees

            profit_margin = float(net_profit / price) if price > 0 else 0.0
            roi = float(net_profit / estimated_cogs) if estimated_cogs > 0 else 0.0

            return {
                "estimated_cogs": float(estimated_cogs),
                "total_fees": float(total_fees),
                "net_profit": float(net_profit),
                "profit_margin": profit_margin,
                "roi": roi,
            }

        except Exception as e:
            logger.error(f"✗ Error calculating profitability for {asin}: {e}")
            return {
                "estimated_cogs": 0,
                "total_fees": 0,
                "net_profit": 0,
                "profit_margin": 0,
                "roi": 0,
            }

    def score_product(self, features: Dict[str, Any], profitability: Dict[str, Any]) -> float:
        """
        Score a product using the ML model with additive penalties.

        Args:
            features: Extracted features
            profitability: Profitability metrics

        Returns:
            Opportunity score (0-100)
        """
        try:
            feature_vector = [
                features.get("price_stability", 0),
                features.get("num_sellers_low", 0),
                features.get("sales_rank_good", 0),
                features.get("estimated_monthly_sales", 0) / 100,
                profitability.get("profit_margin", 0),
                profitability.get("roi", 0) / 10,
            ]

            # Base score from model (0-1)
            base_score = self.model.predict(feature_vector)

            # Additive penalties instead of multiplicative
            penalty = 0.0

            if profitability["profit_margin"] < settings.min_profit_margin:
                shortfall = (settings.min_profit_margin - profitability["profit_margin"]) / settings.min_profit_margin
                penalty += 0.15 * min(shortfall, 1.0)

            if profitability["roi"] < settings.min_roi:
                shortfall = (settings.min_roi - profitability["roi"]) / settings.min_roi
                penalty += 0.10 * min(shortfall, 1.0)

            if features["estimated_monthly_sales"] < settings.min_sales_velocity:
                shortfall = (settings.min_sales_velocity - features["estimated_monthly_sales"]) / settings.min_sales_velocity
                penalty += 0.10 * min(shortfall, 1.0)

            final_score = max(0, (base_score - penalty)) * 100
            return max(0, min(100, final_score))

        except Exception as e:
            logger.error(f"✗ Error scoring product: {e}")
            return 0

    def discover_products(self, asins: List[str]) -> List[Dict[str, Any]]:
        """
        Discover and score products, batching Keepa queries.

        Args:
            asins: List of ASINs to analyze

        Returns:
            List of scored products sorted by opportunity score
        """
        opportunities = []
        batch_size = 100

        for i in range(0, len(asins), batch_size):
            batch = asins[i:i + batch_size]
            logger.info(f"Querying Keepa for batch {i // batch_size + 1} ({len(batch)} ASINs)...")

            product_data_list = self.keepa_api.get_product_data(batch)
            if not product_data_list:
                continue

            for product in product_data_list:
                try:
                    features = self.extract_features(product)
                    if not features:
                        continue

                    current_price = Decimal(str(features.get("avg_price", 0)))
                    if current_price <= 0:
                        continue

                    profitability = self.calculate_profitability(
                        features["asin"], current_price, category=features.get("category", "default")
                    )

                    score = self.score_product(features, profitability)

                    opportunity = {
                        "asin": features["asin"],
                        "title": features["title"],
                        "category": features["category"],
                        "current_price": current_price,
                        "sales_rank": int(features["avg_sales_rank"]),
                        "estimated_monthly_sales": features["estimated_monthly_sales"],
                        "profit_potential": Decimal(str(profitability["net_profit"])),
                        "num_sellers": int(features["avg_seller_count"]),
                        "price_stability": features["price_stability"],
                        "opportunity_score": score,
                        "is_underserved": score >= 50,
                    }

                    opportunities.append(opportunity)

                except Exception as e:
                    logger.error(f"✗ Error analyzing product: {e}")
                    continue

        opportunities.sort(key=lambda x: x["opportunity_score"], reverse=True)
        return opportunities

    def save_opportunities(self, opportunities: List[Dict[str, Any]]) -> int:
        """
        Save discovered opportunities to the database.

        Args:
            opportunities: List of opportunities

        Returns:
            Number of opportunities saved
        """
        saved = 0

        for opp in opportunities:
            try:
                existing = self.db.get_product(self.session, opp["asin"])

                if existing:
                    existing.current_price = opp["current_price"]
                    existing.sales_rank = opp["sales_rank"]
                    existing.estimated_monthly_sales = opp["estimated_monthly_sales"]
                    existing.profit_potential = opp["profit_potential"]
                    existing.num_sellers = opp["num_sellers"]
                    existing.price_stability = opp["price_stability"]
                    existing.opportunity_score = opp["opportunity_score"]
                    existing.is_underserved = opp["is_underserved"]
                    existing.last_updated = datetime.utcnow()
                else:
                    new_product = Product(
                        asin=opp["asin"],
                        title=opp["title"],
                        category=opp["category"],
                        current_price=opp["current_price"],
                        sales_rank=opp["sales_rank"],
                        estimated_monthly_sales=opp["estimated_monthly_sales"],
                        profit_potential=opp["profit_potential"],
                        num_sellers=opp["num_sellers"],
                        price_stability=opp["price_stability"],
                        opportunity_score=opp["opportunity_score"],
                        is_underserved=opp["is_underserved"],
                        status="active",
                    )
                    self.session.add(new_product)

                self.session.commit()
                saved += 1

            except Exception as e:
                logger.error(f"✗ Error saving opportunity {opp.get('asin')}: {e}")
                self.session.rollback()

        return saved

    def _discover_asins_from_categories(self) -> List[str]:
        """
        Discover ASINs from configured categories using Keepa.
        Uses product_finder for filtered discovery and best_sellers as fallback.

        Returns:
            Deduplicated list of ASIN strings.
        """
        all_asins = []

        category_ids = [
            c.strip() for c in settings.discovery_categories.split(",")
            if c.strip()
        ]

        if not category_ids:
            logger.warning(
                "No discovery categories configured. "
                "Set DISCOVERY_CATEGORIES in .env (comma-separated category node IDs)."
            )
            return []

        per_category_limit = max(20, settings.discovery_max_products // len(category_ids))

        for cat_id in category_ids:
            logger.info(f"Discovering products in category {cat_id}...")

            # Primary: Use product_finder with filters
            asins = self.keepa_api.discover_products_by_category(
                category_id=cat_id,
                price_min=settings.discovery_price_min,
                price_max=settings.discovery_price_max,
                sales_rank_max=settings.discovery_sales_rank_max,
                seller_count_max=settings.discovery_seller_count_max,
                n_products=per_category_limit,
            )

            # Fallback: If product_finder returns nothing, try best_sellers
            if not asins:
                logger.info(f"product_finder empty for {cat_id}, trying best_sellers_query...")
                asins = self.keepa_api.get_best_sellers(cat_id, rank_avg_range=30)
                asins = asins[:per_category_limit]

            all_asins.extend(asins)
            logger.info(f"  Category {cat_id}: {len(asins)} ASINs")

        # Deduplicate while preserving order
        seen = set()
        unique_asins = []
        for asin in all_asins:
            if asin not in seen:
                seen.add(asin)
                unique_asins.append(asin)

        unique_asins = unique_asins[:settings.discovery_max_products]
        logger.info(f"Total unique ASINs to analyze: {len(unique_asins)}")

        return unique_asins

    def run(self, asins: List[str] = None) -> int:
        """
        Run the product discovery engine.

        If asins are provided, analyze those directly.
        Otherwise, discover products from configured categories using Keepa.

        Args:
            asins: Optional list of ASINs to analyze directly

        Returns:
            Number of opportunities found
        """
        logger.info("Starting Product Discovery Engine")
        logger.info(f"Timestamp: {datetime.utcnow().isoformat()}")

        if not asins:
            asins = self._discover_asins_from_categories()

        if not asins:
            logger.warning("No ASINs to analyze. Check DISCOVERY_CATEGORIES in .env.")
            return 0

        logger.info(f"Analyzing {len(asins)} discovered ASINs")

        opportunities = self.discover_products(asins)
        logger.info(f"Found {len(opportunities)} opportunities")

        saved = self.save_opportunities(opportunities)
        logger.info(f"✓ Saved {saved} opportunities to database")

        if opportunities:
            logger.info("\nTop 10 Opportunities:")
            for i, opp in enumerate(opportunities[:10], 1):
                logger.info(
                    f"  {i}. {opp['asin']} | Score: {opp['opportunity_score']:.1f} | "
                    f"${opp['current_price']:.2f} | Rank: {opp['sales_rank']} | "
                    f"Est. Sales: {opp['estimated_monthly_sales']}/mo"
                )

        return len(opportunities)


def main():
    """Run Phase 2: Product Discovery."""
    try:
        engine = ProductDiscoveryEngine()
        count = engine.run()
        logger.info(f"✓ Phase 2 complete: {count} opportunities found")
        return True
    except Exception as e:
        logger.error(f"✗ Phase 2 failed: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
