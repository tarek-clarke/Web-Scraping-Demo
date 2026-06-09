#!/usr/bin/env python3
"""
Production entry point for Resilient RAP Framework.

This script demonstrates the core ingestion and schema reconciliation workflow
for reproducible analytical pipelines with autonomous schema drift resolution.

Usage:
    python main.py --adapter openf1 --session 9158 --driver 1
"""

import argparse
import sys
import json
from pathlib import Path
import logging

# Configure logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for RAP framework."""
    parser = argparse.ArgumentParser(
        description='Resilient RAP Framework - Production Pipeline Runner'
    )
    parser.add_argument(
        '--adapter',
        choices=['openf1'],
        default='openf1',
        help='Data adapter to use'
    )
    parser.add_argument(
        '--session',
        type=int,
        help='Session ID (for F1 adapter)'
    )
    parser.add_argument(
        '--driver',
        type=int,
        help='Driver ID (for F1 adapter)'
    )
    args = parser.parse_args()

    try:
        if not args.session or not args.driver:
            parser.error('--session and --driver required for F1 adapter')
        from adapters.sports.ingestion_sports import SportsIngestor
        logger.info(f'Starting F1 ingestion: session={args.session}, driver={args.driver}')
        ingestor = SportsIngestor(
            source_name='OpenF1',
            session_id=args.session,
            driver_id=args.driver
        )
        # Execute pipeline
        logger.info('Connecting to data source...')
        ingestor.connect()
        logger.info('Running ingestion pipeline...')
        df = ingestor.run()
        logger.info(f'Pipeline completed. Output shape: {df.shape}')
        logger.info(f'Sample output:\n{df.head()}')
        return 0
    except Exception as e:
        logger.error(f'Pipeline error: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()