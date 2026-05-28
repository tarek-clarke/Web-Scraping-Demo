#!/usr/bin/env python3
"""
Merge all raw semantic drift results from results/raw/ into a single JSON file.

Recursively walks results/raw/, loads each run JSON, adds metadata fields,
and writes all entries to combined_results.json sorted by hardware and run_id.

Uses only standard library: os, json, re, glob
"""

import json
import os
import re
import glob


VRAM_SPECS = {
    "AMD Radeon 7900XT": 20,
    "Apple M4": 16,
    "NVIDIA GH200": 141,
    "NVIDIA B200 SXM6": 192,
    "NVIDIA B300 SXM6": 262,
    "NVIDIA H100 SXM": 80,
    "NVIDIA H200 SXM5": 141,
    "NVIDIA RTX 5090": 32,
    "NVIDIA RTX 6000 Workstation": 96,
}


def normalize_hardware_name(name: str) -> str:
    return re.sub(r'[_\s]+', '', name).lower()


def match_vram_spec(hardware_name: str):
    """
    Match a hardware folder name to the closest key in VRAM_SPECS.
    Matching is case-insensitive and ignores underscores/spaces.
    Returns the matched VRAM value or None.
    """
    normalized_name = normalize_hardware_name(hardware_name)
    best_key = None
    best_score = -1

    for spec_name, vram_gb in VRAM_SPECS.items():
        normalized_spec = normalize_hardware_name(spec_name)
        if normalized_name == normalized_spec:
            return vram_gb

        if normalized_spec in normalized_name or normalized_name in normalized_spec:
            score = min(len(normalized_spec), len(normalized_name))
            if score > best_score:
                best_key = spec_name
                best_score = score

    if best_key is not None:
        return VRAM_SPECS[best_key]

    return None


def extract_vram_gb(hardware_name: str) -> str:
    """
    Extract VRAM in GB from hardware name if it contains a number followed by "GB".
    Returns empty string for Apple M4 and GH200.
    
    Example: "AMD_Radeon_RX_7900_XT_20GB" → "20"
    """
    if hardware_name in ['Apple_M4_16GB', 'GH200']:
        return ""
    
    # Look for pattern like "20GB" or "80GB"
    match = re.search(r'(\d+)GB', hardware_name)
    if match:
        return match.group(1)
    return ""


def infer_hardware_name_and_vram(hardware_name: str):
    """
    Determine the output hardware name and VRAM value.

    Priority:
    1) VRAM_SPECS match on hardware folder name
    2) VRAM inferred from hardware folder name
    3) Unknown => empty string

    If VRAM is known and not already present in the hardware name,
    append it as _<vram>GB.
    """
    vram_value = match_vram_spec(hardware_name)
    if vram_value is None:
        inferred = extract_vram_gb(hardware_name)
        vram_value = int(inferred) if inferred else None

    output_name = hardware_name
    if vram_value is not None and not re.search(r'\d+GB', hardware_name):
        output_name = f"{hardware_name}_{vram_value}GB"

    return output_name, (vram_value if vram_value is not None else "")


def merge_raw_results(raw_dir='results/raw', output_file='combined_results.json'):
    """
    Merge all run JSONs from raw_dir into a single output file.
    
    Process:
    - Walk results/raw/<hardware>/ directories
    - Load each *.json file (skip system_info.json, hardware_info.json)
    - Add metadata fields to each entry
    - Sort by hardware name, then run_id
    - Write to combined_results.json
    """
    if not os.path.isdir(raw_dir):
        print(f"Error: {raw_dir} does not exist")
        return
    
    all_entries = []
    total_files = 0
    valid_entries = 0
    
    # Walk through hardware folders
    for hardware_folder in sorted(os.listdir(raw_dir)):
        hardware_path = os.path.join(raw_dir, hardware_folder)
        
        if not os.path.isdir(hardware_path):
            continue
        
        hardware_name = hardware_folder
        print(f"Processing hardware: {hardware_name}")
        
        # Get metadata for this hardware
        output_hardware_name, vram_gb = infer_hardware_name_and_vram(hardware_name)
        cpu_model, ram_gb = "", ""
        
        # Process all *.json run files in this hardware folder
        run_files = sorted(glob.glob(os.path.join(hardware_path, '*.json')))
        
        for run_file in run_files:
            filename = os.path.basename(run_file)
            
            # Skip system_info.json and hardware_info.json
            if filename in ['system_info.json', 'hardware_info.json']:
                continue
            
            total_files += 1
            
            try:
                with open(run_file, 'r') as f:
                    run_data = json.load(f)
                
                # Get run_id from filename without extension
                run_id = os.path.splitext(filename)[0]
                
                # Create entry with metadata fields
                entry = {
                    'hardware': output_hardware_name,
                    'source_file': os.path.join(hardware_folder, filename),
                    'run_id': run_id,
                    'vram_gb': vram_gb,
                    'cpu_model': cpu_model,
                    'ram_gb': ram_gb,
                }
                
                # Merge in all fields from run_data
                entry.update(run_data)
                
                all_entries.append(entry)
                valid_entries += 1
            
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load {hardware_name}/{filename}: {e}")
    
    # Sort by hardware name, then by run_id
    all_entries.sort(key=lambda x: (x['hardware'], x['run_id']))
    
    # Write combined results
    with open(output_file, 'w') as f:
        json.dump(all_entries, f, indent=2)
    
    print(f"\nMerge complete:")
    print(f"  Total files processed: {total_files}")
    print(f"  Valid entries written: {valid_entries}")
    print(f"  Output file: {os.path.abspath(output_file)}")


if __name__ == '__main__':
    merge_raw_results()
