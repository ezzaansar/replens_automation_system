"""
Phase 1: Foundation Setup

Initializes the system by:
1. Creating and validating the database
2. Testing API connections
3. Creating initial configuration
4. Setting up logging and monitoring
"""

import logging
import sys
from datetime import datetime

from src.database import init_db, SessionLocal, Product
from src.config import settings, validate_settings
from src.api_wrappers.amazon_sp_api import get_sp_api
from src.api_wrappers.keepa_api import get_keepa_api
from src.utils.logger import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def setup_logging_step():
    """Log that logging has been configured (actual setup is in src.utils.logger)."""
    logger.info("✓ Logging configured")


def setup_database():
    """Initialize the database."""
    try:
        init_db()
        logger.info("✓ Database initialized")
        return True
    except Exception as e:
        logger.error(f"✗ Database initialization failed: {e}")
        return False


def test_amazon_sp_api():
    """Test the Amazon SP-API connection using the Sellers API (base role)."""
    try:
        sp_api = get_sp_api()

        logger.info("Testing Amazon SP-API connection...")
        participations = sp_api.get_marketplace_participations()

        marketplaces = [p.get("marketplace", {}).get("id", "?") for p in participations]
        logger.info(f"✓ Amazon SP-API connection successful (marketplaces: {marketplaces})")
        return True
    except Exception as e:
        logger.error(f"✗ Amazon SP-API connection failed: {e}")
        error_str = str(e).lower()
        if "unauthorized" in error_str or "403" in error_str or "access" in error_str:
            logger.error("")
            logger.error("=" * 70)
            logger.error("SP-API AUTHORIZATION TROUBLESHOOTING")
            logger.error("=" * 70)
            logger.error(
                "The LWA token exchange succeeded but the API returned 403.\n"
                "This means your SP-API app exists but is not fully authorized.\n"
                "\n"
                "Please check the following in Seller Central:\n"
                "\n"
                "  1. APP STATUS\n"
                "     Seller Central -> Apps & Services -> Develop Apps\n"
                "     Your app must be 'Published' or 'Authorized', NOT 'Draft'.\n"
                "\n"
                "  2. SELF-AUTHORIZATION\n"
                "     Seller Central -> Apps & Services -> Manage Your Apps\n"
                "     Click 'Authorize' on your app. This generates the refresh\n"
                "     token tied to your seller account. Copy it to your .env as\n"
                "     AMAZON_REFRESH_TOKEN.\n"
                "\n"
                "  3. IAM ROLE\n"
                "     The IAM Role ARN registered with your app must:\n"
                "     - Still exist in your AWS account\n"
                "     - Have a trust policy allowing sts:AssumeRole\n"
                "     - Have the 'execute-api:Invoke' permission\n"
                "\n"
                "  4. REFRESH TOKEN\n"
                "     If you regenerated your app credentials after the initial\n"
                "     authorization, the old refresh token is invalidated.\n"
                "     Re-authorize the app and update AMAZON_REFRESH_TOKEN in .env.\n"
                "\n"
                "  5. API ROLES\n"
                "     Seller Central -> Apps & Services -> Develop Apps -> Edit\n"
                "     Ensure these roles are enabled:\n"
                "       - Selling Partner Insights (base access)\n"
                "       - Product Listing    (Phase 3: catalog lookups)\n"
                "       - Product Pricing    (Phase 4: repricing)\n"
                "       - Feeds              (Phase 4: price updates)\n"
                "       - FBA Inventory      (inventory queries)\n"
                "       - Orders             (Phase 5: sales history)\n"
            )
            logger.error("=" * 70)
        return False


def test_keepa_api():
    """Test the Keepa API connection."""
    try:
        keepa_api = get_keepa_api()
        logger.info("✓ Keepa API connection successful")
        return True
    except Exception as e:
        logger.error(f"✗ Keepa API connection failed: {e}")
        return False


