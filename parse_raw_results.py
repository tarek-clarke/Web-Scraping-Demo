#!/usr/bin/env python3
"""
IEEE TKDE Empirical Evaluation Log Parser
==========================================

Senior Research Systems Engineer script for parsing individual raw JSON evaluation 
stream files and compiling a unified empirical log for journal submission.

This script implements a rigorous row-by-row mapping of:
  1. Chaos Source (strategy classification)
  2. Injected Chaos Type (exact drift_type value)
  3. Detected Chaos Type (which drift_types key == 1)
  4. Semantic Repair Pathway (fallback routing logic)
  5. Performance Metadata (latency, throughput, resilience)

Output: pristine_chaos_vs_repair_matrix.csv (flattened, unified DataFrame)

Author: Semantic Drift Research Group
Date: May 2026
"""

import json
import os
import sys
import logging
from pathlib import Path
from collections import defaultdict

import pandas as pd
import numpy as np


# ============================================================================
# Configuration & Logging
# ============================================================================

LOG_LEVEL = logging.INFO
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

RESULTS_RAW_DIR = Path('./results/raw')
OUTPUT_CSV = 'pristine_chaos_vs_repair_matrix.csv'

DRIFT_TYPE_KEYS = [
    'missing_keys',
    'extra_keys',
    'renamed_keys',
    'type_mismatch',
    'value_contradiction',
    'split_fields',
    'merged_fields',
    'nested_corruption'
]


# ============================================================================
# Core Logic: Row-by-Row Extraction & Mapping
# ============================================================================

def map_chaos_source(strategy):
    """
    Logic Constraint 1: Chaos Source Mapping
    
    Maps chaos_metadata.strategy to human-readable chaos source labels.
    
    Args:
        strategy (str): Value of chaos_metadata.strategy
        
    Returns:
        str: Labeled chaos source
    """
    strategy_map = {
        'gemma': 'Gemma Adversarial LLM',
        'json': 'Procedural Mutation (JSON Engine)',
        'schema': 'Procedural Mutation (Schema Engine)'
    }
    
    if strategy not in strategy_map:
        logger.warning(f"Unknown chaos strategy: {strategy}, using 'Unknown'")
        return f"Unknown ({strategy})"
    
    return strategy_map[strategy]


def extract_injected_chaos_type(chaos_metadata):
    """
    Logic Constraint 2: Injected Chaos Type
    
    Extracts the exact string value from chaos_metadata.drift_type.
    Normalizes missing/null/empty values to 'clean'.
    
    Args:
        chaos_metadata (dict): The chaos_metadata object from JSON
        
    Returns:
        str: drift_type value, or 'clean' if missing/null/empty
    """
    drift_type = chaos_metadata.get('drift_type')
    # Normalize missing, None, null, or empty strings to 'clean'
    if drift_type is None or drift_type == '' or str(drift_type).lower() == 'none':
        return 'clean'
    return str(drift_type)


def extract_detected_chaos_type(drift_types):
    """
    Logic Constraint 3: Detected Chaos Type
    
    Identifies which key in drift_types has an integer value of 1.
    Returns that key string as the Detected_Chaos_Type, or 'clean' if no detection.
    
    Args:
        drift_types (dict): The drift_types object from JSON
        
    Returns:
        str: Key where drift_types[key] == 1, or 'clean' if no match
    """
    if not isinstance(drift_types, dict):
        return 'clean'
    
    for key in DRIFT_TYPE_KEYS:
        value = drift_types.get(key, 0)
        # Handle both int and float representations of 1
        if value == 1 or (isinstance(value, (int, float)) and abs(value - 1.0) < 1e-6):
            return key
    
    return 'clean'


def map_semantic_repair_pathway(fallback_used, reconciliation_winner, averages):
    """
    Logic Constraint 4: Semantic Repair Pathway
    
    Maps the repair pathway based on fallback_used flag and sub-properties.
    
    Args:
        fallback_used (bool): Whether fallback was triggered
        reconciliation_winner (str): The selected reconciliation method
        averages (dict): The averages object containing latency fields
        
    Returns:
        str: Labeled repair pathway
    """
    if not fallback_used and reconciliation_winner == 'canonical':
        return 'Canonical Matcher Bypass (Serialization Only)'
    
    if fallback_used:
        # Check which reconciler latency is > 0 (in priority order)
        if isinstance(averages, dict):
            if averages.get('gemma_latency', 0) > 0:
                return 'Gemma-4 E4B LLM Reconciler'
            if averages.get('bert_latency', 0) > 0:
                return 'BERT Semantic Embedding (all-MiniLM)'
            if averages.get('regex_latency', 0) > 0:
                return 'Regex Structural Template Matcher'
            if averages.get('levenshtein_latency', 0) > 0:
                return 'Levenshtein String Distance Filter'
    
    # Fallback if no clear pathway identified
    return f'Fallback({reconciliation_winner})'


# ============================================================================
# JSON File Processing
# ============================================================================

