#!/usr/bin/env python3
"""
Normalize raw semantic drift results in results/raw/ and merge them into
clean JSON/CSV outputs.

Behavior:
- Normalizes hardware folder names and run filenames to include authoritative VRAM
- Injects vram_gb into JSON/CSV rows under results/raw/
- Writes combined_results.json/csv and per-hardware JSON/csv outputs
- Exports a compact chaos-vs-repair matrix CSV for downstream analysis

Uses only standard library modules.
"""

import csv
import glob
import json
import os
import re


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


def build_name_with_vram(name: str, vram_gb):
    if vram_gb in (None, ""):
        return name

    suffix = f"{vram_gb}GB"
    if re.search(r'\d+GB', name):
        updated_name = re.sub(r'\d+GB(?!.*\d+GB)', suffix, name)
        return updated_name

    return f"{name}_{suffix}"


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

    output_name = build_name_with_vram(hardware_name, vram_value)

    return output_name, (vram_value if vram_value is not None else "")


def normalize_folder_name(hardware_folder: str):
    """Normalize a hardware folder name and infer VRAM from the name/table."""
    return infer_hardware_name_and_vram(hardware_folder)


def normalize_filename(run_filename: str, vram_gb):
    """Append or replace the VRAM suffix in a run filename stem."""
    stem, ext = os.path.splitext(run_filename)
    normalized_stem = build_name_with_vram(stem, vram_gb)
    return normalized_stem + ext


def safe_filename(name: str) -> str:
    return re.sub(r'[^A-Za-z0-9._-]+', '_', name).strip('_')


