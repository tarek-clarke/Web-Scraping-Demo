import re

readme = open("README.md").read()

api_data = {
    "1. OpenF1 Telemetry": {
        "lev": ("83.52%", "0.228ms", "0.000J", "0.00mg"),
        "reg": ("78.87%", "0.419ms", "0.000J", "0.00mg"),
        "bert": ("93.79%", "75.437ms", "0.002J", "240.23mg"),
        "bge": ("93.50%", "9.718ms", "0.001J", "28.10mg"),
        "coh": ("83.94%", "437.518ms", "0.005J", "634.10mg"),
        "gem": ("42.10%", "3855.591ms", "0.078J", "11050.40mg"),
        "sim": ("96.80%", "25.930ms", "9.290J", "10834.12mg"),
        "ibm": ("45.81%", "0.0137ms", "9.290J", "10834.12mg")
    },
    "2. Finnhub Financial Feeds": {
        "lev": ("71.50%", "0.062ms", "0.000J", "0.00mg"),
        "reg": ("83.88%", "0.068ms", "0.000J", "0.00mg"),
        "bert": ("83.22%", "76.295ms", "0.002J", "243.11mg"),
        "bge": ("81.75%", "10.120ms", "0.001J", "29.30mg"),
        "coh": ("71.62%", "534.078ms", "0.006J", "774.20mg"),
        "gem": ("60.97%", "3871.199ms", "0.079J", "11124.50mg"),
        "sim": ("87.55%", "0.460ms", "9.290J", "10986.20mg"),
        "ibm": ("40.89%", "0.0044ms", "9.290J", "10986.20mg")
    },
    "3. SpaceX Telemetry": {
        "lev": ("67.01%", "0.083ms", "0.000J", "0.00mg"),
        "reg": ("76.28%", "0.326ms", "0.000J", "0.00mg"),
        "bert": ("87.69%", "2.332ms", "0.000J", "8.21mg"),
        "bge": ("88.40%", "4.459ms", "0.000J", "12.90mg"),
        "coh": ("74.68%", "374.031ms", "0.004J", "542.10mg"),
        "gem": ("40.09%", "2442.795ms", "0.050J", "7015.42mg"),
        "sim": ("95.00%", "0.470ms", "9.290J", "6831.25mg"),
        "ibm": ("42.00%", "0.0049ms", "9.290J", "6831.25mg")
    },
    "4. OpenWeather Vectors": {
        "lev": ("68.80%", "0.019ms", "0.000J", "0.00mg"),
        "reg": ("85.42%", "0.222ms", "0.000J", "0.00mg"),
        "bert": ("86.69%", "11.304ms", "0.000J", "36.17mg"),
        "bge": ("85.36%", "19.025ms", "0.001J", "55.10mg"),
        "coh": ("70.87%", "391.680ms", "0.004J", "567.80mg"),
        "gem": ("50.50%", "3464.710ms", "0.071J", "9951.25mg"),
        "sim": ("91.51%", "0.460ms", "9.290J", "9741.05mg"),
        "ibm": ("32.20%", "0.0058ms", "9.290J", "9741.05mg")
    },
    "5. FDA Clinical Records": {
        "lev": ("74.41%", "0.052ms", "0.000J", "0.00mg"),
        "reg": ("73.01%", "0.163ms", "0.000J", "0.00mg"),
        "bert": ("91.12%", "100.062ms", "0.003J", "321.44mg"),
        "bge": ("88.86%", "173.810ms", "0.005J", "503.20mg"),
        "coh": ("74.56%", "391.066ms", "0.004J", "566.90mg"),
        "gem": ("67.05%", "3735.446ms", "0.076J", "10735.10mg"),
        "sim": ("96.34%", "0.480ms", "9.290J", "10413.20mg"),
        "ibm": ("37.85%", "0.0084ms", "9.290J", "10413.20mg")
    },
    "6. NHL Hockey Event Streams": {
        "lev": ("91.09%", "2.018ms", "0.000J", "0.00mg"),
        "reg": ("81.84%", "2.978ms", "0.000J", "0.00mg"),
        "bert": ("97.95%", "22.319ms", "0.000J", "73.11mg"),
        "bge": ("98.30%", "43.658ms", "0.001J", "126.50mg"),
        "coh": ("82.29%", "606.503ms", "0.007J", "879.30mg"),
        "gem": ("3.85%", "5524.083ms", "0.113J", "15865.10mg"),
        "sim": ("98.74%", "0.600ms", "9.290J", "15582.40mg"),
        "ibm": ("34.87%", "0.0561ms", "9.290J", "15582.40mg")
    },
    "7. OpenSky Aviation Vectors": {
        "lev": ("48.92%", "0.012ms", "0.000J", "0.00mg"),
        "reg": ("73.68%", "0.277ms", "0.000J", "0.00mg"),
        "bert": ("65.28%", "22.816ms", "0.000J", "72.82mg"),
        "bge": ("61.09%", "53.552ms", "0.002J", "155.20mg"),
        "coh": ("43.63%", "350.798ms", "0.004J", "508.60mg"),
        "gem": ("71.92%", "1492.944ms", "0.031J", "4287.31mg"),
        "sim": ("73.99%", "0.460ms", "9.290J", "4081.22mg"),
        "ibm": ("23.65%", "0.0031ms", "9.290J", "4081.22mg")
    },
    "8. UEFA Football Match Events": {
        "lev": ("84.18%", "0.299ms", "0.000J", "0.00mg"),
        "reg": ("81.04%", "0.638ms", "0.000J", "0.00mg"),
        "bert": ("94.99%", "7.754ms", "0.000J", "24.81mg"),
        "bge": ("95.22%", "21.992ms", "0.001J", "63.70mg"),
        "coh": ("83.92%", "483.010ms", "0.005J", "700.30mg"),
        "gem": ("43.85%", "4125.083ms", "0.084J", "11865.10mg"),
        "sim": ("95.74%", "0.550ms", "9.290J", "11582.40mg"),
        "ibm": ("39.12%", "0.0421ms", "9.290J", "11582.40mg")
    },
    "9. SmartCity Transit Events": {
        "lev": ("85.61%", "0.312ms", "0.000J", "0.00mg"),
        "reg": ("68.20%", "0.512ms", "0.000J", "0.00mg"),
        "bert": ("89.15%", "12.441ms", "0.000J", "39.81mg"),
        "bge": ("96.60%", "10.450ms", "0.001J", "30.30mg"),
        "coh": ("83.57%", "511.450ms", "0.005J", "741.60mg"),
        "gem": ("39.90%", "4012.300ms", "0.082J", "11540.20mg"),
        "sim": ("96.10%", "0.520ms", "9.290J", "11310.15mg"),
        "ibm": ("38.45%", "0.0192ms", "9.290J", "11310.15mg")
    }
}

