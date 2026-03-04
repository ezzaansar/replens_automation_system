"""
Keepa API Wrapper

Provides a clean, high-level interface to the Keepa API for:
- Fetching historical product data (price, sales rank)
- Discovering products by category using product_finder and best_sellers
- Tracking competitor information
"""

import logging
from typing import Dict, List, Any, Optional

import keepa
from src.config import settings

logger = logging.getLogger(__name__)

# Map numeric domain codes to string codes expected by the keepa library
KEEPA_DOMAIN_MAP = {
    1: "US", 2: "GB", 3: "DE", 4: "FR", 5: "JP",
    6: "CA", 7: "CN", 8: "IT", 9: "ES", 10: "IN",
    11: "MX", 12: "BR",
}


class KeepaAPI:
    """
    Wrapper for the Keepa API.

    Handles authentication, rate limiting, and provides high-level methods
    for common operations.
    """

    def __init__(self):
        """Initialize the Keepa API wrapper."""
        self.api_key = settings.keepa_api_key
        self.domain = KEEPA_DOMAIN_MAP.get(settings.keepa_domain, "US")
        self.api = None

        if not self.api_key:
            raise ValueError("Keepa API key is not configured.")

        try:
            self.api = keepa.Keepa(self.api_key)
            logger.info("✓ Keepa API initialized successfully")
        except Exception as e:
            logger.error(f"✗ Failed to initialize Keepa API: {e}")
            raise

    def get_product_data(self, asins: List[str]) -> List[Dict[str, Any]]:
        """
        Get detailed product data for a list of ASINs.
        Includes 90-day statistics for price/rank analysis.

        Args:
            asins: A list of Amazon Standard Identification Numbers.

        Returns:
            A list of product data dictionaries.
        """
        if not self.api:
            return []

        try:
            products = self.api.query(asins, domain=self.domain, stats=90)
            return products
        except Exception as e:
            logger.error(f"✗ Failed to get product data from Keepa: {e}")
            return []

    def discover_products_by_category(
        self,
        category_id: str,
        price_min: int = None,
        price_max: int = None,
        sales_rank_max: int = None,
        seller_count_max: int = None,
        n_products: int = 50,
    ) -> List[str]:
        """
        Discover product ASINs using Keepa's product_finder.

        Args:
            category_id: Amazon category node ID.
            price_min: Min buy box price in cents (Keepa format).
            price_max: Max buy box price in cents.
            sales_rank_max: Max sales rank to include.
            seller_count_max: Max number of new sellers.
            n_products: Max products to return.

        Returns:
            List of ASIN strings.
        """
        if not self.api:
            return []

        try:
            product_parms = {
                "rootCategory": str(category_id),
                "sort": [["current_SALES", "asc"]],
            }

            if price_min is not None:
                product_parms["current_BUY_BOX_SHIPPING_gte"] = price_min
            if price_max is not None:
                product_parms["current_BUY_BOX_SHIPPING_lte"] = price_max
            if sales_rank_max is not None:
                product_parms["current_SALES_lte"] = sales_rank_max
            if seller_count_max is not None:
                product_parms["current_COUNT_NEW_lte"] = seller_count_max

            asins = self.api.product_finder(
                product_parms,
                domain=self.domain,
                n_products=n_products,
            )
            logger.info(f"product_finder returned {len(asins)} ASINs for category {category_id}")
            return list(asins)

        except Exception as e:
            logger.error(f"✗ Failed to discover products in category {category_id}: {e}")
            return []

    def get_best_sellers(self, category_id: str, rank_avg_range: int = 30) -> List[str]:
        """
        Get bestseller ASINs for a category.

        Args:
            category_id: Category node ID.
            rank_avg_range: 0=current, 30=30-day avg, 90=90-day avg.

        Returns:
            List of ASIN strings.
        """
        if not self.api:
            return []

        try:
            asins = self.api.best_sellers_query(
                category_id,
                rank_avg_range=rank_avg_range,
                domain=self.domain,
            )
            logger.info(f"best_sellers_query returned {len(asins)} ASINs for category {category_id}")
            return list(asins)

        except Exception as e:
            logger.error(f"✗ Failed to get best sellers for category {category_id}: {e}")
            return []

    def search_for_products(self, search_term: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Deprecated: Use discover_products_by_category() instead."""
        logger.warning("search_for_products() is deprecated. Use discover_products_by_category().")
        if category:
            asins = self.discover_products_by_category(category)
            if asins:
                return self.get_product_data(asins[:20])
        return []


# Singleton instance
_keepa_api_instance = None


def get_keepa_api() -> KeepaAPI:
    """Get or create the KeepaAPI instance."""
    global _keepa_api_instance
    if _keepa_api_instance is None:
        _keepa_api_instance = KeepaAPI()
    return _keepa_api_instance
