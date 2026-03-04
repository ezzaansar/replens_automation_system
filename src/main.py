"""
Main entry point for the Amazon Replens Automation System.

This script orchestrates the execution of all phases of the system.
"""

import logging
import sys

from src.utils.logger import setup_logging
from src.phases import phase_1_setup, phase_2_discovery, phase_3_sourcing, phase_4_repricing, phase_5_forecasting

setup_logging()
logger = logging.getLogger(__name__)

def main():
    """Run all phases of the Replens automation system."""
    logger.info("Starting Amazon Replens Automation System")

    # Phase 1: Foundation Setup
    logger.info("\n--- Running Phase 1: Foundation Setup ---")
    if not phase_1_setup.main():
        logger.error("Phase 1 failed. Aborting.")
        sys.exit(1)

    # Phase 2: Product Discovery
    logger.info("\n--- Running Phase 2: Product Discovery ---")
    if not phase_2_discovery.main():
        logger.error("Phase 2 failed. Aborting.")
        sys.exit(1)

    # Phase 3: Sourcing & Procurement
    logger.info("\n--- Running Phase 3: Sourcing & Procurement ---")
    phase_3_sourcing.main()

    # Phase 4: Dynamic Repricing
    logger.info("\n--- Running Phase 4: Dynamic Repricing ---")
    phase_4_repricing.main()

    # Phase 5: Inventory Forecasting
    logger.info("\n--- Running Phase 5: Inventory Forecasting ---")
    phase_5_forecasting.main()

    logger.info("\n✓ All phases completed successfully!")

if __name__ == "__main__":
    main()
