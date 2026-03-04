"""
Tests for src/database.py

Covers:
- DatabaseOperations.add_product / get_product / get_underserved_products
- DatabaseOperations.add_supplier / get_supplier
- DatabaseOperations.create_purchase_order
- DatabaseOperations.record_performance
- ORM model relationships and defaults
- Constraint violations (duplicate ASIN, unique supplier name)

Uses SQLite in-memory database via fixtures in conftest.py.
"""

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database import (
    Base,
    Product,
    Supplier,
    ProductSupplier,
    Inventory,
    PurchaseOrder,
    Performance,
    DatabaseOperations,
)


# ============================================================================
# Fixtures (local to this test module, using conftest db_session as well)
# ============================================================================
@pytest.fixture
def db_ops():
    """Return the DatabaseOperations class (it only has static methods)."""
    return DatabaseOperations


@pytest.fixture
def product_in_db(db_session, db_ops, sample_product_data):
    """Insert a sample product and return it."""
    return db_ops.add_product(db_session, **sample_product_data)


@pytest.fixture
def supplier_in_db(db_session, db_ops, sample_supplier_data):
    """Insert a sample supplier and return it."""
    return db_ops.add_supplier(db_session, **sample_supplier_data)


# ============================================================================
# Product CRUD Tests
# ============================================================================
class TestProductCrud:
    """Tests for product creation and retrieval."""

    def test_add_product(self, db_session, db_ops, sample_product_data):
        product = db_ops.add_product(db_session, **sample_product_data)
        assert product.asin == "B0ABCD1234"
        assert product.title == "Test Product Widget"
        assert product.category == "Home"

    def test_add_product_with_defaults(self, db_session, db_ops):
        """Minimal product creation with only required fields."""
        product = db_ops.add_product(
            db_session, asin="B0MINIMAL1", title="Minimal Product", category="Toys"
        )
        assert product.asin == "B0MINIMAL1"
        assert product.status == "active"
        assert product.is_underserved is False
        assert product.opportunity_score == 0.0
        assert product.num_sellers == 0
        assert product.estimated_monthly_sales == 0

    def test_get_product_exists(self, db_session, db_ops, product_in_db):
        found = db_ops.get_product(db_session, "B0ABCD1234")
        assert found is not None
        assert found.asin == "B0ABCD1234"
        assert found.title == "Test Product Widget"

    def test_get_product_not_found(self, db_session, db_ops):
        found = db_ops.get_product(db_session, "B0NOTEXIST")
        assert found is None

    def test_add_product_with_price(self, db_session, db_ops):
        product = db_ops.add_product(
            db_session,
            asin="B0PRICED01",
            title="Priced Product",
            category="Electronics",
            current_price=Decimal("49.99"),
        )
        assert product.current_price == Decimal("49.99")

    def test_add_product_with_opportunity_score(self, db_session, db_ops):
        product = db_ops.add_product(
            db_session,
            asin="B0SCORED01",
            title="Scored Product",
            category="Home",
            opportunity_score=85.0,
            is_underserved=True,
        )
        assert product.opportunity_score == 85.0
        assert product.is_underserved is True

    def test_product_timestamps(self, db_session, db_ops):
        """Products should have created_at and last_updated timestamps."""
        product = db_ops.add_product(
            db_session, asin="B0TIMED001", title="Timed Product", category="Home"
        )
        assert product.created_at is not None
        assert isinstance(product.created_at, datetime)

    def test_duplicate_asin_raises_error(self, db_session, db_ops, product_in_db):
        """Adding a product with duplicate ASIN should raise IntegrityError."""
        with pytest.raises(IntegrityError):
            db_ops.add_product(
                db_session,
                asin="B0ABCD1234",  # Same ASIN as product_in_db
                title="Duplicate Product",
                category="Home",
            )

    def test_add_multiple_products(self, db_session, db_ops):
        """Can add multiple products with different ASINs."""
        db_ops.add_product(db_session, asin="B0MULTI001", title="Product 1", category="Home")
        db_ops.add_product(db_session, asin="B0MULTI002", title="Product 2", category="Toys")
        db_ops.add_product(db_session, asin="B0MULTI003", title="Product 3", category="Electronics")

        p1 = db_ops.get_product(db_session, "B0MULTI001")
        p2 = db_ops.get_product(db_session, "B0MULTI002")
        p3 = db_ops.get_product(db_session, "B0MULTI003")
        assert p1 is not None
        assert p2 is not None
        assert p3 is not None


