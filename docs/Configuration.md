# Configuration

All settings are managed via environment variables loaded from `.env` using Pydantic Settings (`src/config.py`).

## Setup

```bash
cp .env.example .env
# Edit .env with your credentials
```

## Required Credentials

| Variable | Description | Source |
|---|---|---|
| `AMAZON_CLIENT_ID` | SP-API client ID | [Seller Central](https://sellercentral.amazon.com/) → Apps & Services → Develop Apps |
| `AMAZON_CLIENT_SECRET` | SP-API client secret | Same as above |
| `AMAZON_REFRESH_TOKEN` | SP-API refresh token | Generated during app authorization |
| `AMAZON_SELLER_ID` | Your seller ID | Seller Central → Account Info |
| `KEEPA_API_KEY` | Keepa API key | [keepa.com/#!api](https://keepa.com/#!api) |

## Optional Credentials

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | None | Enhances Phase 3 supplier suggestions. Falls back to rule-based estimation if absent. |
| `EVA_GURU_API_KEY` | None | Eva.guru repricing integration (reserved for future use) |
| `BQOOL_API_KEY` | None | BQool repricing integration (reserved for future use) |

## Database

| Variable | Default | Description |
|---|---|---|
| `DATABASE_TYPE` | `sqlite` | `sqlite` or `postgresql` |
| `DATABASE_URL` | `sqlite:///./replens_automation.db` | Full connection string |

## Amazon Settings

| Variable | Default | Description |
|---|---|---|
| `AMAZON_REGION` | `NA` | `NA` (North America), `EU`, `FE` (Far East) |
| `AMAZON_RATE_LIMIT` | `5` | Max API requests per second |

## Keepa Settings

| Variable | Default | Description |
|---|---|---|
| `KEEPA_DOMAIN` | `1` | 1=US, 2=GB, 3=DE, 4=FR, 5=JP, 6=CA |
| `KEEPA_RATE_LIMIT` | `10` | Max requests per second |

## Discovery (Phase 2)

| Variable | Default | Description |
|---|---|---|
| `DISCOVERY_CATEGORIES` | `2619525011,3760911,1055398` | Comma-separated Amazon category node IDs (Grocery, Health, Home & Kitchen) |
| `DISCOVERY_PRICE_MIN` | `1000` | Min buy box price in cents (Keepa format) = $10.00 |
| `DISCOVERY_PRICE_MAX` | `10000` | Max buy box price in cents = $100.00 |
| `DISCOVERY_SALES_RANK_MAX` | `100000` | Maximum sales rank to include |
| `DISCOVERY_SELLER_COUNT_MAX` | `15` | Maximum number of new sellers |
| `DISCOVERY_MAX_PRODUCTS` | `200` | Max total products to analyze per run |
| `DISCOVERY_COGS_RATIO` | `0.30` | Default estimated COGS as fraction of price |

## Profitability Thresholds

| Variable | Default | Description |
|---|---|---|
| `MIN_PROFIT_MARGIN` | `0.25` | Minimum profit margin (25%) |
| `MIN_ROI` | `1.0` | Minimum ROI (100%) |
| `MIN_SALES_VELOCITY` | `10` | Minimum units sold per month |

## Pricing

| Variable | Default | Description |
|---|---|---|
| `TARGET_BUY_BOX_WIN_RATE` | `0.90` | Target Buy Box ownership (90%) |
| `PRICE_ADJUSTMENT_FREQUENCY` | `hourly` | How often to reprice |
| `PRICE_ADJUSTMENT_AMOUNT` | `0.01` | Undercut amount ($0.01) |

## Inventory

| Variable | Default | Description |
|---|---|---|
| `INVENTORY_TURNOVER_TARGET` | `4` | Target turnover per month |
| `SAFETY_STOCK_DAYS` | `7` | Days of safety stock to maintain |
| `REORDER_POINT_MULTIPLIER` | `1.5` | Multiplier for reorder point calculation |

## Forecasting

| Variable | Default | Description |
|---|---|---|
| `FORECAST_DAYS_AHEAD` | `30` | Forecast horizon in days |
| `SEASONALITY_ADJUSTMENT` | `true` | Enable seasonality adjustment |
| `PROMOTION_IMPACT_FACTOR` | `1.5` | Sales multiplier during promotions |

## Notifications

| Variable | Default | Description |
|---|---|---|
| `SMTP_SERVER` | `smtp.gmail.com` | SMTP server |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USERNAME` | None | Email username |
| `SMTP_PASSWORD` | None | Email app password |
| `ALERT_EMAIL_TO` | None | Alert recipient email |
| `SLACK_WEBHOOK_URL` | None | Slack webhook for alerts |

## System

| Variable | Default | Description |
|---|---|---|
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `LOG_FILE` | `logs/replens_automation.log` | Log file path |
| `API_TIMEOUT` | `30` | API request timeout in seconds |
| `API_RETRIES` | `3` | Number of retries for failed requests |
| `API_BACKOFF_FACTOR` | `2.0` | Exponential backoff multiplier |
| `CACHE_ENABLED` | `true` | Enable API response caching |
| `CACHE_TTL` | `3600` | Cache time-to-live in seconds |
| `DEBUG_MODE` | `false` | Enable debug logging |
| `TEST_MODE` | `false` | Use test data instead of live APIs |
| `DRY_RUN` | `false` | Simulate operations without changes |

## SP-API Required Roles

The Amazon SP-API app needs these roles enabled in Seller Central:

| Role | Used By |
|---|---|
| Product Listing | Phase 3 (catalog enrichment) |
| Product Pricing | Phase 4 (competitor pricing) |
| Product Fees | Phase 2 (fee estimation) |
| Fulfillment By Amazon Inventory | Phase 1 (connection test) |
| Orders | Phase 5 (sales data) |
| Feeds | Phase 4 (price updates) |

After adding roles, re-authorize the app and update `AMAZON_REFRESH_TOKEN`.
