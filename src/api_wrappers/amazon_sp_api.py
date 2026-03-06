"""
Amazon Selling Partner API (SP-API) Wrapper

Uses the python-amazon-sp-api library for authentication (LWA + STS role
assumption + SigV4 signing) and provides a clean, high-level interface for:
- Fetching product information
- Getting sales data and orders
- Managing inventory
- Updating prices
- Calculating fees
"""

import logging
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from decimal import Decimal

from sp_api.api import (
    CatalogItems,
    Feeds,
    Inventories,
    Orders,
    ProductFees,
    Products,
    Sellers,
)
from sp_api.base import Marketplaces
from sp_api.base.exceptions import SellingApiException, SellingApiRequestThrottledException

from src.config import settings

logger = logging.getLogger(__name__)

# Map marketplace IDs to sp_api Marketplaces enum
_MARKETPLACE_MAP: Dict[str, Marketplaces] = {
    "ATVPDKIKX0DER": Marketplaces.US,
    "A2EUQ1WTGCTBG2": Marketplaces.CA,
    "A1AM78C64UM0Y8": Marketplaces.MX,
    "A1F83G8C2ARO7P": Marketplaces.GB,
    "A13V1IB3VIYZZH": Marketplaces.FR,
    "A1PA6795UKMFR9": Marketplaces.DE,
    "APJ6JRA9NG5V4": Marketplaces.IT,
    "A1RKKUPIHCS9HS": Marketplaces.ES,
    "A1VC38T7YXB528": Marketplaces.JP,
    "A21TJRUUN4KGV": Marketplaces.IN,
    "A2Q3Y263D00KWC": Marketplaces.BR,
    "A39IBJ37TRP1C6": Marketplaces.AU,
}


