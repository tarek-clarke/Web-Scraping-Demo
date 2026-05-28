#!/usr/bin/env python3
"""Quick validation of pristine_chaos_vs_repair_matrix.csv"""

import pandas as pd

df = pd.read_csv('pristine_chaos_vs_repair_matrix.csv')

print('✓ File: pristine_chaos_vs_repair_matrix.csv')
print(f'✓ Total Records: {len(df):,}')
print(f'✓ Total Columns: {len(df.columns)}')

print('\n=== LOGIC CONSTRAINT VERIFICATION ===')
print('\n1. Chaos_Source Distribution:')
print(df['Chaos_Source'].value_counts())

print('\n2. Injected_Chaos_Type (Top 5):')
print(df['Injected_Chaos_Type'].value_counts().head(5))

print('\n3. Detected_Chaos_Type (Top 5):')
print(df['Detected_Chaos_Type'].value_counts().head(5))

print('\n4. Semantic_Repair_Pathway:')
print(df['Semantic_Repair_Pathway'].value_counts())

print('\n5. Hardware Distribution:')
print(df['Hardware'].value_counts().head())

print('\n=== PERFORMANCE METRICS ===')
print(f'P95_Latency_ms - Mean: {df["P95_Latency_ms"].mean():.2f} ms, Median: {df["P95_Latency_ms"].median():.2f} ms')
print(f'Resilience_P - Mean: {df["Resilience_P"].mean():.4f}, Median: {df["Resilience_P"].median():.4f}')
print(f'Throughput_pps - Mean: {df["Throughput_pps"].mean():.2f} pps')

print('\n=== SAMPLE ROWS (Different Chaos Types) ===')
for chaos_type in ['split_fields', 'type_mismatch', 'value_contradiction']:
    sample = df[df['Injected_Chaos_Type'] == chaos_type].iloc[0]
    print(f'\n{chaos_type.upper()}:')
    print(f'  Chaos_Source: {sample["Chaos_Source"]}')
    print(f'  Detected_Chaos_Type: {sample["Detected_Chaos_Type"]}')
    print(f'  Semantic_Repair_Pathway: {sample["Semantic_Repair_Pathway"]}')
    print(f'  Hardware: {sample["Hardware"]}')
    print(f'  P95_Latency_ms: {sample["P95_Latency_ms"]:.3f}')
    print(f'  Resilience_P: {sample["Resilience_P"]:.4f}')