# ============================================================================
# Underserved Products Tests
# ============================================================================
class TestUnderservedProducts:
    """Tests for get_underserved_products query."""

    def test_returns_underserved_active_products(self, db_session, db_ops):
        """Should only return products that are both underserved and active."""
        # Underserved + active (should be returned)
        db_ops.add_product(
            db_session,
            asin="B0UNDER001",
            title="Underserved 1",
            category="Home",
            is_underserved=True,
            opportunity_score=80.0,
            status="active",
        )
        # Not underserved (should NOT be returned)
        db_ops.add_product(
            db_session,
            asin="B0NORMAL01",
            title="Normal Product",
            category="Home",
            is_underserved=False,
            opportunity_score=30.0,
            status="active",
        )
        # Underserved but archived (should NOT be returned)
        db_ops.add_product(
            db_session,
            asin="B0ARCHIV01",
            title="Archived Product",
            category="Home",
            is_underserved=True,
            opportunity_score=70.0,
            status="archived",
        )

        results = db_ops.get_underserved_products(db_session)
        asins = [p.asin for p in results]
        assert "B0UNDER001" in asins
        assert "B0NORMAL01" not in asins
        assert "B0ARCHIV01" not in asins

    def test_ordered_by_opportunity_score_desc(self, db_session, db_ops):
        """Results should be ordered by opportunity_score descending."""
        db_ops.add_product(
            db_session,
            asin="B0LOW00001",
            title="Low Score",
            category="Home",
            is_underserved=True,
            opportunity_score=50.0,
        )
        db_ops.add_product(
            db_session,
            asin="B0HIGH0001",
            title="High Score",
            category="Home",
            is_underserved=True,
            opportunity_score=95.0,
        )
        db_ops.add_product(
            db_session,
            asin="B0MID00001",
            title="Mid Score",
            category="Home",
            is_underserved=True,
            opportunity_score=70.0,
        )

        results = db_ops.get_underserved_products(db_session)
        scores = [p.opportunity_score for p in results]
        assert scores == sorted(scores, reverse=True)

    def test_respects_limit(self, db_session, db_ops):
        """Should limit results to the specified count."""
        for i in range(10):
            db_ops.add_product(
                db_session,
                asin=f"B0LIMIT0{i:02d}",
                title=f"Product {i}",
                category="Home",
                is_underserved=True,
                opportunity_score=float(50 + i),
            )

        results = db_ops.get_underserved_products(db_session, limit=5)
        assert len(results) == 5

    def test_empty_when_none_underserved(self, db_session, db_ops):
        """Should return empty list when no underserved products exist."""
        db_ops.add_product(
            db_session,
            asin="B0NOTUND01",
            title="Not Underserved",
            category="Home",
            is_underserved=False,
        )
        results = db_ops.get_underserved_products(db_session)
        assert results == []

    def test_default_limit_is_50(self, db_session, db_ops):
        """Default limit should be 50."""
        for i in range(60):
            db_ops.add_product(
                db_session,
                asin=f"B0DLIM{i:04d}",
                title=f"Product {i}",
                category="Home",
                is_underserved=True,
                opportunity_score=float(i),
            )
        results = db_ops.get_underserved_products(db_session)
        assert len(results) == 50


