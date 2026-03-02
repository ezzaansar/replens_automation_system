# Amazon Replens Automation System

**Enterprise-Grade Automated Amazon FBA Business Management Platform**

A production-ready Python system for automating the complete Amazon Replens workflow: product discovery, supplier sourcing, dynamic pricing, inventory management, and performance monitoring.

## Features

- **Automated Product Discovery:** ML-powered identification of underserved Amazon listings
- **Intelligent Supplier Matching:** Real-time supplier discovery with profitability analysis
- **Dynamic Repricing Engine:** AI-driven price optimization for Buy Box dominance
- **Demand Forecasting:** Predictive inventory management with automated replenishment
- **Real-Time Dashboard:** Comprehensive KPI monitoring with alerts
- **100% Automated:** Runs on schedule with manual override capabilities

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    AMAZON REPLENS AUTOMATION                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │  Product     │  │  Supplier    │  │  Dynamic     │           │
│  │  Discovery   │→ │  Matching    │→ │  Repricing   │           │
│  │  Engine      │  │  Engine      │  │  Engine      │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│         ↓                  ↓                  ↓                 │
│  ┌──────────────────────────────────────────────────┐           │
│  │       Inventory Forecasting & Replenishment      │           │
│  └──────────────────────────────────────────────────┘           │
│         ↓                                                       │
│  ┌──────────────────────────────────────────────────┐           │
│  │    Performance Monitoring & Analytics Dashboard  │           │
│  └──────────────────────────────────────────────────┘           │
│                                                                 │
│  ┌──────────────────────────────────────────────────┐           │
│  │         Database (PostgreSQL/SQLite)             │           │
│  │  Products | Suppliers | Inventory | POs | KPIs   │           │
│  └──────────────────────────────────────────────────┘           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL or SQLite
- Amazon SP-API credentials
- Keepa API key
- OpenAI API key (optional)

### Installation

```bash
# Clone repository
git clone <repo>
cd replens-automation

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API credentials
```

### Running the System

```bash
# Run all phases
python src/main.py

# Run specific phase
python src/phases/phase_2_discovery.py

# Start dashboard
streamlit run src/dashboard/app.py

# Schedule daily runs
python src/scheduler.py
```

## Project Structure

```
replens-automation/
├── src/
│   ├── __init__.py
│   ├── main.py                 # Main entry point
│   ├── config.py               # Configuration management
│   ├── database.py             # Database models and operations
│   ├── api_wrappers/           # API integrations
│   │   ├── amazon_sp_api.py
│   │   ├── keepa_api.py
│   │   └── openai_api.py
│   ├── phases/                 # Implementation phases
│   │   ├── phase_1_setup.py
│   │   ├── phase_2_discovery.py
│   │   ├── phase_3_sourcing.py
│   │   ├── phase_4_repricing.py
│   │   └── phase_5_forecasting.py
│   ├── models/                 # ML models
│   │   ├── discovery_model.py
│   │   └── forecast_model.py
│   ├── dashboard/              # Streamlit dashboard
│   │   └── app.py
│   ├── utils/                  # Utilities
│   │   ├── logger.py
│   │   ├── profitability.py
│   │   └── validators.py
│   └── scheduler.py            # Task scheduling
├── config/
│   ├── .env.example
│   └── database_schema.sql
├── data/
│   ├── models/                 # Trained ML models
│   └── cache/                  # API response cache
├── logs/
│   └── system.log
├── tests/
│   ├── test_api_wrappers.py
│   ├── test_models.py
│   └── test_database.py
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

## Key Metrics

**Target Performance:**
- Operational time reduction: **80%+**
- Inventory turnover: **>4x/month**
- Buy Box win rate: **>90%**
- Profit margin: **>25%**
- ROI: **>100%**

## Documentation

- [Technical Specification](docs/TECHNICAL_SPEC.md)
- [Database Schema](docs/DATABASE_SCHEMA.md)
- [API Integration Guide](docs/API_INTEGRATION.md)
- [Deployment Guide](docs/DEPLOYMENT.md)
- [Operations Manual](docs/OPERATIONS.md)

## Support

For issues, questions, or contributions, please refer to the documentation or contact the development team.

## License

Proprietary - For personal use only.
