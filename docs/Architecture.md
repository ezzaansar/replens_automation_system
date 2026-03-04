# System Architecture

## Overview

The system is a 5-phase pipeline that runs sequentially via `src/main.py`. Each phase is an independent module that can also run standalone.

```
┌─────────────────────────────────────────────────────────┐
│                    PIPELINE FLOW                         │
│                                                          │
│  Phase 1        Phase 2         Phase 3                  │
│  Setup    ───>  Discovery  ───> Sourcing                 │
│  (DB init,      (Keepa →        (Suppliers,              │
│   API tests)     scoring)        POs)                    │
│                                    │                     │
│                    ┌───────────────┘                     │
│                    ▼                                      │
│               Phase 4          Phase 5                   │
│               Repricing  ───>  Forecasting               │
│               (stub)           (stub)                    │
└─────────────────────────────────────────────────────────┘
```

## Components

### Entry Point (`src/main.py`)

Runs phases 1-5 sequentially. Aborts if Phase 1 or 2 fails.

### Configuration (`src/config.py`)

- Pydantic `BaseSettings` loaded from `.env` at import time
- Business constants: Amazon fee tables, COGS estimates, thresholds
- Singleton `settings` instance used throughout the codebase

### Database (`src/database.py`)

- SQLAlchemy ORM with 6 tables (see [Database.md](Database.md))
- SQLite (dev) or PostgreSQL (prod), configured via `DATABASE_URL`
- `DatabaseOperations` class provides high-level CRUD methods
- Engine created at import time based on `DATABASE_TYPE`

### API Wrappers (`src/api_wrappers/`)

**`amazon_sp_api.py`** - Amazon Selling Partner API:
- OAuth2 token refresh with automatic expiry handling
- Rate limiting (configurable requests/second)
- Retry with exponential backoff (3 retries default)
- Endpoints: catalog items, pricing, inventory, orders, fees
- Singleton via `get_sp_api()`

**`keepa_api.py`** - Keepa API:
- Wraps the `keepa` Python library
- `product_finder()` - discover ASINs by category with filters
- `best_sellers_query()` - fallback discovery method
- `query()` - get detailed product data with 90-day stats
- Singleton via `get_keepa_api()`

### Utility Modules (`src/utils/`)

**`profitability.py`** - Shared profit math:
- `estimate_amazon_fees()` - referral + FBA fees by category/weight
- `calculate_profitability()` - net profit, margin, ROI
- `meets_profitability_thresholds()` - margin/ROI/lead-time/reliability checks
- `calculate_min_price()` - floor price for repricing engine

**`validators.py`** - Input validation:
- ASIN, UPC, price, quantity validation
- String sanitization, PO ID generation

**`logger.py`** - Centralized logging config

### ML Models (`src/models/`)

**`discovery_model.py`** - Weighted scoring (not true ML):
- 6-feature weighted sum: price stability, competition, rank, velocity, margin, ROI
- Returns 0-1 score, scaled to 0-100 in Phase 2
- `train()`, `save()`, `load()` are placeholder methods

## Data Flow

```
Keepa API                          Amazon SP-API
    │                                   │
    ▼                                   ▼
Phase 2: Discovery              Phase 3: Sourcing
    │                                   │
    │  product_finder()                 │  get_catalog_item()
    │  best_sellers_query()             │  estimate_fees()
    │  query() → product['data']        │
    │                                   │
    ▼                                   ▼
┌─────────────────────────────────────────┐
│              SQLite / PostgreSQL          │
│                                          │
│  products ←──── product_suppliers        │
│     │                  │                 │
│     ├── inventory      ├── suppliers     │
│     ├── performance    └── purchase_orders│
│     └── purchase_orders                  │
└─────────────────────────────────────────┘
```

## External Dependencies

| Service | Required | Used By | Purpose |
|---|---|---|---|
| Keepa API | Yes | Phase 2 | Product discovery, historical data |
| Amazon SP-API | Yes | Phase 1, 2, 3 | Catalog, fees, inventory, orders |
| OpenAI API | No | Phase 3 | Supplier suggestions (falls back to rule-based) |