# ============================================================================
# Supplier CRUD Tests
# ============================================================================
class TestSupplierCrud:
    """Tests for supplier creation and retrieval."""

    def test_add_supplier(self, db_session, db_ops, sample_supplier_data):
        supplier = db_ops.add_supplier(db_session, **sample_supplier_data)
        assert supplier.name == "Test Supplier Inc."
        assert supplier.supplier_id is not None
        assert supplier.reliability_score == 85.0
        assert supplier.lead_time_days == 7

    def test_add_supplier_minimal(self, db_session, db_ops):
        """Supplier with only name should use defaults."""
        supplier = db_ops.add_supplier(db_session, name="Minimal Supplier")
        assert supplier.name == "Minimal Supplier"
        assert supplier.status == "active"
        assert supplier.min_order_qty == 1
        assert supplier.lead_time_days == 7
        assert supplier.reliability_score == 0.0
        assert supplier.total_orders == 0

    def test_get_supplier_exists(self, db_session, db_ops, supplier_in_db):
        found = db_ops.get_supplier(db_session, supplier_in_db.supplier_id)
        assert found is not None
        assert found.name == "Test Supplier Inc."

    def test_get_supplier_not_found(self, db_session, db_ops):
        found = db_ops.get_supplier(db_session, 99999)
        assert found is None

    def test_supplier_auto_increment_id(self, db_session, db_ops):
        """Supplier IDs should auto-increment."""
        s1 = db_ops.add_supplier(db_session, name="Supplier Alpha")
        s2 = db_ops.add_supplier(db_session, name="Supplier Beta")
        assert s2.supplier_id > s1.supplier_id

    def test_duplicate_supplier_name_raises_error(self, db_session, db_ops, supplier_in_db):
        """Supplier name has a unique constraint."""
        with pytest.raises(IntegrityError):
            db_ops.add_supplier(db_session, name="Test Supplier Inc.")

    def test_supplier_timestamps(self, db_session, db_ops):
        supplier = db_ops.add_supplier(db_session, name="Timed Supplier")
        assert supplier.created_at is not None


# ============================================================================
# Purchase Order Tests
# ============================================================================
class TestPurchaseOrderCrud:
    """Tests for purchase order creation."""

    def test_create_purchase_order(self, db_session, db_ops, product_in_db, supplier_in_db):
        po = db_ops.create_purchase_order(
            session=db_session,
            po_id="PO-B0ABCD1234-1-20240101120000",
            asin=product_in_db.asin,
            supplier_id=supplier_in_db.supplier_id,
            quantity=50,
            unit_cost=Decimal("10.00"),
        )
        assert po.po_id == "PO-B0ABCD1234-1-20240101120000"
        assert po.quantity == 50
        assert po.unit_cost == Decimal("10.00")
        assert po.total_cost == Decimal("500.00")  # 50 * 10.00
        assert po.status == "pending"

    def test_purchase_order_total_cost_calculated(self, db_session, db_ops, product_in_db, supplier_in_db):
        """Total cost should be quantity * unit_cost."""
        po = db_ops.create_purchase_order(
            session=db_session,
            po_id="PO-TEST-CALC",
            asin=product_in_db.asin,
            supplier_id=supplier_in_db.supplier_id,
            quantity=25,
            unit_cost=Decimal("12.50"),
        )
        assert po.total_cost == Decimal("312.50")

    def test_duplicate_po_id_raises_error(self, db_session, db_ops, product_in_db, supplier_in_db):
        """PO IDs are primary keys and must be unique."""
        db_ops.create_purchase_order(
            session=db_session,
            po_id="PO-DUPLICATE",
            asin=product_in_db.asin,
            supplier_id=supplier_in_db.supplier_id,
            quantity=10,
            unit_cost=Decimal("5.00"),
        )
        with pytest.raises(IntegrityError):
            db_ops.create_purchase_order(
                session=db_session,
                po_id="PO-DUPLICATE",
                asin=product_in_db.asin,
                supplier_id=supplier_in_db.supplier_id,
                quantity=20,
                unit_cost=Decimal("5.00"),
            )

    def test_purchase_order_default_status(self, db_session, db_ops, product_in_db, supplier_in_db):
        po = db_ops.create_purchase_order(
            session=db_session,
            po_id="PO-STATUS-TEST",
            asin=product_in_db.asin,
            supplier_id=supplier_in_db.supplier_id,
            quantity=10,
            unit_cost=Decimal("5.00"),
        )
        assert po.status == "pending"

    def test_purchase_order_timestamps(self, db_session, db_ops, product_in_db, supplier_in_db):
        po = db_ops.create_purchase_order(
            session=db_session,
            po_id="PO-TIMESTAMPS",
            asin=product_in_db.asin,
            supplier_id=supplier_in_db.supplier_id,
            quantity=10,
            unit_cost=Decimal("5.00"),
        )
        assert po.created_at is not None
        assert po.order_date is not None


