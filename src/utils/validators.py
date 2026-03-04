"""
Input validation utilities for the Replens Automation System.

Used by Phase 3 (sourcing) for UPC validation and PO generation,
and Phase 4 (repricing) for price validation.
"""

import re
from datetime import datetime
from decimal import Decimal
from typing import Optional


def validate_asin(asin: str) -> bool:
    """
    Validate an Amazon ASIN (10 alphanumeric characters, starts with B0).

    Args:
        asin: The ASIN string to validate

    Returns:
        True if valid
    """
    if not asin or not isinstance(asin, str):
        return False
    return bool(re.match(r"^B0[A-Z0-9]{8}$", asin.upper()))


def validate_upc(upc: str) -> bool:
    """
    Validate a UPC/EAN code (12 or 13 digits).

    Args:
        upc: The UPC/EAN string to validate

    Returns:
        True if valid
    """
    if not upc or not isinstance(upc, str):
        return False
    return bool(re.match(r"^\d{12,13}$", upc))


def validate_price(price: Decimal) -> bool:
    """
    Validate a price is positive and within a reasonable range.

    Args:
        price: The price to validate

    Returns:
        True if valid
    """
    try:
        price = Decimal(str(price))
        return Decimal("0.01") <= price <= Decimal("10000.00")
    except Exception:
        return False


def validate_quantity(quantity: int) -> bool:
    """
    Validate an order quantity is a positive integer.

    Args:
        quantity: The quantity to validate

    Returns:
        True if valid
    """
    return isinstance(quantity, int) and quantity > 0


def sanitize_string(s: Optional[str], max_length: int = 500) -> str:
    """
    Sanitize a string by stripping whitespace and truncating.

    Args:
        s: The string to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized string
    """
    if not s:
        return ""
    return s.strip()[:max_length]


def generate_po_id(asin: str, supplier_id: int) -> str:
    """
    Generate a unique purchase order ID.

    Format: PO-{ASIN}-{SUPPLIER_ID}-{TIMESTAMP}

    Args:
        asin: Product ASIN
        supplier_id: Supplier ID

    Returns:
        Unique PO ID string
    """
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"PO-{asin}-{supplier_id}-{timestamp}"