def write_json_file(path: str, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def safe_csv_value(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False)
    return value


def collect_fieldnames(entries):
    preferred = ['hardware', 'source_file', 'run_id', 'vram_gb']
    fieldnames = list(preferred)
    seen = set(fieldnames)

    for entry in entries:
        for key in entry.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    return fieldnames


def write_csv_file(path: str, entries):
    fieldnames = collect_fieldnames(entries)
    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for entry in entries:
            writer.writerow({key: safe_csv_value(entry.get(key, "")) for key in fieldnames})


def write_normalized_json(path: str, payload, hardware_name: str, vram_gb):
    if isinstance(payload, dict):
        payload['hardware'] = hardware_name
        payload['vram_gb'] = vram_gb if vram_gb is not None else ""
    elif isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                item['hardware'] = hardware_name
                item['vram_gb'] = vram_gb if vram_gb is not None else ""

    with open(path, 'w') as f:
        json.dump(payload, f, indent=2)


def write_normalized_csv(path: str, rows, hardware_name: str, vram_gb):
    if not rows:
        return

    fieldnames = list(rows[0].keys())
    if 'hardware' not in fieldnames:
        fieldnames.insert(0, 'hardware')
    if 'vram_gb' not in fieldnames:
        fieldnames.append('vram_gb')

    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            normalized_row = dict(row)
            normalized_row['hardware'] = hardware_name
            normalized_row['vram_gb'] = vram_gb if vram_gb is not None else ""
            writer.writerow(normalized_row)


def rename_if_needed(source_path: str, target_path: str, summary: list, kind: str):
    if source_path == target_path:
        return source_path

    if os.path.exists(target_path):
        summary.append(f"{kind}: skipped rename because target exists -> {target_path}")
        return source_path

    os.rename(source_path, target_path)
    summary.append(f"{kind}: {source_path} -> {target_path}")
    return target_path


def normalize_raw_results(raw_dir='results/raw'):
    """Normalize hardware folders and raw JSON/CSV files in place."""
    summary = []

    if not os.path.isdir(raw_dir):
        print(f"Error: {raw_dir} does not exist")
        return summary

    for hardware_folder in sorted(os.listdir(raw_dir)):
        source_folder_path = os.path.join(raw_dir, hardware_folder)
        if not os.path.isdir(source_folder_path):
            continue

        normalized_hardware_name, vram_gb = normalize_folder_name(hardware_folder)
        target_folder_path = os.path.join(raw_dir, normalized_hardware_name)
        current_folder_path = rename_if_needed(source_folder_path, target_folder_path, summary, 'folder')

        if vram_gb not in (None, ""):
            summary.append(f"VRAM: {normalized_hardware_name} -> {vram_gb}GB")
        else:
            summary.append(f"VRAM: {hardware_folder} -> unknown")

        for filename in sorted(os.listdir(current_folder_path)):
            if filename in {'system_info.json', 'hardware_info.json'}:
                continue

            source_file_path = os.path.join(current_folder_path, filename)
            if not os.path.isfile(source_file_path):
                continue

            ext = os.path.splitext(filename)[1].lower()
            if ext not in {'.json', '.csv'}:
                continue

            normalized_filename = normalize_filename(filename, vram_gb)
            target_file_path = os.path.join(current_folder_path, normalized_filename)
            current_file_path = rename_if_needed(source_file_path, target_file_path, summary, 'file')

            if ext == '.json':
                try:
                    with open(current_file_path, 'r') as f:
                        payload = json.load(f)
                except (json.JSONDecodeError, OSError) as exc:
                    summary.append(f"json: skipped {current_file_path} ({exc})")
                    continue

                write_normalized_json(current_file_path, payload, normalized_hardware_name, vram_gb)
                summary.append(f"json: updated hardware/vram_gb in {current_file_path}")

            elif ext == '.csv':
                try:
                    with open(current_file_path, 'r', newline='') as f:
                        reader = csv.DictReader(f)
                        rows = list(reader)
                        fieldnames = reader.fieldnames or []
                except OSError as exc:
                    summary.append(f"csv: skipped {current_file_path} ({exc})")
                    continue

                if rows:
                    write_normalized_csv(current_file_path, rows, normalized_hardware_name, vram_gb)
                    summary.append(f"csv: updated hardware/vram_gb in {current_file_path}")
                else:
                    summary.append(f"csv: skipped empty {current_file_path}")

    return summary


def get_nested_dict(entry, key):
    value = entry.get(key)
    return value if isinstance(value, dict) else {}


def get_chaos_source_label(entry):
    chaos_metadata = get_nested_dict(entry, 'chaos_metadata')
    strategy = str(chaos_metadata.get('strategy', '') or '').strip().lower()
    if strategy == 'gemma':
        return 'Gemma Adversarial LLM'
    if strategy in {'json', 'schema'}:
        return 'Procedural Algorithmic Engine'
    return strategy or ''


def get_chaos_type_injected(entry):
    chaos_metadata = get_nested_dict(entry, 'chaos_metadata')
    return chaos_metadata.get('drift_type', '') or ''


def get_chaos_detected(entry):
    drift_types = get_nested_dict(entry, 'drift_types')
    detected = []
    for key, value in drift_types.items():
        if value in (1, True, '1', 'true', 'True'):
            detected.append(key)
    return '; '.join(sorted(detected))


def get_semantic_repair_type(entry):
    fallback_used = bool(entry.get('fallback_used'))
    reconciliation_winner = str(entry.get('reconciliation_winner', '') or '').strip().lower()

    if not fallback_used and reconciliation_winner == 'canonical':
        return 'Canonical Matcher Bypass'

    if fallback_used:
        averages = get_nested_dict(entry, 'averages')
        latency_map = {
            'bert_latency': 'BERT Semantic Embedding',
            'gemma_latency': 'Gemma-4 E4B LLM Reconciler',
            'levenshtein_latency': 'Levenshtein Distance',
            'regex_latency': 'Regex Template',
        }

        active = []
        for metric, label in latency_map.items():
            value = averages.get(metric)
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                numeric_value = 0.0
            if numeric_value > 0:
                active.append((numeric_value, label))

        if active:
            active.sort(key=lambda item: item[0], reverse=True)
            return active[0][1]

        if reconciliation_winner:
            return reconciliation_winner.replace('_', ' ').title()

    return ''


def build_chaos_vs_repair_rows(entries):
    rows = []
    for entry in entries:
        rows.append({
            'hardware': entry.get('hardware', ''),
            'api_name': entry.get('api_name', ''),
            'chaos_source': get_chaos_source_label(entry),
            'chaos_type_injected': get_chaos_type_injected(entry),
            'chaos_detected': get_chaos_detected(entry),
            'semantic_repair_type': get_semantic_repair_type(entry),
            'p95_latency_ms': entry.get('p95_latency_ms', ''),
            'throughput_pps': entry.get('throughput_pps', ''),
            'resilience_P': entry.get('resilience_P', ''),
        })

    rows.sort(key=lambda row: (
        str(row.get('hardware', '')),
        str(row.get('api_name', '')),
        str(row.get('chaos_source', '')),
        str(row.get('chaos_type_injected', '')),
    ))
    return rows


def write_chaos_vs_repair_matrix(rows, output_path='chaos_vs_repair_matrix.csv'):
    if not rows:
        return

    fieldnames = ['hardware', 'api_name', 'chaos_source', 'chaos_type_injected', 'chaos_detected', 'semantic_repair_type', 'p95_latency_ms', 'throughput_pps', 'resilience_P']
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def merge_raw_results(raw_dir='results/raw', output_file='combined_results.json', per_hardware_dir='hardware_results'):
    """
    Merge all run JSONs from raw_dir into a single output file.
    
    Process:
    - Walk results/raw/<hardware>/ directories
    - Load each *.json file (skip system_info.json, hardware_info.json)
    - Add metadata fields to each entry
    - Sort by hardware name, then run_id
    - Write to combined_results.json
    """
    normalization_summary = normalize_raw_results(raw_dir)

    if not os.path.isdir(raw_dir):
        print(f"Error: {raw_dir} does not exist")
        return
    
    all_entries = []
    entries_by_hardware = {}
    total_files = 0
    valid_entries = 0
    
    # Walk through hardware folders
    for hardware_folder in sorted(os.listdir(raw_dir)):
        hardware_path = os.path.join(raw_dir, hardware_folder)
        
        if not os.path.isdir(hardware_path):
            continue
        
        hardware_name = hardware_folder
        print(f"Processing hardware: {hardware_name}")
        
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

                output_hardware_name, vram_gb = infer_hardware_name_and_vram(hardware_name)
                
                # Create entry with metadata fields
                entry = {
                    'hardware': output_hardware_name,
                    'source_file': os.path.join(hardware_folder, filename),
                    'run_id': run_id,
                    'vram_gb': vram_gb,
                }
                
                # Merge in all fields from run_data
                entry.update(run_data)
                
                all_entries.append(entry)
                entries_by_hardware.setdefault(output_hardware_name, []).append(entry)
                valid_entries += 1
            
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load {hardware_name}/{filename}: {e}")
    
    # Sort by hardware name, then by run_id
    all_entries.sort(key=lambda x: (x['hardware'], x['run_id']))

    for hardware_name, hardware_entries in entries_by_hardware.items():
        hardware_entries.sort(key=lambda x: (x['hardware'], x['run_id']))
    
    # Write combined results
    write_json_file(output_file, all_entries)
    write_csv_file(os.path.splitext(output_file)[0] + '.csv', all_entries)

    chaos_vs_repair_rows = build_chaos_vs_repair_rows(all_entries)
    write_chaos_vs_repair_matrix(chaos_vs_repair_rows)

    os.makedirs(per_hardware_dir, exist_ok=True)
    for hardware_name, hardware_entries in sorted(entries_by_hardware.items()):
        hardware_file = os.path.join(per_hardware_dir, f"{safe_filename(hardware_name)}.json")
        write_json_file(hardware_file, hardware_entries)
        write_csv_file(os.path.splitext(hardware_file)[0] + '.csv', hardware_entries)
    
    print(f"\nMerge complete:")
    print(f"  Total files processed: {total_files}")
    print(f"  Valid entries written: {valid_entries}")
    print(f"  Output file: {os.path.abspath(output_file)}")
    print(f"  Per-hardware directory: {os.path.abspath(per_hardware_dir)}")
    print(f"  Normalization actions: {len(normalization_summary)}")
    print(f"  CSV outputs written alongside JSON files")
    print(f"  Chaos-vs-repair matrix: {os.path.abspath('chaos_vs_repair_matrix.csv')}")


if __name__ == '__main__':
    merge_raw_results()
