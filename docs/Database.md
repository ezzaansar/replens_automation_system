# Database Schema

SQLAlchemy ORM models defined in `src/models/` (one file per model). Engine, session factory, and CRUD facade in `src/database.py`. Supports SQLite (dev) and PostgreSQL (prod).

## Entity Relationship

```
products ──┬── product_suppliers ──── suppliers
            ├── inventory
            ├── purchase_orders ──────── suppliers
            └── performance
```

## Tables

### `products`

Tracks Amazon products (ASINs) for replens opportunities.

| Column | Type | Description |
|---|---|---|
| `asin` | String(10) | **PK**. Amazon Standard Identification Number |
| `upc` | String(14) | Universal Product Code (nullable) |
| `sku` | String(40) | Amazon SKU for price updates (nullable) |
| `title` | String(500) | Product title |
| `category` | String(200) | Amazon category |
| `current_price` | Numeric(10,2) | Current selling price |
| `sales_rank` | Integer | Current sales rank |
| `estimated_monthly_sales` | Integer | ML-estimated units/month |
| `profit_potential` | Numeric(10,2) | Estimated profit per unit |
| `num_sellers` | Integer | Number of active sellers |
| `num_fba_sellers` | Integer | Number of FBA sellers |
| `buy_box_owner` | String(200) | Current Buy Box owner |
| `price_history_avg` | Numeric(10,2) | 90-day average price |
| `price_stability` | Numeric(10,2) | Price standard deviation |
| `is_underserved` | Boolean | True if opportunity_score >= 50 |
| `opportunity_score` | Float | 0-100 opportunity ranking |
| `status` | String(20) | `active`, `archived`, `rejected` |
| `notes` | Text | Manual notes |
| `created_at` | DateTime | Record creation time |
| `last_updated` | DateTime | Last update time (auto) |

**Indexes:** `asin`, `upc`, `sku`, `(status, opportunity_score)`, `is_underserved`

### `suppliers`

Supplier/vendor information.

| Column | Type | Description |
|---|---|---|
| `supplier_id` | Integer | **PK** (auto-increment) |
| `name` | String(200) | Supplier name (unique) |
| `website` | String(500) | Website URL |
| `contact_email` | String(200) | Contact email |
| `min_order_qty` | Integer | Minimum order quantity |
| `lead_time_days` | Integer | Delivery lead time in days |
| `reliability_score` | Float | 0-100 performance score |
| `last_order_date` | DateTime | Last order date |
| `total_orders` | Integer | Lifetime order count |
| `on_time_delivery_rate` | Float | 0-1 on-time rate |
| `status` | String(20) | `active`, `inactive`, `blacklisted` |
| `notes` | Text | Notes |
| `created_at` | DateTime | Record creation time |
| `last_updated` | DateTime | Last update time (auto) |

**Indexes:** `supplier_id`, `name`

### `product_suppliers`

Junction table linking products to suppliers with cost/profitability data.

| Column | Type | Description |
|---|---|---|
| `id` | Integer | **PK** (auto-increment) |
| `asin` | String(10) | **FK** → products.asin |
| `supplier_id` | Integer | **FK** → suppliers.supplier_id |
| `supplier_cost` | Numeric(10,2) | Cost per unit |
| `shipping_cost` | Numeric(10,2) | Shipping per unit |
| `total_cost` | Numeric(10,2) | Landed cost (supplier + shipping) |
| `estimated_profit` | Numeric(10,2) | Profit per unit |
| `profit_margin` | Float | 0-1 (e.g., 0.25 = 25%) |
| `roi` | Float | Return on investment |
| `is_preferred` | Boolean | Preferred supplier flag |
| `status` | String(20) | `active`, `inactive` |
| `created_at` | DateTime | Record creation time |
| `last_updated` | DateTime | Last update time (auto) |

**Indexes:** `asin`, `supplier_id`

### `inventory`

Current and forecasted stock levels per product.

| Column | Type | Description |
|---|---|---|
| `asin` | String(10) | **PK, FK** → products.asin |
| `current_stock` | Integer | Units in Amazon FBA |
| `reserved` | Integer | Units reserved for orders |
| `available` | Integer | Units available (stock - reserved) |
| `reorder_point` | Integer | Reorder trigger level |
| `safety_stock` | Integer | Minimum buffer stock |
| `forecasted_stock_30d` | Integer | Predicted stock in 30 days |
| `forecasted_stock_60d` | Integer | Predicted stock in 60 days |
| `last_restock_date` | DateTime | Last restock date |
| `days_of_supply` | Float | Days until stockout |
| `needs_reorder` | Boolean | Reorder flag |
| `created_at` | DateTime | Record creation time |
| `last_updated` | DateTime | Last update time (auto) |

**Indexes:** `asin`, `needs_reorder`

### `purchase_orders`

Procurement tracking.

| Column | Type | Description |
|---|---|---|
| `po_id` | String(50) | **PK**. Format: `PO-{ASIN}-{SUPPLIER_ID}-{TIMESTAMP}` |
| `asin` | String(10) | **FK** → products.asin |
| `supplier_id` | Integer | **FK** → suppliers.supplier_id |
| `quantity` | Integer | Units ordered |
| `unit_cost` | Numeric(10,2) | Cost per unit |
| `total_cost` | Numeric(10,2) | Total PO cost |
| `status` | String(20) | `pending`, `confirmed`, `shipped`, `received`, `cancelled` |
| `order_date` | DateTime | PO creation date |
| `expected_delivery` | DateTime | Expected arrival |
| `actual_delivery` | DateTime | Actual arrival |
| `notes` | Text | Notes |
| `created_at` | DateTime | Record creation time |
| `last_updated` | DateTime | Last update time (auto) |

**Indexes:** `po_id`, `asin`, `supplier_id`, `status`

### `performance`

Daily per-product sales and profit metrics.

| Column | Type | Description |
|---|---|---|
| `id` | Integer | **PK** (auto-increment) |
| `asin` | String(10) | **FK** → products.asin |
| `date` | DateTime | Metrics date |
| `units_sold` | Integer | Units sold |
| `revenue` | Numeric(10,2) | Revenue |
| `cost_of_goods` | Numeric(10,2) | COGS |
| `amazon_fees` | Numeric(10,2) | Amazon fees |
| `net_profit` | Numeric(10,2) | Net profit |
| `buy_box_owned` | Boolean | Buy Box owned flag |
| `buy_box_percentage` | Float | 0-1 Buy Box ownership % |
| `price` | Numeric(10,2) | End-of-day price |
| `competitor_price` | Numeric(10,2) | Lowest competitor price |
| `sales_rank` | Integer | End-of-day sales rank |
| `created_at` | DateTime | Record creation time |

**Indexes:** `(asin, date)`, `asin`, `date`

## Usage

```python
from src.database import init_db, DatabaseOperations, SessionLocal
# Or import models from their canonical location:
from src.models import Product, Supplier, Inventory

# Initialize tables
init_db()

# Use CRUD operations
session = SessionLocal()
db = DatabaseOperations()
product = db.get_product(session, "B0EXAMPLE1")
underserved = db.get_underserved_products(session, limit=50)
```
