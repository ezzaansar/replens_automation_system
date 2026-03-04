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
**Status:** Implemented

Monitors competitor prices, adjusts our prices to win the Buy Box, and enforces a cost-based price floor to protect margins.

### Workflow

For each eligible product (active, has inventory with `current_stock > 0`, has a preferred supplier):

1. **Calculate Price Floor** — `calculate_min_price(preferred_supplier.total_cost, category)` from `utils/profitability.py`. Ensures we never sell below minimum margin threshold.
2. **Fetch Competitor Pricing** — `sp_api.get_product_pricing(asin)` for Buy Box price + `sp_api.get_my_price(asin)` for our current offer.
3. **Decide Action:**
   - We own the Buy Box → no change
   - Our price is at or below Buy Box → no change (seller-metrics issue; undercutting won't help)
   - Our price > Buy Box → target = `buy_box_price - price_adjustment_amount` ($0.01)
   - Clamp target to price floor (never go below)
   - Validate with `validate_price()`
4. **Apply** — In `dry_run` mode: log only. Otherwise: `sp_api.update_price(sku, new_price)` and update `product.current_price` in DB. Uses `product.sku` if set, falls back to ASIN.
5. **Record** — Writes pricing snapshot to Performance table via `record_repricing_action()` regardless of action taken.

### Error Handling

- SP-API 403 on first pricing call → disables all pricing API calls for the rest of the run (avoids hammering a forbidden endpoint)
- Each product wrapped in try/except with `session.rollback()` — one product's failure doesn't abort the run

### Key Classes / Functions

- `RepricingEngine` — main engine (context manager)
  - `calculate_price_floor(product)` → `Decimal` or `None`
  - `get_competitor_pricing(asin)` → `dict` or `None`
  - `determine_new_price(product, competitor_data, price_floor)` → `Decimal` or `None`
  - `reprice_product(product)` → result dict
  - `run(limit=100)` → summary stats dict
- `get_repriceable_products()` — service query (active + inventory + preferred supplier)
- `record_repricing_action()` — writes pricing snapshot to Performance table

### Configuration

| Variable | Default | Description |
|---|---|---|
| `PRICE_ADJUSTMENT_AMOUNT` | `0.01` | Amount to undercut Buy Box ($0.01) |
| `TARGET_BUY_BOX_WIN_RATE` | `0.90` | Target Buy Box ownership (90%) |
| `DRY_RUN` | `false` | Log repricing decisions without applying |

```bash
uv run python src/phases/phase_4_repricing.py
```

---

## Phase 5: Inventory Forecasting

**File:** `src/phases/phase_5_forecasting.py`
**Status:** Implemented

Predicts future demand per product using a tiered approach, updates inventory forecast fields, and auto-generates purchase orders when reorder points are breached.

### Tiered Forecasting

| Data Points | Tier | Method | Rationale |
|---|---|---|---|
| < 14 | 1 | Keepa `estimated_monthly_sales / 30` | Always available, no history needed |
| 14–59 | 2 | Exponential smoothing (statsmodels `SimpleExpSmoothing`, α=0.3) | Works with limited data, captures recent trends |
| 60+ | 3 | Prophet (weekly seasonality, conservative changepoints) | Full seasonality detection with enough data |

Each tier falls back to the one below on failure. Daily demand clamped to min 0.01 to avoid division by zero.

### Workflow

For each eligible product (active, has inventory record, has preferred supplier):

1. **Gather History** — Queries Performance table for `(date, units_sold)` where `units_sold > 0`. Optionally supplements with SP-API order data (gracefully handles 403).
2. **Select Tier** — Based on number of historical data points.
3. **Forecast Daily Demand** — Runs the selected tier's algorithm. Falls back to lower tiers on failure.
4. **Update Inventory** — Computes and writes:
   - `forecasted_stock_30d` = current_stock - ceil(daily_demand × 30)
   - `forecasted_stock_60d` = current_stock - ceil(daily_demand × 60)
   - `days_of_supply` = current_stock / daily_demand
   - `safety_stock` = ceil(daily_demand × safety_stock_days)
   - `reorder_point` = ceil(daily_demand × safety_stock_days × reorder_point_multiplier)
   - `needs_reorder` = (current_stock <= reorder_point)
5. **Auto-PO** — When `needs_reorder=True` and no active PO exists (`status in [pending, confirmed, shipped]`): generates a PO via `create_purchase_order()`. Quantity = `max(supplier.min_order_qty, ceil(daily_demand × forecast_days_ahead))`. Skipped in `dry_run` mode.

### Error Handling

- SP-API 403 on orders → disables order fetching for the rest of the run
- Prophet import failure → falls back to Tier 2 (exponential smoothing)
- Each product wrapped in try/except with `session.rollback()`

### Key Classes / Functions

- `ForecastingEngine` — main engine (context manager)
  - `forecast_daily_demand(product, history)` → `(float, int)` (demand, tier)
  - `update_inventory_forecast(product, daily_demand)` → dict
  - `forecast_product(product)` → result dict
  - `run(limit=100)` → summary stats dict
- `get_forecastable_products()` — service query (active + inventory + preferred supplier, any stock level)
- `get_sales_history()` — Performance table query for sales data

### Configuration

| Variable | Default | Description |
|---|---|---|
| `FORECAST_DAYS_AHEAD` | `30` | Days of demand to order when generating auto-PO |
| `SAFETY_STOCK_DAYS` | `7` | Buffer days for safety stock calculation |
| `REORDER_POINT_MULTIPLIER` | `1.5` | Multiplier on safety stock for reorder trigger |
| `DRY_RUN` | `false` | Log PO decisions without creating them |

```bash
uv run python src/phases/phase_5_forecasting.py
```
