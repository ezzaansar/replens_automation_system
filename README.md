# Amazon Replens Automation System

Automated Amazon FBA replenishment platform: product discovery, supplier sourcing, dynamic pricing, inventory management, and performance monitoring.

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Amazon SP-API credentials
- Keepa API key
- OpenAI API key (optional)

### Installation

```bash
git clone <repo>
cd replens_automation_system

# Install dependencies
uv sync

# Configure environment
cp .env.example .env
# Edit .env with your API credentials
```

### Running

```bash
# Run full pipeline (all phases)
uv run python src/main.py

# Run individual phases
uv run python src/phases/phase_1_setup.py
uv run python src/phases/phase_2_discovery.py
uv run python src/phases/phase_3_sourcing.py

# Start dashboard (stub)
uv run streamlit run src/dashboard/app.py
```

## Project Structure

```
replens_automation_system/
├── src/
│   ├── main.py                  # Main entry point - runs all phases
│   ├── config.py                # Configuration (Pydantic Settings)
│   ├── database.py              # SQLAlchemy ORM models & operations
│   ├── api_wrappers/
│   │   ├── amazon_sp_api.py     # Amazon SP-API wrapper
│   │   └── keepa_api.py         # Keepa API wrapper
│   ├── phases/
│   │   ├── phase_1_setup.py     # Foundation setup
│   │   ├── phase_2_discovery.py # Product discovery engine
│   │   ├── phase_3_sourcing.py  # Supplier matching & procurement
│   │   ├── phase_4_repricing.py # Dynamic repricing (stub)
│   │   └── phase_5_forecasting.py # Inventory forecasting (stub)
│   ├── models/
│   │   └── discovery_model.py   # Opportunity scoring model
│   ├── dashboard/
│   │   └── app.py               # Streamlit dashboard (stub)
│   └── utils/
│       ├── logger.py            # Centralized logging
│       ├── profitability.py     # Fee estimation & profit calculations
│       └── validators.py        # Input validation & PO ID generation
├── tests/                       # Test suite
├── docs/                        # Documentation
├── logs/                        # Log files
├── .env.example                 # Environment variable template
├── pyproject.toml               # Project config & dependencies
└── CLAUDE.md                    # AI assistant context file
```

## Pipeline

| Phase | Status | Description |
|---|---|---|
| Phase 1: Setup | Implemented | DB init, config validation, API connection tests |
| Phase 2: Discovery | Implemented | Keepa-powered product discovery with ML scoring |
| Phase 3: Sourcing | Implemented | Supplier matching, profitability analysis, PO generation |
| Phase 4: Repricing | Planned | Dynamic price optimization for Buy Box |
| Phase 5: Forecasting | Planned | Demand prediction & inventory replenishment |

## Documentation

- [Architecture](docs/Architecture.md) - System design and data flow
- [Database Schema](docs/Database.md) - Table definitions and relationships
- [Configuration](docs/Configuration.md) - All environment variables
- [Phase Details](docs/Phases.md) - Implementation details per phase
- [Development](docs/Development.md) - Dev setup, testing, roadmap

## License

Proprietary - For personal use only.