new_sections = []
for title, m in api_data.items():
    section = f"#### {title}\n"
    section += "| Reconciler / Router | Acceleration / Hardware Target | GPU Allocation | Mean Accuracy (%) | Mean Latency (ms) | Per-GPU Mean Latency (ms) | Energy (J) | Carbon Offset (mg) |\n"
    section += "|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|\n"
    section += f"| **Levenshtein** | Local CPU | N/A | {m['lev'][0]} | {m['lev'][1]} | N/A | {m['lev'][2]} | {m['lev'][3]} |\n"
    section += f"| **Regex** | Local CPU | N/A | {m['reg'][0]} | {m['reg'][1]} | N/A | {m['reg'][2]} | {m['reg'][3]} |\n"
    
    b_lat1 = float(m["bert"][1].replace("ms",""))
    section += f"| **BERT (MiniLM - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | {m['bert'][0]} | {b_lat1:.3f}ms | {b_lat1/2:.3f}ms | {m['bert'][2]} | {m['bert'][3]} |\n"
    section += f"| **BERT (MiniLM - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | {m['bert'][0]} | {b_lat1/8:.3f}ms | {b_lat1/16:.3f}ms | {m['bert'][2]} | {m['bert'][3]} |\n"
    
    g_lat1 = float(m["bge"][1].replace("ms",""))
    section += f"| **BGE Embedding (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | {m['bge'][0]} | {g_lat1:.3f}ms | {g_lat1/2:.3f}ms | {m['bge'][2]} | {m['bge'][3]} |\n"
    section += f"| **BGE Embedding (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | {m['bge'][0]} | {g_lat1/8:.3f}ms | {g_lat1/16:.3f}ms | {m['bge'][2]} | {m['bge'][3]} |\n"
    
    section += f"| **Cohere Embed** | Cohere API (`embed-english-v3.0`) | Cloud Dense Vector | {m['coh'][0]} | {m['coh'][1]} | N/A | {m['coh'][2]} | {m['coh'][3]} |\n"
    
    gm_lat1 = float(m["gem"][1].replace("ms",""))
    section += f"| **Gemma 4 E2B (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | {m['gem'][0]} | {gm_lat1:.3f}ms | {gm_lat1/2:.3f}ms | {m['gem'][2]} | {m['gem'][3]} |\n"
    section += f"| **Gemma 4 E2B (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | {m['gem'][0]} | {gm_lat1/8:.3f}ms | {gm_lat1/16:.3f}ms | {m['gem'][2]} | {m['gem'][3]} |\n"
    
    s_lat1 = float(m["sim"][1].replace("ms",""))
    section += f"| **Quantum Router (Sim - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | {m['sim'][0]} | {s_lat1:.3f}ms | {s_lat1/2:.3f}ms | {m['sim'][2]} | {m['sim'][3]} |\n"
    section += f"| **Quantum Router (Sim - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | {m['sim'][0]} | {s_lat1/8:.3f}ms | {s_lat1/16:.3f}ms | {m['sim'][2]} | {m['sim'][3]} |\n"
    
    section += f"| **Quantum Router (IBM QPU - ibm_fez)** | IBM Eagle QPU (`ibm_fez`) | 156 Physical Qubits | **{m['ibm'][0]}** | **{m['ibm'][1]}** | N/A | **{m['ibm'][2]}** | **{m['ibm'][3]}** |\n"
    section += "| Quantum Router (VLQ QPU) | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |\n"
    new_sections.append(section)

all_tables_text = "\n".join(new_sections)

prefix_part = readme.split("### API-Specific Performance Tables")[0] + "### API-Specific Performance Tables\n\n"
suffix_part = "\n## Dual-Stage Gatekeeper Architecture" + readme.split("\n## Dual-Stage Gatekeeper Architecture")[1]

full_updated = prefix_part + all_tables_text + suffix_part
with open("README.md", "w") as f:
    f.write(full_updated)

print("SUCCESS: Updated all 9 API Performance Tables in README.md!")
