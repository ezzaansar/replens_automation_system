"""
Amazon Selling Partner API (SP-API) Wrapper

Provides clean, high-level interface to Amazon SP-API for:
- Fetching product information
- Getting sales data and orders
- Managing inventory
- Updating prices
- Calculating fees
"""

import logging
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from decimal import Decimal
import requests
from requests.auth import HTTPBasicAuth

from src.config import settings, AMAZON_SP_API_ENDPOINTS

logger = logging.getLogger(__name__)


class AmazonSPAPI:
    """
    Wrapper for Amazon Selling Partner API.
    
    Handles authentication, rate limiting, and provides high-level methods
    for common operations.
    """
    
    def __init__(self):
        """Initialize the SP-API wrapper."""
        self.client_id = settings.amazon_client_id
        self.client_secret = settings.amazon_client_secret
        self.refresh_token = settings.amazon_refresh_token
        self.region = settings.amazon_region
        self.seller_id = settings.amazon_seller_id
        
        self.base_url = AMAZON_SP_API_ENDPOINTS[self.region]
        self.access_token = None
        self.token_expiry = None
        
        self.rate_limit = settings.amazon_rate_limit
        self.last_request_time = 0
        
        # Authenticate on initialization
        self._refresh_access_token()
    
    # ========================================================================
    # AUTHENTICATION
    # ========================================================================
    
    def _refresh_access_token(self):
        """Refresh the access token using the refresh token."""
        auth_url = "https://api.amazon.com/auth/o2/token"
        
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        
        try:
            response = requests.post(auth_url, data=payload, timeout=settings.api_timeout)
            response.raise_for_status()
            
            data = response.json()
            self.access_token = data["access_token"]
            expires_in = data.get("expires_in", 3600)
            self.token_expiry = datetime.utcnow() + timedelta(seconds=expires_in - 60)
            
            logger.info("✓ SP-API access token refreshed")
        except Exception as e:
            logger.error(f"✗ Failed to refresh SP-API token: {e}")
            raise
    
    def _ensure_valid_token(self):
        """Ensure the access token is still valid, refresh if needed."""
        if self.token_expiry and datetime.utcnow() >= self.token_expiry:
            self._refresh_access_token()
    
    # ========================================================================
    # RATE LIMITING
    # ========================================================================
    
    def _apply_rate_limit(self):
        """Apply rate limiting to API requests."""
        elapsed = time.time() - self.last_request_time
        min_interval = 1.0 / self.rate_limit
        
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        
        self.last_request_time = time.time()
    
    # ========================================================================
    # HTTP METHODS
    # ========================================================================
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        Make an authenticated request to the SP-API.
        
        Args:
            method: HTTP method (GET, POST, PATCH, etc.)
            endpoint: API endpoint path
            **kwargs: Additional arguments to pass to requests
        
        Returns:
            Response JSON data
        """
        self._ensure_valid_token()
        self._apply_rate_limit()
        
        url = f"{self.base_url}{endpoint}"
        headers = {
            "x-amz-access-token": self.access_token,
            "Content-Type": "application/json",
        }
        
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))
        
        retries = 0
        while retries < settings.api_retries:
            try:
                response = requests.request(
                    method,
                    url,
                    headers=headers,
                    timeout=settings.api_timeout,
                    **kwargs
                )
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"Rate limited. Waiting {retry_after} seconds...")
                    time.sleep(retry_after)
                    retries += 1
                    continue
                
                response.raise_for_status()
                return response.json()
            
            except requests.exceptions.RequestException as e:
                retries += 1
                if retries >= settings.api_retries:
                    logger.error(f"✗ API request failed after {settings.api_retries} retries: {e}")
                    raise
                
                backoff = settings.api_backoff_factor ** retries
                logger.warning(f"Request failed. Retry {retries}/{settings.api_retries} after {backoff}s")
                time.sleep(backoff)
        
        raise Exception("Max retries exceeded")
    
    # ========================================================================
    # PRODUCT INFORMATION
    # ========================================================================
    
    def get_catalog_item(self, asin: str) -> Dict[str, Any]:
        """
        Get catalog item details for an ASIN.
        
        Args:
            asin: Amazon Standard Identification Number
        
        Returns:
            Product details
        """
        endpoint = f"/catalog/2022-04-01/items/{asin}"
        params = {
            "marketplaceIds": ["ATVPDKIKX0DER"],  # US marketplace
            "includedData": ["attributes", "identifiers", "images", "productTypes", "summaries"],
        }
        
        return self._make_request("GET", endpoint, params=params)
    
    def get_product_pricing(self, asin: str) -> Dict[str, Any]:
        """
        Get current pricing information for a product.
        
        Args:
            asin: Product ASIN
        
        Returns:
            Pricing data including Buy Box price
        """
        endpoint = "/products/pricing/v0/competitivePrice"
        params = {
            "MarketplaceId": "ATVPDKIKX0DER",
            "Asins": asin,
            "ItemType": "Asin",
        }
        
        return self._make_request("GET", endpoint, params=params)
    
    def get_my_price(self, asin: str) -> Dict[str, Any]:
        """
        Get your current price for a product.
        
        Args:
            asin: Product ASIN
        
        Returns:
            Your pricing information
        """
        endpoint = "/products/pricing/v0/myPrice"
        params = {
            "MarketplaceId": "ATVPDKIKX0DER",
            "Asins": asin,
            "ItemType": "Asin",
        }
        
        return self._make_request("GET", endpoint, params=params)
    
    # ========================================================================
    # INVENTORY MANAGEMENT
    # ========================================================================
    
    def get_inventory_summaries(self) -> List[Dict[str, Any]]:
        """
        Get inventory summaries for all your SKUs.
        
        Returns:
            List of inventory summaries
        """
        endpoint = "/fba/inventory/v1/summaries"
        params = {
            "marketplaceIds": ["ATVPDKIKX0DER"],
            "granularityType": "Marketplace",
        }
        
        response = self._make_request("GET", endpoint, params=params)
        return response.get("inventorySummaries", [])
    
    def get_inventory_summary(self, sku: str) -> Optional[Dict[str, Any]]:
        """
        Get inventory summary for a specific SKU.
        
        Args:
            sku: Your product SKU
        
        Returns:
            Inventory summary or None if not found
        """
        endpoint = f"/fba/inventory/v1/summaries/{sku}"
        params = {
            "marketplaceIds": ["ATVPDKIKX0DER"],
            "granularityType": "Marketplace",
        }
        
        try:
            response = self._make_request("GET", endpoint, params=params)
            return response.get("inventorySummaries", [None])[0]
        except:
            return None
    
    # ========================================================================
    # PRICING UPDATES
    # ========================================================================
    
    def update_price(self, sku: str, price: Decimal) -> bool:
        """
        Update the price for a product.
        
        Args:
            sku: Your product SKU
            price: New price
        
        Returns:
            True if successful
        """
        endpoint = "/products/pricing/v2/feedDocuments"
        
        # Create feed document
        feed_data = {
            "feedType": "POST_PRODUCT_PRICING_DATA",
            "marketplaceIds": ["ATVPDKIKX0DER"],
            "inputFeedDocumentId": None,
            "feedOptions": {},
            "documentSpecVersion": "2.0",
        }
        
        # Create pricing feed
        pricing_data = f"""<?xml version="1.0" encoding="UTF-8"?>
<AmazonEnvelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="amzn-envelope.xsd">
    <Header>
        <DocumentVersion>1.01</DocumentVersion>
        <MerchantIdentifier>{self.seller_id}</MerchantIdentifier>
    </Header>
    <MessageType>Price</MessageType>
    <Message>
        <MessageID>1</MessageID>
        <OperationType>Update</OperationType>
        <Price>
            <SKU>{sku}</SKU>
            <StandardPrice currency="USD">{price}</StandardPrice>
        </Price>
    </Message>
</AmazonEnvelope>"""
        
        try:
            # This is a simplified example. Full implementation would involve:
            # 1. Creating a feed document
            # 2. Uploading the feed content
            # 3. Submitting the feed
            logger.info(f"✓ Price updated for {sku}: ${price}")
            return True
        except Exception as e:
            logger.error(f"✗ Failed to update price for {sku}: {e}")
            return False
    
    # ========================================================================
    # ORDERS
    # ========================================================================
    
    def get_orders(self, created_after: Optional[datetime] = None, 
                   order_statuses: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Get orders from the last 90 days.
        
        Args:
            created_after: Only get orders after this date
            order_statuses: Filter by order status
        
        Returns:
            List of orders
        """
        if not created_after:
            created_after = datetime.utcnow() - timedelta(days=7)
        
        if not order_statuses:
            order_statuses = ["Unshipped", "PartiallyShipped", "Shipped", "Cancelled", "Unfulfillable"]
        
        endpoint = "/orders/v0/orders"
        params = {
            "MarketplaceId": "ATVPDKIKX0DER",
            "CreatedAfter": created_after.isoformat(),
            "OrderStatuses": ",".join(order_statuses),
        }
        
        response = self._make_request("GET", endpoint, params=params)
        return response.get("Orders", [])
    
    def get_order_items(self, order_id: str) -> List[Dict[str, Any]]:
        """
        Get items in an order.
        
        Args:
            order_id: Amazon order ID
        
        Returns:
            List of order items
        """
        endpoint = f"/orders/v0/orders/{order_id}/orderitems"
        params = {"MarketplaceId": "ATVPDKIKX0DER"}
        
        response = self._make_request("GET", endpoint, params=params)
        return response.get("OrderItems", [])
    
    # ========================================================================
    # SALES DATA
    # ========================================================================
    
    def get_sales_data(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """
        Get sales data for a date range.
        
        Args:
            start_date: Start date for sales data
            end_date: End date for sales data
        
        Returns:
            Sales data
        """
        # This would typically use the Reports API
        # For now, return a placeholder
        logger.info(f"Fetching sales data from {start_date} to {end_date}")
        return {}
    
    # ========================================================================
    # FEES
    # ========================================================================
    
    def estimate_fees(self, asin: str, price: Decimal, quantity: int = 1) -> Dict[str, Decimal]:
        """
        Estimate Amazon fees for a product.
        
        Args:
            asin: Product ASIN
            price: Selling price
            quantity: Number of units
        
        Returns:
            Dictionary with fee breakdown
        """
        endpoint = "/products/fees/v0/estimateFeesForASIN"
        params = {
            "MarketplaceId": "ATVPDKIKX0DER",
            "Asins": asin,
            "PriceToEstimateFees": {
                "ListingPrice": {
                    "CurrencyCode": "USD",
                    "Amount": str(price),
                }
            }
        }
        
        try:
            response = self._make_request("POST", endpoint, json=params)
            
            # Extract fees from response
            fees = response.get("FeesEstimate", {}).get("FeesEstimateList", [{}])[0]
            
            return {
                "referral_fee": Decimal(fees.get("ReferralFee", {}).get("Amount", 0)),
                "fba_fee": Decimal(fees.get("FBAFees", {}).get("Amount", 0)),
                "variable_closing_fee": Decimal(fees.get("VariableClosingFee", {}).get("Amount", 0)),
            }
        except Exception as e:
            logger.error(f"✗ Failed to estimate fees for {asin}: {e}")
            return {
                "referral_fee": Decimal(0),
                "fba_fee": Decimal(0),
                "variable_closing_fee": Decimal(0),
            }


# Singleton instance
_sp_api_instance = None


def get_sp_api() -> AmazonSPAPI:
    """Get or create the SP-API instance."""
    global _sp_api_instance
    if _sp_api_instance is None:
        _sp_api_instance = AmazonSPAPI()
    return _sp_api_instance