# ============================================================================
# Performance Recording Tests
# ============================================================================
class TestPerformanceRecording:
    """Tests for recording daily performance metrics."""

    def test_record_performance(self, db_session, db_ops, product_in_db):
        perf = db_ops.record_performance(
            session=db_session,
            asin=product_in_db.asin,
            units_sold=10,
            revenue=Decimal("299.90"),
            cost_of_goods=Decimal("100.00"),
            amazon_fees=Decimal("45.00"),
            buy_box_owned=True,
        )
        assert perf.asin == product_in_db.asin
        assert perf.units_sold == 10
        assert perf.revenue == Decimal("299.90")
        assert perf.net_profit == Decimal("154.90")  # 299.90 - 100.00 - 45.00
        assert perf.buy_box_owned is True

    def test_performance_net_profit_calculation(self, db_session, db_ops, product_in_db):
        """net_profit = revenue - cost_of_goods - amazon_fees."""
        perf = db_ops.record_performance(
            session=db_session,
            asin=product_in_db.asin,
            units_sold=5,
            revenue=Decimal("100.00"),
            cost_of_goods=Decimal("30.00"),
            amazon_fees=Decimal("15.00"),
        )
        assert perf.net_profit == Decimal("55.00")

    def test_performance_default_buy_box(self, db_session, db_ops, product_in_db):
        """Default buy_box_owned should be False."""
        perf = db_ops.record_performance(
            session=db_session,
            asin=product_in_db.asin,
            units_sold=1,
            revenue=Decimal("10.00"),
            cost_of_goods=Decimal("3.00"),
            amazon_fees=Decimal("1.50"),
        )
        assert perf.buy_box_owned is False

    def test_multiple_performance_records(self, db_session, db_ops, product_in_db):
        """Can create multiple performance records for the same product."""
        perf1 = db_ops.record_performance(
            session=db_session,
            asin=product_in_db.asin,
            units_sold=5,
            revenue=Decimal("50.00"),
            cost_of_goods=Decimal("15.00"),
            amazon_fees=Decimal("7.50"),
        )
        perf2 = db_ops.record_performance(
            session=db_session,
            asin=product_in_db.asin,
            units_sold=8,
            revenue=Decimal("80.00"),
            cost_of_goods=Decimal("24.00"),
            amazon_fees=Decimal("12.00"),
        )
        assert perf1.id != perf2.id


# ============================================================================
# ORM Model Tests
# ============================================================================
class TestOrmModels:
    """Tests for ORM model structure and relationships."""

    def test_product_table_name(self):
        assert Product.__tablename__ == "products"

    def test_supplier_table_name(self):
        assert Supplier.__tablename__ == "suppliers"

    def test_purchase_order_table_name(self):
        assert PurchaseOrder.__tablename__ == "purchase_orders"

    def test_inventory_table_name(self):
        assert Inventory.__tablename__ == "inventory"

    def test_performance_table_name(self):
        assert Performance.__tablename__ == "performance"

    def test_product_supplier_table_name(self):
        assert ProductSupplier.__tablename__ == "product_suppliers"

    def test_product_has_relationship_to_suppliers(self):
        """Product model should have a 'suppliers' relationship."""
        assert hasattr(Product, "suppliers")

    def test_product_has_relationship_to_inventory(self):
        assert hasattr(Product, "inventory")

    def test_product_has_relationship_to_purchase_orders(self):
        assert hasattr(Product, "purchase_orders")

    def test_product_has_relationship_to_performance(self):
        assert hasattr(Product, "performance")

    def test_supplier_has_relationship_to_product_suppliers(self):
        assert hasattr(Supplier, "product_suppliers")

    def test_supplier_has_relationship_to_purchase_orders(self):
        assert hasattr(Supplier, "purchase_orders")


