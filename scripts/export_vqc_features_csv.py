import json, csv, os
from pathlib import Path
from src.routing.feature_extractor import FeatureExtractor

def export_vqc_features():
    print("Extracting 10-dimensional VQC feature vectors across all 22,500 benchmark packets...")
    extractor = FeatureExtractor()
    
    input_file = "data/training/router_oracle_22500_v2.workload.jsonl"
        
    records = []
    with open(input_file, "r") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
            
    output_csv = "data/vqc_input_features_22500.csv"
    fieldnames = [
        "packet_id", "api_source", "chaos_method",
        "x0_field_count", "x1_nesting_depth", "x2_numeric_ratio", "x3_string_ratio",
        "x4_fields_added", "x5_fields_removed", "x6_key_edit_dist_mean",
        "x7_has_type_changes", "x8_has_structural_changes", "x9_source_encoded"
    ]
    
    with open(output_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for idx, item in enumerate(records):
            orig = item.get("original_data", item.get("original", {}))
            drifted = item.get("drifted_data", item.get("drifted", {}))
            api = item.get("source", item.get("api", "unknown"))
            chaos = item.get("chaos_method", "unknown")
            
            vec = extractor.extract(orig, drifted, source=api)
            
            writer.writerow({
                "packet_id": item.get("id", f"pkt_{idx}"),
                "api_source": api,
                "chaos_method": chaos,
                "x0_field_count": round(float(vec[0]), 6),
                "x1_nesting_depth": round(float(vec[1]), 6),
                "x2_numeric_ratio": round(float(vec[2]), 6),
                "x3_string_ratio": round(float(vec[3]), 6),
                "x4_fields_added": round(float(vec[4]), 6),
                "x5_fields_removed": round(float(vec[5]), 6),
                "x6_key_edit_dist_mean": round(float(vec[6]), 6),
                "x7_has_type_changes": round(float(vec[7]), 6),
                "x8_has_structural_changes": round(float(vec[8]), 6),
                "x9_source_encoded": round(float(vec[9]), 6),
            })
            
    print(f"SUCCESS: Exported {len(records):,} VQC feature vectors to {output_csv}!")

if __name__ == "__main__":
    export_vqc_features()
