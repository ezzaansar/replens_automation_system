# Amazon Replens Automation System

## Project Overview

Automated Amazon FBA replenishment platform. Discovers profitable products via Keepa, matches suppliers, and manages procurement. Built with Python 3.12, managed with `uv`.

## Tech Stack

- **Runtime:** Python 3.12, `uv` package manager
- **Config:** Pydantic Settings + `.env`
- **Database:** SQLAlchemy ORM, SQLite (dev), PostgreSQL (prod)
- **APIs:** Amazon SP-API, Keepa, OpenAI (optional)
- **Dashboard:** Streamlit (stub)
- **ML:** Weighted scoring model (discovery_model.py)

## Project Structure

```
src/
  main.py              # Orchestrates all phases sequentially
  config.py            # Pydantic Settings + business constants
  database.py          # Engine, session factory, DatabaseOperations facade
  api_wrappers/
    amazon_sp_api.py   # SP-API: auth, pricing, inventory, orders, fees
    keepa_api.py       # Keepa: product_finder, best_sellers, product data
  phases/
    phase_1_setup.py   # [IMPLEMENTED] DB init, config validation, API tests
    phase_2_discovery.py  # [IMPLEMENTED] Keepa discovery, feature extraction, ML scoring
    phase_3_sourcing.py   # [IMPLEMENTED] Supplier matching, profitability, PO generation
    phase_4_repricing.py  # [IMPLEMENTED] Dynamic repricing (Buy Box optimization)
    phase_5_forecasting.py # [STUB] Inventory forecasting
  models/
    base.py            # SQLAlchemy declarative base
    product.py         # Product ORM model
    supplier.py        # Supplier + ProductSupplier ORM models
    inventory.py       # Inventory ORM model
    purchase_order.py  # PurchaseOrder ORM model
    performance.py     # Performance ORM model
    discovery_model.py # Weighted scoring model (not true ML yet)
  services/
    product_service.py   # Product CRUD operations
    supplier_service.py  # Supplier CRUD operations
    order_service.py     # Purchase order operations
    performance_service.py # Performance recording + repricing actions
  dashboard/
    app.py             # Streamlit stub
  utils/
    logger.py          # Centralized logging setup
    profitability.py   # Fee estimation, profit math, threshold checks
    validators.py      # ASIN/UPC/price validation, PO ID generation
tests/                 # Test suite (pytest)
docs/                  # Project documentation
```

## Running

```bash
uv sync                          # Install dependencies
uv run python src/main.py        # Run full pipeline (phases 1-5)
uv run python src/phases/phase_2_discovery.py  # Run single phase
uv run streamlit run src/dashboard/app.py      # Dashboard (stub)
```

## Database Tables

6 tables: `products`, `suppliers`, `product_suppliers`, `inventory`, `purchase_orders`, `performance`. See `docs/Database.md`.

## Pipeline Flow

1. **Phase 1 (Setup):** DB init, config validation, API connection tests
2. **Phase 2 (Discovery):** Keepa product_finder -> feature extraction from `product['data']` dict -> weighted scoring -> save to DB. Products with score >= 50 marked `is_underserved=True`.
3. **Phase 3 (Sourcing):** For each underserved product: enrich UPC via SP-API, get supplier suggestions (OpenAI or rule-based COGS estimation), calculate profitability, select preferred supplier, initialize inventory, generate POs.
4. **Phase 4 (Repricing):** For each product with inventory + preferred supplier: calculate price floor from supplier cost, fetch Buy Box price via SP-API, undercut by `price_adjustment_amount` ($0.01), clamp to floor, apply via SP-API (or log in `dry_run` mode), record to Performance table. Disables SP-API pricing calls on 403.
5. **Phase 5 (Forecasting):** Stub - not implemented

## Key Configuration (.env)

- `AMAZON_CLIENT_ID/SECRET/REFRESH_TOKEN/SELLER_ID` — SP-API credentials (required)
- `KEEPA_API_KEY` — Keepa API key (required)
- `OPENAI_API_KEY` — Optional, enhances Phase 3 supplier suggestions
- `DISCOVERY_CATEGORIES` — Comma-separated Amazon category node IDs
- `MIN_PROFIT_MARGIN=0.25`, `MIN_ROI=1.0`, `MIN_SALES_VELOCITY=10`

## Known Issues / Limitations

- SP-API returns 403 on most endpoints (client needs to enable roles: Product Listing, Product Pricing, Product Fees, FBA Inventory, Orders, Feeds)
- OpenAI key in .env is placeholder — falls back to rule-based supplier estimation
- Phase 5 is a stub
- Dashboard is a stub
- No scheduler implemented (referenced in docs but `scheduler.py` doesn't exist)

## Important Implementation Details

- Keepa data parsing uses `product['data']` dict (pre-parsed by keepa library with timestamps stripped, prices in dollars). Do NOT use raw `product['csv']` — it contains interleaved [timestamp, value] pairs.
- SP-API fee estimation falls back to local calculation (`utils/profitability.py`) on 403 errors.
- `config.py` loads settings at import time via `settings = Settings()`. Requires valid `.env`.
- `is_underserved` threshold: `opportunity_score >= 50`
- Profitability thresholds: margin >= 25%, ROI >= 100%, lead time <= 30 days, reliability >= 70
