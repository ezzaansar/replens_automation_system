"""
Domain service functions for the Replens Automation System.

Re-exports all service functions for convenient imports::

    from src.services import get_product, add_supplier, create_purchase_order
"""

from src.services.product_service import (
    add_product,
    get_product,
    get_underserved_products,
    get_low_stock_products,
    get_repriceable_products,
    get_forecastable_products,
)
from src.services.supplier_service import (
    add_supplier,
    get_supplier,
    get_product_suppliers,
)
from src.services.order_service import create_purchase_order
from src.services.performance_service import (
    record_performance,
    record_repricing_action,
    get_sales_history,
)

__all__ = [
    "add_product",
    "get_product",
    "get_underserved_products",
    "get_low_stock_products",
    "get_repriceable_products",
    "get_forecastable_products",
    "add_supplier",
    "get_supplier",
    "get_product_suppliers",
    "create_purchase_order",
    "record_performance",
    "record_repricing_action",
    "get_sales_history",
]