def process_json_file(filepath):
    """
    Parse a single JSON file and extract all required fields.
    
    Implements graceful error handling for malformed or incomplete records.
    
    Args:
        filepath (Path): Absolute path to JSON file
        
    Returns:
        dict: Flattened record with all extracted fields, or None if parsing fails
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to parse {filepath}: {e}")
        return None
    
    try:
        # Extract chaos metadata
        chaos_metadata = data.get('chaos_metadata', {})
        strategy = chaos_metadata.get('strategy', 'Unknown')
        
        # Apply Logic Constraints
        chaos_source = map_chaos_source(strategy)
        injected_chaos_type = extract_injected_chaos_type(chaos_metadata)
        
        drift_types = data.get('drift_types', {})
        detected_chaos_type = extract_detected_chaos_type(drift_types)
        
        fallback_used = data.get('fallback_used', False)
        reconciliation_winner = data.get('reconciliation_winner', 'unknown')
        averages = data.get('averages', {})
        
        repair_pathway = map_semantic_repair_pathway(
            fallback_used,
            reconciliation_winner,
            averages
        )
        
        # Extract performance metadata
        record = {
            # Core Mapping Fields
            'Chaos_Source': chaos_source,
            'Injected_Chaos_Type': injected_chaos_type,
            'Detected_Chaos_Type': detected_chaos_type,
            'Semantic_Repair_Pathway': repair_pathway,
            
            # Performance Metadata
            'Hardware': data.get('hardware', 'Unknown'),
            'API_Name': data.get('api_name', 'Unknown'),
            'Chaos_Level': data.get('chaos_level', 'Unknown'),
            'P95_Latency_ms': data.get('p95_latency_ms', np.nan),
            'Throughput_pps': data.get('throughput_pps', np.nan),
            'Resilience_P': data.get('resilience_P', np.nan),
            
            # Additional Context (for completeness)
            'Run_Number': data.get('run_number', np.nan),
            'Detection_Rate': data.get('detection_rate', np.nan),
            'Repair_Rate': data.get('repair_rate', np.nan),
            'Recovery_Score': data.get('recovery_score', np.nan),
            'Drift_Detected': data.get('drift_detected', False),
            'Fallback_Used': fallback_used,
            'Reconciliation_Winner': reconciliation_winner,
            'Throughput_bytes_per_sec': data.get('throughput_bytes_per_sec', np.nan),
            'Total_Runtime_sec': data.get('total_runtime_sec', np.nan),
            'Packet_Profile': data.get('packet_profile', 'Unknown'),
            'Frequency_Profile': data.get('frequency_profile', 'Unknown'),
            'Packet_Size': data.get('packet_size', np.nan),
            'Concurrency': data.get('concurrency', np.nan),
            '_Label': data.get('_label', 'Unknown'),
        }
        
        return record
        
    except Exception as e:
        logger.error(f"Error extracting fields from {filepath}: {e}")
        return None


def collect_all_json_files(root_dir):
    """
    Recursively collect all JSON files from results/raw directory structure.
    
    Args:
        root_dir (Path): Root directory to scan
        
    Returns:
        list: List of Path objects for all JSON files
    """
    json_files = []
    for json_file in root_dir.rglob('*.json'):
        json_files.append(json_file)
    return sorted(json_files)


# ============================================================================
# Main Processing Pipeline
# ============================================================================

def main():
    """
    Execute the full empirical log compilation pipeline:
    1. Discover all JSON files in results/raw/
    2. Parse each file and extract fields
    3. Flatten into unified DataFrame
    4. Export as pristine_chaos_vs_repair_matrix.csv
    """
    
    logger.info("Starting IEEE TKDE Empirical Log Compilation")
    logger.info(f"Source directory: {RESULTS_RAW_DIR}")
    
    # Validate source directory
    if not RESULTS_RAW_DIR.exists():
        logger.error(f"Results directory not found: {RESULTS_RAW_DIR}")
        sys.exit(1)
    
    # Collect all JSON files
    json_files = collect_all_json_files(RESULTS_RAW_DIR)
    logger.info(f"Discovered {len(json_files)} JSON files")
    
    if len(json_files) == 0:
        logger.error("No JSON files found in results/raw/")
        sys.exit(1)
    
    # Process each file
    records = []
    errors = 0
    
    for idx, filepath in enumerate(json_files, 1):
        if idx % 500 == 0 or idx == len(json_files):
            logger.info(f"Processing: {idx}/{len(json_files)}")
        
        record = process_json_file(filepath)
        if record is not None:
            records.append(record)
        else:
            errors += 1
    
    logger.info(f"Successfully processed {len(records)} files ({errors} errors)")
    
    # Create DataFrame
    df = pd.DataFrame(records)
    
    # Log schema and summary statistics
    logger.info(f"DataFrame shape: {df.shape}")
    logger.info(f"Columns: {list(df.columns)}")
    logger.info("\n--- Column Data Types ---")
    for col, dtype in df.dtypes.items():
        logger.info(f"  {col}: {dtype}")
    
    logger.info("\n--- Sample Record (first row) ---")
    logger.info(df.iloc[0].to_string())
    
    logger.info("\n--- Value Distribution (Key Columns) ---")
    for col in ['Chaos_Source', 'Injected_Chaos_Type', 'Detected_Chaos_Type', 'Semantic_Repair_Pathway']:
        if col in df.columns:
            logger.info(f"{col} distribution:")
            for val, count in df[col].value_counts().items():
                logger.info(f"  {val}: {count}")
    
    # Export to CSV
    output_path = Path(OUTPUT_CSV)
    df.to_csv(output_path, index=False, encoding='utf-8')
    logger.info(f"\n✓ Exported {len(df)} rows to {output_path}")
    
    # Final statistics
    logger.info("\n--- Export Statistics ---")
    logger.info(f"Total rows: {len(df)}")
    logger.info(f"Total columns: {len(df.columns)}")
    logger.info(f"Memory usage: {df.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB")
    logger.info(f"Missing values: {df.isnull().sum().sum()}")
    
    return df


if __name__ == '__main__':
    main()