class AmazonSPAPI:
    """
    Wrapper for Amazon Selling Partner API.

    Delegates authentication (LWA tokens, STS role assumption, SigV4 signing)
    to the python-amazon-sp-api library.
    """

    def __init__(self):
        """Initialize the SP-API wrapper."""
        self.seller_id = settings.amazon_seller_id
        self.marketplace_id = settings.amazon_marketplace_id

        self._credentials = dict(
            refresh_token=settings.amazon_refresh_token,
            lwa_app_id=settings.amazon_client_id,
            lwa_client_secret=settings.amazon_client_secret,
        )
        self._marketplace = _MARKETPLACE_MAP.get(
            self.marketplace_id, Marketplaces.US
        )

        # Verify credentials are valid by creating a lightweight client
        try:
            Sellers(credentials=self._credentials, marketplace=self._marketplace)
            logger.info("SP-API credentials accepted")
        except Exception as e:
            logger.error("SP-API credential setup failed: %s", e)
            raise

    def _client(self, api_class, **kwargs):
        """Create an SP-API client instance with shared credentials."""
        return api_class(
            credentials=self._credentials,
            marketplace=self._marketplace,
            **kwargs,
        )

    def _handle_sp_error(self, exc: Exception, context: str) -> None:
        """Log SP-API errors consistently."""
        if isinstance(exc, SellingApiRequestThrottledException):
            logger.warning("SP-API throttled during %s: %s", context, exc)
        elif isinstance(exc, SellingApiException):
            logger.error("SP-API error during %s: [%s] %s", context, exc.code, exc)
        else:
            logger.error("Unexpected error during %s: %s", context, exc)

    # ========================================================================
    # CONNECTIVITY TEST
    # ========================================================================

    def get_marketplace_participations(self) -> List[Dict[str, Any]]:
        """Test connectivity using the Sellers API (requires only base SP-API role)."""
        try:
            resp = self._client(Sellers).get_marketplace_participation()
            return resp.payload or []
        except Exception as exc:
            self._handle_sp_error(exc, "get_marketplace_participations")
            raise

    # ========================================================================
    # PRODUCT INFORMATION
    # ========================================================================

    def get_catalog_item(self, asin: str) -> Dict[str, Any]:
        """
        Get catalog item details for an ASIN.

        Args:
            asin: Amazon Standard Identification Number

        Returns:
            Product details dict
        """
        try:
            resp = self._client(
                CatalogItems, version="2022-04-01"
            ).get_catalog_item(
                asin=asin,
                includedData="attributes,identifiers,images,productTypes,summaries",
            )
            return resp.payload or {}
        except Exception as exc:
            self._handle_sp_error(exc, f"get_catalog_item({asin})")
            raise

    def get_product_pricing(self, asin: str) -> Dict[str, Any]:
        """
        Get current competitive pricing information for a product.

        Args:
            asin: Product ASIN

        Returns:
            Pricing data including Buy Box price
        """
        try:
            resp = self._client(Products).get_competitive_pricing_for_asins(
                asin_list=[asin],
            )
            return resp.payload or {}
        except Exception as exc:
            self._handle_sp_error(exc, f"get_product_pricing({asin})")
            raise

    def get_my_price(self, asin: str) -> Dict[str, Any]:
        """
        Get your current price for a product.

        Args:
            asin: Product ASIN

        Returns:
            Your pricing information
        """
        try:
            resp = self._client(Products).get_product_pricing_for_asins(
                asin_list=[asin],
            )
            return resp.payload or {}
        except Exception as exc:
            self._handle_sp_error(exc, f"get_my_price({asin})")
            raise

    # ========================================================================
    # INVENTORY MANAGEMENT
    # ========================================================================

    def get_inventory_summaries(self) -> List[Dict[str, Any]]:
        """
        Get inventory summaries for all your SKUs.

        Returns:
            List of inventory summaries
        """
        try:
            resp = self._client(Inventories).get_inventory_summary_marketplace(
                granularityType="Marketplace",
                granularityId=self.marketplace_id,
            )
            return resp.payload.get("inventorySummaries", [])
        except Exception as exc:
            self._handle_sp_error(exc, "get_inventory_summaries")
            raise

    def get_inventory_summary(self, sku: str) -> Optional[Dict[str, Any]]:
        """
        Get inventory summary for a specific SKU.

        Args:
            sku: Your product SKU

        Returns:
            Inventory summary or None if not found
        """
        try:
            resp = self._client(Inventories).get_inventory_summary_marketplace(
                granularityType="Marketplace",
                granularityId=self.marketplace_id,
                sellerSkus=[sku],
            )
            summaries = resp.payload.get("inventorySummaries", [])
            return summaries[0] if summaries else None
        except Exception as exc:
            self._handle_sp_error(exc, f"get_inventory_summary({sku})")
            return None

    # ========================================================================
    # PRICING UPDATES
    # ========================================================================

    def update_price(self, sku: str, price: Decimal) -> bool:
        """
        Update the price for a product via the Feeds API.

        Args:
            sku: Your product SKU
            price: New price

        Returns:
            True if the feed was submitted successfully
        """
        import xml.etree.ElementTree as ET

        # Build pricing feed XML
        envelope = ET.Element("AmazonEnvelope")
        envelope.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        envelope.set("xsi:noNamespaceSchemaLocation", "amzn-envelope.xsd")

        header = ET.SubElement(envelope, "Header")
        ET.SubElement(header, "DocumentVersion").text = "1.01"
        ET.SubElement(header, "MerchantIdentifier").text = str(self.seller_id)

        ET.SubElement(envelope, "MessageType").text = "Price"

        message = ET.SubElement(envelope, "Message")
        ET.SubElement(message, "MessageID").text = "1"
        ET.SubElement(message, "OperationType").text = "Update"

        price_elem = ET.SubElement(message, "Price")
        ET.SubElement(price_elem, "SKU").text = str(sku)
        std_price = ET.SubElement(price_elem, "StandardPrice")
        std_price.set("currency", "USD")
        std_price.text = str(price)

        ET.indent(envelope, space="    ")
        pricing_xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(
            envelope, encoding="unicode"
        )

        try:
            resp = self._client(Feeds).submit_feed(
                "POST_PRODUCT_PRICING_DATA",
                pricing_xml.encode("utf-8"),
                content_type="text/xml; charset=UTF-8",
            )
            feed_id = resp.payload.get("feedId") if resp.payload else None
            logger.info(
                "Price update feed submitted for %s: $%s (feedId=%s)",
                sku, price, feed_id,
            )
            return True
        except Exception as exc:
            self._handle_sp_error(exc, f"update_price({sku})")
            return False

    # ========================================================================
    # ORDERS
    # ========================================================================

    def get_orders(
        self,
        created_after: Optional[datetime] = None,
        order_statuses: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get orders.

        Args:
            created_after: Only get orders after this date
            order_statuses: Filter by order status

        Returns:
            List of orders
        """
        if not created_after:
            created_after = datetime.utcnow() - timedelta(days=7)

        if not order_statuses:
            order_statuses = [
                "Unshipped", "PartiallyShipped", "Shipped",
                "Cancelled", "Unfulfillable",
            ]

        try:
            resp = self._client(Orders).get_orders(
                CreatedAfter=created_after.isoformat(),
                OrderStatuses=order_statuses,
                MarketplaceIds=[self.marketplace_id],
            )
            return resp.payload.get("Orders", [])
        except Exception as exc:
            self._handle_sp_error(exc, "get_orders")
            raise

    def get_order_items(self, order_id: str) -> List[Dict[str, Any]]:
        """
        Get items in an order.

        Args:
            order_id: Amazon order ID

        Returns:
            List of order items
        """
        try:
            resp = self._client(Orders).get_order_items(order_id=order_id)
            return resp.payload.get("OrderItems", [])
        except Exception as exc:
            self._handle_sp_error(exc, f"get_order_items({order_id})")
            raise

    # ========================================================================
    # SALES DATA
    # ========================================================================

    def get_sales_data(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """
        Get sales data for a date range (placeholder — needs Reports API).

        Args:
            start_date: Start date for sales data
            end_date: End date for sales data

        Returns:
            Sales data
        """
        logger.info("Fetching sales data from %s to %s", start_date, end_date)
        return {}

    # ========================================================================
    # FEES
    # ========================================================================

    def estimate_fees(
        self, asin: str, price: Decimal, quantity: int = 1
    ) -> Dict[str, Decimal]:
        """
        Estimate Amazon fees for a product.

        Args:
            asin: Product ASIN
            price: Selling price
            quantity: Number of units

        Returns:
            Dictionary with fee breakdown
        """
        try:
            resp = self._client(ProductFees).get_product_fees_estimate_for_asin(
                asin=asin,
                price=float(price),
                currency="USD",
                is_fba=True,
            )
            fee_detail = resp.payload or {}
            estimate = (
                fee_detail
                .get("FeesEstimateResult", {})
                .get("FeesEstimate", {})
            )
            fee_list = estimate.get("FeeDetailList", [])

            referral = Decimal("0")
            fba = Decimal("0")
            closing = Decimal("0")
            for fee in fee_list:
                fee_type = fee.get("FeeType", "")
                amount = Decimal(str(fee.get("FinalFee", {}).get("Amount", 0)))
                if fee_type == "ReferralFee":
                    referral = amount
                elif fee_type == "FBAFees":
                    fba = amount
                elif fee_type == "VariableClosingFee":
                    closing = amount

            return {
                "referral_fee": referral,
                "fba_fee": fba,
                "variable_closing_fee": closing,
            }
        except SellingApiException as exc:
            self._handle_sp_error(exc, f"estimate_fees({asin})")
            if exc.code == 403:
                raise
            return {"referral_fee": Decimal(0), "fba_fee": Decimal(0), "variable_closing_fee": Decimal(0)}
        except Exception as exc:
            self._handle_sp_error(exc, f"estimate_fees({asin})")
            return {"referral_fee": Decimal(0), "fba_fee": Decimal(0), "variable_closing_fee": Decimal(0)}


# Singleton instance
_sp_api_lock = threading.Lock()
_sp_api_instance = None


def get_sp_api() -> AmazonSPAPI:
    """Get or create the SP-API instance (thread-safe)."""
    global _sp_api_instance
    if _sp_api_instance is None:
        with _sp_api_lock:
            if _sp_api_instance is None:
                _sp_api_instance = AmazonSPAPI()
    return _sp_api_instance