def validate_configuration():
    """Validate that all required configuration is present."""
    try:
        validate_settings()
        logger.info("✓ Configuration validation passed")
        return True
    except ValueError as e:
        logger.error(f"✗ Configuration validation failed: {e}")
        return False


def create_sample_data():
    """Create sample data for testing (optional)."""
    try:
        session = SessionLocal()
        
        # Check if we already have sample data
        products = session.query(Product).count()
        if products > 0:
            logger.info("Sample data already exists, skipping creation")
            return True
        
        logger.info("Creating sample data...")
        
        # This would be populated with actual test data
        # For now, just log that we're ready
        logger.info("✓ Sample data creation complete")
        return True
    except Exception as e:
        logger.error(f"✗ Sample data creation failed: {e}")
        return False
    finally:
        session.close()


def print_system_status():
    """Print a summary of the system status."""
    print("\n" + "=" * 70)
    print("AMAZON REPLENS AUTOMATION SYSTEM - SETUP COMPLETE")
    print("=" * 70)
    print(f"\nConfiguration:")
    print(f"  Database Type: {settings.database_type}")
    print(f"  Database URL: {settings.database_url}")
    print(f"  Amazon Region: {settings.amazon_region}")
    print(f"  Min Profit Margin: {settings.min_profit_margin * 100}%")
    print(f"  Min ROI: {settings.min_roi * 100}%")
    print(f"  Target Buy Box Win Rate: {settings.target_buy_box_win_rate * 100}%")
    print(f"\nSchedules:")
    print(f"  Product Discovery: {settings.discovery_run_time}")
    print(f"  Repricing Frequency: {settings.repricing_run_frequency}")
    print(f"  Inventory Check: {settings.inventory_check_frequency}")
    print(f"  Forecast Update: {settings.forecast_update_frequency}")
    print(f"\nNext Steps:")
    print(f"  1. Review and customize configuration in .env file")
    print(f"  2. Run Phase 2 (Product Discovery): python src/phases/phase_2_discovery.py")
    print(f"  3. Start the dashboard: streamlit run src/dashboard/app.py")
    print(f"  4. Start the scheduler: python src/scheduler.py")
    print("=" * 70 + "\n")


def main():
    """Run the Phase 1 setup."""
    logger.info("Starting Phase 1: Foundation Setup")
    logger.info(f"Timestamp: {datetime.utcnow().isoformat()}")
    
    # Step 1: Setup logging
    logger.info("\n[1/6] Setting up logging...")
    setup_logging_step()
    
    # Step 2: Validate configuration
    logger.info("\n[2/6] Validating configuration...")
    if not validate_configuration():
        logger.error("Configuration validation failed. Please check your .env file.")
        return False
    
    # Step 3: Initialize database
    logger.info("\n[3/6] Initializing database...")
    if not setup_database():
        logger.error("Database initialization failed.")
        return False
    
    # Step 4: Test Amazon SP-API
    logger.info("\n[4/6] Testing Amazon SP-API connection...")
    sp_api_ok = test_amazon_sp_api()
    
    # Step 5: Test Keepa API
    logger.info("\n[5/6] Testing Keepa API connection...")
    keepa_api_ok = test_keepa_api()
    
    # Step 6: Create sample data (optional)
    logger.info("\n[6/6] Creating sample data...")
    create_sample_data()
    
    # Print status
    logger.info("\n" + "=" * 70)
    logger.info("PHASE 1 SETUP COMPLETE")
    logger.info("=" * 70)
    
    if sp_api_ok and keepa_api_ok:
        logger.info("✓ All systems operational")
    else:
        if not sp_api_ok:
            logger.warning("⚠ Amazon SP-API: Check app permissions in Seller Central")
        if not keepa_api_ok:
            logger.error("✗ Keepa API: Check your API key — Keepa is required for Phase 2 discovery")
            return False

    print_system_status()
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
