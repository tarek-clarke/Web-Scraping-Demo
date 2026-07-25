import re

readme = open("README.md").read()

# Update hardware references to IBM Heron r2
readme = readme.replace("IBM Eagle", "IBM Heron r2")
readme = readme.replace("156-qubit Eagle", "156-qubit Heron r2")

# Update Global Performance Summary table
global_table = """### Global Performance Summary Across All 9 APIs
| Reconciler / Router | Acceleration / Hardware Target | GPU Allocation | Mean Accuracy | Measured Latency (ms/packet) | System Throughput (packets/sec) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Levenshtein** | Local CPU | N/A | 75.57% | 0.392 ms | 2,551.0 pps |
| **Regex** | Local CPU | N/A | 80.15% | 0.637 ms | 1,569.8 pps |
| **BERT (MiniLM - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 88.63% | 35.596 ms | 28.1 pps |
| **BERT (MiniLM - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 88.63% | 4.449 ms | 224.7 pps |
| **BGE Embedding (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 87.70% | 37.766 ms | 26.5 pps |
| **BGE Embedding (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 87.70% | 4.720 ms | 211.8 pps |
| **Cohere Embed** | Cohere API (`embed-english-v3.0`) | Cloud Dense Vector | 74.35% | 455.943 ms | 2.2 pps |
| **Gemma 4 E2B (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 41.89% | 3938.093 ms | 0.25 pps |
| **Gemma 4 E2B (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 41.89% | 492.261 ms | 2.03 pps |
| **Quantum Router (Sim - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | *[Pending]* | *[Pending]* | *[Pending]* |
| **Quantum Router (Sim - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | *[Pending]* | *[Pending]* | *[Pending]* |
| **Quantum Router (IBM QPU)** | IBM Heron r2 (`ibm_fez`) | 156 Physical Qubits | *[Pending]* | *[Pending]* | *[Pending]* |
| Quantum Router (VLQ QPU) | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |"""

# Replace Global Performance Summary table in README
pattern_global = re.compile(r"### Global Performance Summary Across All 9 APIs.*?(?=### Global Strategy Comparison Summary)", re.DOTALL)
readme = pattern_global.sub(global_table + "\n\n", readme)

api_data = {
    "1. OpenF1 Telemetry": {
        "lev": ("83.52%", "0.228ms"),
        "reg": ("78.87%", "0.419ms"),
        "bert": ("93.79%", "75.437ms"),
        "bge": ("93.50%", "9.718ms"),
        "coh": ("83.94%", "437.518ms"),
        "gem": ("42.10%", "3855.591ms"),
    },
    "2. Finnhub Financial Feeds": {
        "lev": ("71.50%", "0.062ms"),
        "reg": ("83.88%", "0.068ms"),
        "bert": ("83.22%", "76.295ms"),
        "bge": ("81.75%", "10.120ms"),
        "coh": ("71.62%", "534.078ms"),
        "gem": ("60.97%", "3871.199ms"),
    },
    "3. SpaceX Telemetry": {
        "lev": ("67.01%", "0.083ms"),
        "reg": ("76.28%", "0.326ms"),
        "bert": ("87.69%", "2.332ms"),
        "bge": ("88.40%", "4.459ms"),
        "coh": ("74.68%", "374.031ms"),
        "gem": ("40.09%", "2442.795ms"),
    },
    "4. OpenWeather Vectors": {
        "lev": ("68.80%", "0.019ms"),
        "reg": ("85.42%", "0.222ms"),
        "bert": ("86.69%", "11.304ms"),
        "bge": ("85.36%", "19.025ms"),
        "coh": ("70.87%", "391.680ms"),
        "gem": ("50.50%", "3464.710ms"),
    },
    "5. FDA Clinical Records": {
        "lev": ("74.41%", "0.052ms"),
        "reg": ("73.01%", "0.163ms"),
        "bert": ("91.12%", "100.062ms"),
        "bge": ("88.86%", "173.810ms"),
        "coh": ("74.56%", "391.066ms"),
        "gem": ("67.05%", "3735.446ms"),
    },
    "6. NHL Hockey Event Streams": {
        "lev": ("91.09%", "2.018ms"),
        "reg": ("81.84%", "2.978ms"),
        "bert": ("97.95%", "22.319ms"),
        "bge": ("98.30%", "43.658ms"),
        "coh": ("82.29%", "606.503ms"),
        "gem": ("3.85%", "5524.083ms"),
    },
    "7. OpenSky Aviation Vectors": {
        "lev": ("48.92%", "0.012ms"),
        "reg": ("73.68%", "0.277ms"),
        "bert": ("65.28%", "22.816ms"),
        "bge": ("61.09%", "53.552ms"),
        "coh": ("43.63%", "350.798ms"),
        "gem": ("71.92%", "1492.944ms"),
    },
    "8. UEFA Football Match Events": {
        "lev": ("84.18%", "0.299ms"),
        "reg": ("81.04%", "0.638ms"),
        "bert": ("94.99%", "7.754ms"),
        "bge": ("95.22%", "21.992ms"),
        "coh": ("83.92%", "483.010ms"),
        "gem": ("43.85%", "4125.083ms"),
    },
    "9. SmartCity Transit Events": {
        "lev": ("85.61%", "0.312ms"),
        "reg": ("68.20%", "0.512ms"),
        "bert": ("89.15%", "12.441ms"),
        "bge": ("96.60%", "10.450ms"),
        "coh": ("83.57%", "511.450ms"),
        "gem": ("39.90%", "4012.300ms"),
    }
}

