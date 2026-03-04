# Development Guide

## Setup

```bash
# Clone and install
git clone <repo>
cd replens_automation_system
uv sync --group dev    # Includes test/lint dependencies

# Configure
cp .env.example .env   # Edit with your API credentials
```

## Running

```bash
# Full pipeline
uv run python src/main.py

# Individual phases
uv run python src/phases/phase_1_setup.py
uv run python src/phases/phase_2_discovery.py
uv run python src/phases/phase_3_sourcing.py

# Dashboard
uv run streamlit run src/dashboard/app.py

# Config check
uv run python src/config.py
```

## Testing

```bash
uv run pytest                    # Run tests
uv run pytest --cov=src          # With coverage
uv run pytest -v                 # Verbose
```

**Note:** No tests are written yet. Test files should go in `tests/`.

## Linting

```bash
uv run black src/ tests/         # Format code
uv run isort src/ tests/         # Sort imports
uv run flake8 src/ tests/        # Lint
uv run mypy src/                 # Type check
```

## Project Conventions

- **Package manager:** `uv` (not pip)
- **Python version:** 3.12+ (set in `.python-version`)
- **Database:** SQLAlchemy ORM models in `src/models/`, engine/CRUD in `src/database.py`, domain services in `src/services/`
- **Config:** Pydantic Settings from `.env`, accessed via `settings` singleton
- **Logging:** `logging` module, output to file + console
- **API wrappers:** Singleton pattern via `get_*()` functions
- **Phases:** Independent modules, each with a `main()` function

## Database Operations

```bash
# Initialize/reset tables
uv run python src/database.py

# Quick DB inspection (SQLite)
sqlite3 replens_automation.db ".tables"
sqlite3 replens_automation.db "SELECT COUNT(*) FROM products;"
sqlite3 replens_automation.db "SELECT asin, opportunity_score, is_underserved FROM products ORDER BY opportunity_score DESC LIMIT 10;"
```

## Roadmap

### Not Yet Implemented

- [ ] Phase 4: Dynamic repricing engine
- [ ] Phase 5: Inventory forecasting with Prophet/XGBoost
- [ ] Dashboard: Streamlit app with charts and KPIs
- [ ] Scheduler: APScheduler-based job scheduling (`scheduler.py`)
- [ ] Test suite
- [ ] Docker deployment files
- [ ] Alembic database migrations
- [ ] Notification system (email/Slack alerts)

### Known Technical Debt

- `datetime.utcnow()` used in some modules (deprecated in Python 3.12, use `datetime.now(timezone.utc)`)
- `declarative_base()` in `src/models/base.py` (legacy, could migrate to `DeclarativeBase` class)
- Bare `except:` in `amazon_sp_api.py:260`
- `config.py` runs `Settings()` at import time — crashes without valid `.env`
- Duplicate `logging.basicConfig()` calls in phase modules (should use `utils/logger.py`)