# ============================================================================
# Product-Supplier Junction Tests
# ============================================================================
class TestProductSupplierJunction:
    """Tests for the product-supplier junction table."""

    def test_link_product_to_supplier(self, db_session, product_in_db, supplier_in_db):
        """Can create a product-supplier relationship with pricing."""
        ps = ProductSupplier(
            asin=product_in_db.asin,
            supplier_id=supplier_in_db.supplier_id,
            supplier_cost=Decimal("8.00"),
            shipping_cost=Decimal("2.00"),
            total_cost=Decimal("10.00"),
            estimated_profit=Decimal("12.00"),
            profit_margin=0.40,
            roi=1.20,
            is_preferred=True,
        )
        db_session.add(ps)
        db_session.commit()

        assert ps.id is not None
        assert ps.asin == product_in_db.asin
        assert ps.supplier_id == supplier_in_db.supplier_id
        assert ps.is_preferred is True

    def test_get_product_suppliers(self, db_session, db_ops, product_in_db, supplier_in_db):
        """get_product_suppliers should return suppliers sorted by profit_margin desc."""
        # Add a second supplier
        s2 = db_ops.add_supplier(db_session, name="Second Supplier")

        ps1 = ProductSupplier(
            asin=product_in_db.asin,
            supplier_id=supplier_in_db.supplier_id,
            supplier_cost=Decimal("10.00"),
            total_cost=Decimal("10.00"),
            estimated_profit=Decimal("5.00"),
            profit_margin=0.20,
            roi=0.50,
        )
        ps2 = ProductSupplier(
            asin=product_in_db.asin,
            supplier_id=s2.supplier_id,
            supplier_cost=Decimal("7.00"),
            total_cost=Decimal("7.00"),
            estimated_profit=Decimal("10.00"),
            profit_margin=0.45,
            roi=1.40,
        )
        db_session.add_all([ps1, ps2])
        db_session.commit()

        results = db_ops.get_product_suppliers(db_session, product_in_db.asin)
        assert len(results) == 2
        # Should be ordered by profit_margin descending
        assert results[0].profit_margin >= results[1].profit_margin


# ============================================================================
# Inventory Tests
# ============================================================================
class TestInventory:
    """Tests for inventory model."""

    def test_create_inventory(self, db_session, product_in_db):
        inv = Inventory(
            asin=product_in_db.asin,
            current_stock=100,
            reserved=10,
            available=90,
            reorder_point=20,
            safety_stock=10,
            needs_reorder=False,
        )
        db_session.add(inv)
        db_session.commit()

        assert inv.asin == product_in_db.asin
        assert inv.current_stock == 100
        assert inv.available == 90
        assert inv.needs_reorder is False

    def test_inventory_defaults(self, db_session, product_in_db):
        inv = Inventory(asin=product_in_db.asin)
        db_session.add(inv)
        db_session.commit()

        assert inv.current_stock == 0
        assert inv.reserved == 0
        assert inv.available == 0
        assert inv.reorder_point == 0
        assert inv.safety_stock == 0
        assert inv.needs_reorder is False
        assert inv.days_of_supply == 0

    def test_inventory_product_relationship(self, db_session, product_in_db):
        """Inventory should link back to its product."""
        inv = Inventory(asin=product_in_db.asin, current_stock=50)
        db_session.add(inv)
        db_session.commit()

        assert inv.product.asin == product_in_db.asin
        assert inv.product.title == product_in_db.title
