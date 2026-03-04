# Pipeline Phases

## Phase 1: Foundation Setup

**File:** `src/phases/phase_1_setup.py`
**Status:** Implemented

Sets up the system foundation. Runs 6 steps:

1. Configure logging (file + console)
2. Validate configuration (checks required API keys)
3. Initialize database (create all tables)
4. Test Amazon SP-API connection (tries `get_inventory_summaries()`)
5. Test Keepa API connection (initializes keepa client)
6. Create sample data (skips if products exist)

**Behavior:** Returns `True` even if API tests fail — logs warnings and continues. The main pipeline (`src/main.py`) aborts if Phase 1 returns `False`.

```bash
uv run python src/phases/phase_1_setup.py
```

---

## Phase 2: Product Discovery

**File:** `src/phases/phase_2_discovery.py`
**Status:** Implemented

Discovers and scores replenishable product opportunities.

### Workflow

1. **ASIN Discovery** — Uses `keepa.product_finder()` for each category in `DISCOVERY_CATEGORIES`. Falls back to `best_sellers_query()` if product_finder returns nothing. Deduplicates and caps at `DISCOVERY_MAX_PRODUCTS`.

2. **Product Data Fetch** — Queries Keepa for detailed data in batches of 100 ASINs. Uses `stats=90` for 90-day statistics.

3. **Feature Extraction** — From the pre-parsed `product['data']` dict:
   - `data['NEW']` — marketplace new prices (numpy array, already in dollars)
   - `data['SALES']` — sales rank history
   - `data['COUNT_NEW']` — new offer count history
   - Calculates: avg price, price stability, avg rank, avg seller count
   - Sales velocity from `stats['salesRankDrops30']` or rank-based estimation

4. **Profitability Analysis** — Tries SP-API `estimate_fees()`, falls back to local estimation on 403. Uses category-aware COGS ratios.

5. **ML Scoring** — Weighted sum model (6 features):
   ```
   Score = 0.15 * price_stability
        + 0.20 * low_competition (sellers < 5)
        + 0.20 * good_sales_rank (rank < 50K)
        + 0.20 * sales_velocity (normalized)
        + 0.15 * profit_margin
        + 0.10 * roi (normalized)
   ```
   Additive penalties for below-threshold margin/ROI/velocity.
   Products with score >= 50 are marked `is_underserved=True`.

6. **Save** — Upserts products to the `products` table.

### Key Classes

- `ProductDiscoveryEngine` — main engine
- `DiscoveryModel` (`src/models/discovery_model.py`) — weighted scoring

```bash
uv run python src/phases/phase_2_discovery.py
```

---

## Phase 3: Supplier Matching & Procurement

**File:** `src/phases/phase_3_sourcing.py`
**Status:** Implemented

Matches suppliers to discovered products and generates purchase orders.

### Workflow

For each underserved product (score >= 50, status = active):

1. **Enrich** — Fetches UPC/EAN from SP-API catalog data
2. **Supplier Suggestions** — Two modes:
   - **OpenAI mode:** GPT generates supplier names, costs, lead times (requires valid `OPENAI_API_KEY`)
   - **Rule-based mode:** Estimates costs using `CATEGORY_COGS_ESTIMATES` from config. Always runs as a baseline even when OpenAI is available.
3. **Create Supplier** — Gets or creates `Supplier` record by name
4. **Profitability Analysis** — Uses `utils/profitability.py`:
   - Amazon fees (referral + FBA by category/weight)
   - Net profit, margin, ROI calculation
   - Threshold check: margin >= 25%, ROI >= 100%, lead time <= 30d, reliability >= 70
5. **Save Pairing** — Creates/updates `ProductSupplier` record
6. **Select Preferred** — Highest margin supplier passing all thresholds
7. **Initialize Inventory** — Creates `Inventory` record with reorder point and safety stock based on estimated daily sales
8. **Generate POs** — For products with `needs_reorder=True` and a preferred supplier, creates `PurchaseOrder` if no active PO exists. Skipped in `DRY_RUN` mode.

### Key Classes

- `SourcingEngine` — main engine

```bash
uv run python src/phases/phase_3_sourcing.py
```

---

## Phase 4: Dynamic Repricing

**File:** `src/phases/phase_4_repricing.py`
**Status:** Stub (not implemented)

### Planned Functionality

- Monitor competitor pricing via Keepa and SP-API
- Algorithmic repricing with Buy Box optimization
- Price bounds: min price from `calculate_min_price()`, max from market tolerance
- Integration options: Eva.guru, BQool, or custom rules engine
- Configuration: `TARGET_BUY_BOX_WIN_RATE`, `PRICE_ADJUSTMENT_FREQUENCY`, `PRICE_ADJUSTMENT_AMOUNT`

### Existing Support

- `utils/profitability.py` has `calculate_min_price()` ready
- `amazon_sp_api.py` has `update_price()`, `get_product_pricing()`, `get_my_price()`
- Config has pricing constants and fee tables

---

## Phase 5: Inventory Forecasting

**File:** `src/phases/phase_5_forecasting.py`
**Status:** Stub (not implemented)

### Planned Functionality

- Pull historical sales data from SP-API
- Time-series forecasting (Prophet, XGBoost, ARIMA — all in dependencies)
- Reorder point = lead time demand + safety stock
- Auto-trigger POs when stock < reorder point
- Seasonality adjustment

### Existing Support

- `Inventory` model has `forecasted_stock_30d`, `forecasted_stock_60d`, `reorder_point`, `safety_stock`
- Phase 3 already initializes inventory records with basic reorder parameters
- Dependencies: `prophet`, `xgboost`, `statsmodels`, `scikit-learn` all installed
