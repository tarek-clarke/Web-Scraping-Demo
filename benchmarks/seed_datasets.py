#!/usr/bin/env python3
"""
Production-ready seeding orchestration script for the Resilient RAP Framework.
Downloads high-fidelity sample JSON payloads ("base packets") to complete the
10-domain telemetry test suite with idempotent checks and robust error degradation.
"""
import os
import sys
import json
import logging
import requests
from typing import Dict, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="[SeedTelemetry] %(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("seed_datasets")

# Target Directory layout: benchmarks/test_suite/
BASE_DIR = os.path.join("benchmarks", "test_suite")

# Define target endpoints for the 5 new domains
DOMAINS: Dict[str, Dict[str, str]] = {
    "06_hockey_nhl": {
        "url": "https://api-web.nhle.com/v1/gamecenter/2023020001/play-by-play",
        "description": "Spatial Sports (Hockey)"
    },
    "07_aviation_opensky": {
        "url": "https://opensky-network.org/api/states/all",
        "description": "Aviation Vector Logistics"
    },
    "08_football_uefa": {
        "url": "https://api.football-data.org/v4/competitions/CL/matches",
        "description": "Continental Football"
    },
    "09_industrial_iiot": {
        "url": "https://api.openaq.org/v2/measurements?limit=100",
        "description": "Industrial IoT Tracking"
    },
    "10_smartcity_transit": {
        "url": "https://api.tfl.gov.uk/Line/victoria/Arrivals",
        "description": "Smart City Transit"
    }
}

# Explicit Header block to bypass User-Agent blocking of public APIs
HEADERS = {
    "User-Agent": "Resilient-RAP-Framework-HPC-Benchmark/2.0.0",
    "Accept": "application/json"
}

def seed_domain(dir_name: str, config: Dict[str, str]) -> str:
    """Download base packet for a domain. Returns status: 'SUCCESS', 'SKIPPED', or 'FAILED'."""
    domain_dir = os.path.join(BASE_DIR, dir_name)
    os.makedirs(domain_dir, exist_ok=True)
    target_file = os.path.join(domain_dir, "base_packet.json")

    # Idempotent check
    if os.path.exists(target_file):
        logger.info(f"Skipping {config['description']}... base_packet.json already exists.")
        return "SKIPPED"

    logger.info(f"Seeding {config['description']} from {config['url']}...")
    try:
        response = requests.get(config['url'], headers=HEADERS, timeout=10)
        
        # Check HTTP response code
        if response.status_code != 200:
            logger.warning(f"Failed to fetch {config['description']}: HTTP {response.status_code}")
            sys.stderr.write(f"[WARNING] API Pull Failed: {config['description']} returned status code {response.status_code}\n")
            return "FAILED"

        # Verify response is valid JSON
        payload = response.json()
        
        # Write to disk
        with open(target_file, "w") as f:
            json.dump(payload, f, indent=2)
            
        logger.info(f"Successfully seeded {config['description']}.")
        return "SUCCESS"
        
    except requests.exceptions.Timeout:
        logger.warning(f"Connection timeout during query to {config['url']}")
        sys.stderr.write(f"[WARNING] Timeout Error seeding {config['description']}\n")
        return "FAILED"
    except json.JSONDecodeError:
        logger.warning(f"Received invalid or corrupted JSON payload from {config['url']}")
        sys.stderr.write(f"[WARNING] JSON Corruption Error seeding {config['description']}\n")
        return "FAILED"
    except Exception as e:
        logger.warning(f"Unexpected exception during query: {e}")
        sys.stderr.write(f"[WARNING] Telemetry seed error for {config['description']}: {e}\n")
        return "FAILED"

def main():
    logger.info("Initializing 10-Domain Telemetry Seeding Pipeline...")
    results = {}

    for dir_name, config in DOMAINS.items():
        status = seed_domain(dir_name, config)
        results[config["description"]] = status

    # Print final summary table
    print("\n" + "="*50)
    print(f"{'Domain / Telemetry Data Source':<30} | {'Status':<10}")
    print("="*50)
    for desc, status in results.items():
        print(f"{desc:<30} | {status:<10}")
    print("="*50 + "\n")

if __name__ == "__main__":
    main()
