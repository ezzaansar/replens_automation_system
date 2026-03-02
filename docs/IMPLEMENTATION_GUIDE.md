# Amazon Replens Automation System - Implementation Guide

**Author:** Manus AI  
**Version:** 1.0  
**Date:** December 2025

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Phase 1: Foundation Setup](#phase-1-foundation-setup)
3. [Phase 2: Product Discovery Engine](#phase-2-product-discovery-engine)
4. [Phase 3: Supplier Matching](#phase-3-supplier-matching)
5. [Phase 4: Dynamic Repricing](#phase-4-dynamic-repricing)
6. [Phase 5: Inventory Forecasting](#phase-5-inventory-forecasting)
7. [Phase 6: Monitoring Dashboard](#phase-6-monitoring-dashboard)
8. [Deployment](#deployment)
9. [Operations & Maintenance](#operations--maintenance)

---

## Getting Started

### Prerequisites

- Python 3.11 or higher
- PostgreSQL 12+ (or SQLite for development)
- Amazon Selling Partner API credentials
- Keepa API subscription
- OpenAI API key (optional, for advanced features)
- Docker and Docker Compose (for containerized deployment)

### Initial Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd replens-automation
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

5. **Initialize database:**
   ```bash
   python src/phases/phase_1_setup.py
   ```

---

## Phase 1: Foundation Setup

### Objective

Establish the system foundation by initializing the database, testing API connections, and validating configuration.

### Implementation

The Phase 1 setup script (`src/phases/phase_1_setup.py`) performs the following:

1. **Database Initialization:** Creates all required tables and indexes.
2. **API Testing:** Validates connections to Amazon SP-API and Keepa API.
3. **Configuration Validation:** Ensures all required settings are configured.
4. **Logging Setup:** Initializes logging to file and console.

### Running Phase 1

```bash
python src/phases/phase_1_setup.py
```

### Expected Output

```
[INFO] Starting Phase 1: Foundation Setup
[INFO] [1/6] Setting up logging...
[INFO] ✓ Logging configured
[INFO] [2/6] Validating configuration...
[INFO] ✓ Configuration validation passed
[INFO] [3/6] Initializing database...
[INFO] ✓ Database initialized
[INFO] [4/6] Testing Amazon SP-API connection...
[INFO] ✓ Amazon SP-API connection successful
[INFO] [5/6] Testing Keepa API connection...
[INFO] ✓ Keepa API connection successful
[INFO] [6/6] Creating sample data...
[INFO] ✓ Sample data creation complete
[INFO] ✓ All systems operational
```

### Troubleshooting

**Database Connection Error:**
- Verify database credentials in `.env`
- Ensure PostgreSQL is running (if using PostgreSQL)
- Check database URL format

**API Authentication Error:**
- Verify API credentials in `.env`
- Ensure credentials have not expired
- Check API key permissions in respective dashboards

---

## Phase 2: Product Discovery Engine

### Objective

Identify high-potential replenishable products using machine learning and data analysis.

### Key Features

- **Automated Scanning:** Continuously monitors Amazon for underserved listings
- **ML Scoring:** Uses machine learning to rank opportunities
- **Profitability Analysis:** Estimates profit potential for each product
- **Real-time Updates:** Keeps product data current with historical tracking

### Implementation Details

The discovery engine (`src/phases/phase_2_discovery.py`) works as follows:

1. **Data Collection:** Fetches product data from Keepa API
2. **Feature Extraction:** Calculates key metrics:
   - Sales velocity (estimated units/month)
   - Price stability (coefficient of variation)
   - Competition level (number of sellers)
   - Sales rank trends

3. **Profitability Calculation:** Estimates profit margins using:
   - Estimated cost of goods (40% of selling price by default)
   - Amazon referral fees (15% by default)
   - FBA fulfillment fees (based on product size)

4. **ML Scoring:** Applies weighted scoring model:
   ```
   Score = 0.15 × price_stability
         + 0.20 × low_competition
         + 0.20 × good_sales_rank
         + 0.20 × sales_velocity
         + 0.15 × profit_margin
         + 0.10 × roi
   ```

5. **Database Storage:** Saves opportunities to the database for further analysis

### Running Phase 2

```bash
python src/phases/phase_2_discovery.py
```

### Customizing Product Discovery

Edit `src/config.py` to adjust thresholds:

```python
# Profitability Thresholds
MIN_PROFIT_MARGIN = 0.25  # 25% minimum
MIN_ROI = 1.0  # 100% minimum
MIN_SALES_VELOCITY = 10  # units/month

# Sales Rank Thresholds
SALES_RANK_THRESHOLDS = {
    "excellent": 10000,
    "good": 50000,
    "moderate": 100000,
}

# Seller Count Thresholds
SELLER_COUNT_THRESHOLDS = {
    "very_low": 2,
    "low": 5,
    "moderate": 10,
}
```

### Expected Output

```
[INFO] Starting Product Discovery Engine
[INFO] Found 45 opportunities
[INFO] ✓ Saved 45 opportunities to database

[INFO] Top 5 Opportunities:
  1. Premium Reusable Food Storage Bags (Score: 87.3)
  2. Stainless Steel Water Bottle (Score: 84.1)
  3. Wireless Charging Pad (Score: 81.5)
  4. Yoga Mat with Carrying Strap (Score: 79.2)
  5. Phone Screen Protector (Score: 76.8)
```

---

## Phase 3: Supplier Matching

### Objective

Automatically find reliable suppliers for identified products and calculate profitability.

### Key Features

- **Supplier Discovery:** Finds verified suppliers for each product
- **Cost Analysis:** Compares supplier pricing and terms
- **Profitability Filtering:** Only recommends suppliers meeting margin requirements
- **PO Generation:** Automatically creates purchase orders

### Implementation Details

The sourcing engine (`src/phases/phase_3_sourcing.py`) performs:

1. **UPC/EAN Extraction:** Gets product identifiers from Keepa/SP-API
2. **Supplier Search:** Uses multiple methods:
   - Seller Assistant API (if integrated)
   - Google Shopping API
   - Manual supplier database
   - Web scraping (ethical)

3. **Cost Calculation:** For each supplier:
   ```
   Total Cost = Supplier Cost + Shipping Cost
   Net Profit = Selling Price - Total Cost - Amazon Fees
   Profit Margin = Net Profit / Selling Price
   ROI = Net Profit / Total Cost
   ```

4. **Filtering:** Keeps only suppliers meeting criteria:
   - Profit margin > MIN_PROFIT_MARGIN
   - ROI > MIN_ROI
   - Lead time < 30 days
   - Reliability score > 0.7

5. **PO Generation:** Creates purchase orders for approved products

### Configuration

Edit supplier thresholds in `.env`:

```
MIN_PROFIT_MARGIN=0.25
MIN_ROI=1.0
SUPPLIER_LEAD_TIME_MAX=30
SUPPLIER_RELIABILITY_MIN=0.7
```

---

## Phase 4: Dynamic Repricing

### Objective

Optimize prices to maximize profitability while maintaining Buy Box ownership.

### Key Features

- **Real-time Monitoring:** Tracks competitor pricing
- **Algorithmic Repricing:** Automatically adjusts prices
- **Margin Protection:** Ensures minimum profit margins
- **Buy Box Optimization:** Targets >90% Buy Box win rate

### Implementation Details

The repricing engine (`src/phases/phase_4_repricing.py`) uses:

1. **Competitor Monitoring:** Fetches competitor prices from:
   - Keepa API (Buy Box history)
   - Amazon SP-API (offers report)

2. **Repricing Strategy:** Three options:
   - **Eva.guru Integration:** Uses their AI-driven repricing
   - **BQool Integration:** Uses their repricing engine
   - **Custom Rules:** Uses predefined rules engine

3. **Custom Rules Example:**
   ```python
   if competitor_price > min_price and competitor_price < max_price:
       new_price = competitor_price - 0.01  # Undercut by $0.01
   elif competitor_price < min_price:
       new_price = min_price  # Don't go below minimum
   else:
       new_price = max_price  # Don't exceed maximum
   ```

4. **Price Bounds:**
   ```
   Min Price = Cost + Fees + Target Margin
   Max Price = Market Tolerance (e.g., 1.5 × Cost)
   ```

### Configuration

```
TARGET_BUY_BOX_WIN_RATE=0.90
PRICE_ADJUSTMENT_FREQUENCY=hourly
PRICE_ADJUSTMENT_AMOUNT=0.01
```

---

## Phase 5: Inventory Forecasting

### Objective

Predict future demand and automate inventory replenishment.

### Key Features

- **Demand Forecasting:** Uses time-series models (Prophet, XGBoost)
- **Reorder Automation:** Automatically triggers purchase orders
- **Safety Stock:** Maintains buffer for unexpected demand
- **Seasonality Adjustment:** Accounts for seasonal trends

### Implementation Details

The forecasting engine (`src/phases/phase_5_forecasting.py`) uses:

1. **Historical Data:** Pulls 90+ days of sales history from SP-API
2. **Feature Engineering:** Creates features:
   - Day of week
   - Seasonality (monthly, yearly)
   - Price changes
   - Promotion periods
   - External factors (weather, events)

3. **Model Selection:**
   - **Prophet:** For products with clear seasonality
   - **XGBoost:** For complex patterns
   - **ARIMA:** For stationary data

4. **Reorder Logic:**
   ```
   Reorder Point = Lead Time Demand + Safety Stock
   Lead Time Demand = Avg Daily Sales × Lead Time Days
   Safety Stock = Std Dev × Service Level Factor
   ```

5. **Automated Replenishment:**
   - Monitors inventory daily
   - Triggers PO when stock < reorder point
   - Calculates optimal order quantity

### Configuration

```
FORECAST_DAYS_AHEAD=30
SAFETY_STOCK_DAYS=7
REORDER_POINT_MULTIPLIER=1.5
SEASONALITY_ADJUSTMENT=true
```

---

## Phase 6: Monitoring Dashboard

### Objective

Provide real-time visibility into system performance and business metrics.

### Key Features

- **Real-time KPIs:** Revenue, profit, ROI, turnover, Buy Box %
- **Product Management:** View and manage tracked products
- **Alerts:** Notifications for critical events
- **Charts & Analytics:** Visual performance tracking

### Running the Dashboard

```bash
streamlit run src/dashboard/app.py
```

The dashboard will be available at `http://localhost:8501`

### Dashboard Sections

1. **Overview:** Key metrics and KPIs
2. **Products:** List of tracked products with performance
3. **Opportunities:** New products awaiting review
4. **Inventory:** Stock levels and reorder alerts
5. **Performance:** Charts and trend analysis
6. **Settings:** Configuration and preferences

---

## Deployment

### Docker Deployment

1. **Build the image:**
   ```bash
   docker build -t replens-automation .
   ```

2. **Run with Docker Compose:**
   ```bash
   docker-compose up -d
   ```

3. **Access services:**
   - Dashboard: http://localhost:8501
   - API: http://localhost:8000

### Production Deployment

For production, use:

- **Web Server:** Gunicorn or Uvicorn
- **Database:** PostgreSQL 12+
- **Cache:** Redis
- **Task Queue:** Celery
- **Reverse Proxy:** Nginx
- **Container Orchestration:** Kubernetes or Docker Swarm

See `DEPLOYMENT.md` for detailed production setup.

---

## Operations & Maintenance

### Monitoring

Monitor system health with:

```bash
# Check logs
tail -f logs/replens_automation.log

# Monitor database
psql -U postgres -d replens_db -c "SELECT COUNT(*) FROM products;"

# Check scheduler status
ps aux | grep scheduler
```

### Backup & Recovery

```bash
# Backup database
pg_dump replens_db > backup_$(date +%Y%m%d).sql

# Restore database
psql replens_db < backup_20231215.sql
```

### Performance Optimization

1. **Database Indexes:** Already optimized in schema
2. **API Caching:** Enabled by default (3600s TTL)
3. **Rate Limiting:** Configured per API
4. **Batch Processing:** Processes products in batches

### Troubleshooting

**High API Costs:**
- Reduce discovery frequency
- Increase cache TTL
- Use batch queries

**Slow Dashboard:**
- Add database indexes
- Reduce data retention period
- Use materialized views

**Missed Replenishments:**
- Check forecast accuracy
- Adjust safety stock levels
- Verify supplier lead times

---

## Next Steps

1. Complete Phase 1 setup
2. Run Phase 2 to identify opportunities
3. Review opportunities in dashboard
4. Configure Phase 3 for your suppliers
5. Set up repricing rules in Phase 4
6. Monitor forecasts in Phase 5
7. Optimize based on dashboard metrics

For support and questions, refer to the documentation or contact the development team.