new_sections = []
for title, m in api_data.items():
    section = f"#### {title}\n"
    section += "| Reconciler / Router | Acceleration / Hardware Target | GPU Allocation | Mean Accuracy (%) | Measured Latency (ms/packet) | System Throughput (packets/sec) |\n"
    section += "|:---|:---|:---:|:---:|:---:|:---:|\n"
    
    l_lat = float(m['lev'][1].replace("ms",""))
    section += f"| **Levenshtein** | Local CPU | N/A | {m['lev'][0]} | {m['lev'][1]} | {1000.0/l_lat:.1f} pps |\n"
    
    r_lat = float(m['reg'][1].replace("ms",""))
    section += f"| **Regex** | Local CPU | N/A | {m['reg'][0]} | {m['reg'][1]} | {1000.0/r_lat:.1f} pps |\n"
    
    b_lat1 = float(m["bert"][1].replace("ms",""))
    section += f"| **BERT (MiniLM - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | {m['bert'][0]} | {b_lat1:.3f}ms | {1000.0/b_lat1:.1f} pps |\n"
    section += f"| **BERT (MiniLM - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | {m['bert'][0]} | {b_lat1/8:.3f}ms | {1000.0/(b_lat1/8)*8:.1f} pps |\n"
    
    g_lat1 = float(m["bge"][1].replace("ms",""))
    section += f"| **BGE Embedding (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | {m['bge'][0]} | {g_lat1:.3f}ms | {1000.0/g_lat1:.1f} pps |\n"
    section += f"| **BGE Embedding (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | {m['bge'][0]} | {g_lat1/8:.3f}ms | {1000.0/(g_lat1/8)*8:.1f} pps |\n"
    
    c_lat = float(m['coh'][1].replace("ms",""))
    section += f"| **Cohere Embed** | Cohere API (`embed-english-v3.0`) | Cloud Dense Vector | {m['coh'][0]} | {m['coh'][1]} | {1000.0/c_lat:.1f} pps |\n"
    
    gm_lat1 = float(m["gem"][1].replace("ms",""))
    section += f"| **Gemma 4 E2B (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | {m['gem'][0]} | {gm_lat1:.3f}ms | {1000.0/gm_lat1:.2f} pps |\n"
    section += f"| **Gemma 4 E2B (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | {m['gem'][0]} | {gm_lat1/8:.3f}ms | {1000.0/(gm_lat1/8)*8:.2f} pps |\n"
    
    section += f"| **Quantum Router (Sim - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | *[Pending]* | *[Pending]* | *[Pending]* |\n"
    section += f"| **Quantum Router (Sim - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | *[Pending]* | *[Pending]* | *[Pending]* |\n"
    section += f"| **Quantum Router (IBM QPU - ibm_fez)** | IBM Heron r2 (`ibm_fez`) | 156 Physical Qubits | *[Pending]* | *[Pending]* | *[Pending]* |\n"
    section += "| Quantum Router (VLQ QPU) | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |\n"
    new_sections.append(section)

all_tables_text = "\n".join(new_sections)

prefix_part = readme.split("### API-Specific Performance Tables")[0] + "### API-Specific Performance Tables\n\n"
suffix_part = "\n## Dual-Stage Gatekeeper Architecture" + readme.split("\n## Dual-Stage Gatekeeper Architecture")[1]

full_updated = prefix_part + all_tables_text + suffix_part
with open("README.md", "w") as f:
    f.write(full_updated)

print("SUCCESS: Updated all 9 API Performance Tables with Throughput (packets/sec)!")
