"""
Shared pytest fixtures for the Replens Automation System test suite.

Provides:
- In-memory SQLite database sessions for database tests
- Mocked settings for tests that import from src.config
"""

import pytest
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database import Base, Product, Supplier, ProductSupplier, Inventory, PurchaseOrder, Performance


@pytest.fixture
def db_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """Create a fresh database session for each test."""
    Session = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def sample_product_data():
    """Return sample product data for testing."""
    return {
        "asin": "B0ABCD1234",
        "title": "Test Product Widget",
        "category": "Home",
        "current_price": Decimal("29.99"),
        "sales_rank": 5000,
        "estimated_monthly_sales": 50,
        "num_sellers": 3,
        "num_fba_sellers": 2,
        "is_underserved": True,
        "opportunity_score": 75.0,
        "status": "active",
    }


@pytest.fixture
def sample_supplier_data():
    """Return sample supplier data for testing."""
    return {
        "name": "Test Supplier Inc.",
        "website": "https://testsupplier.com",
        "contact_email": "contact@testsupplier.com",
        "min_order_qty": 10,
        "lead_time_days": 7,
        "reliability_score": 85.0,
    }
