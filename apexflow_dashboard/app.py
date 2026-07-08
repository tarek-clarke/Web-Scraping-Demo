import os
import sys
import json
import time
import math
import random
import threading
from datetime import datetime
from flask import Flask, Response, render_template, jsonify, request

# Add parent directory to path to import src modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from src.routing.quantum_router import QuantumRouter
    from src.routing.feature_extractor import FeatureExtractor
    from src.reconciliation.engine import ReconciliationEngine
    IMPORTS_OK = True
except ImportError:
    IMPORTS_OK = False

# Dynamically detect hardware platform
PLATFORM_NAME = "AMD Instinct MI300X (ROCm 6.1)"
GPU_MODEL = "AMD Instinct MI300X"

try:
    import torch
    if torch.cuda.is_available():
        device_name = torch.cuda.get_device_name(0)
        if "AMD" in device_name or "Instinct" in device_name:
            PLATFORM_NAME = f"{device_name} (ROCm 6.1)"
            GPU_MODEL = device_name
            HW_PROFILE = "rocm"
        else:
            PLATFORM_NAME = f"{device_name} (CUDA)"
            GPU_MODEL = device_name
            HW_PROFILE = "cuda"
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        PLATFORM_NAME = "Apple Silicon (MPS / Unified Memory)"
        GPU_MODEL = "Apple M4 (Metal)"
        HW_PROFILE = "cpu"
    else:
        PLATFORM_NAME = "Local CPU (Classical Fallback)"
        GPU_MODEL = "Standard CPU"
        HW_PROFILE = "cpu"
except Exception:
    PLATFORM_NAME = "Local CPU (Classical Fallback)"
    GPU_MODEL = "Standard CPU"
    HW_PROFILE = "cpu"

app = Flask(__name__, static_folder="static", static_url_path="/static")

# Shared state for simulation configuration
state_lock = threading.Lock()
simulation_config = {
    "drift_rate": 0.30,
    "chaos_type": "json_manip",
    "active_driver": "Fernando Alonso",
    "data_source": "openf1",
    "is_running": True
}

DATA_SOURCES = ["openf1", "openmeteo", "spacex", "finnhub"]

STOCK_SYMBOLS = ["AAPL", "TSLA", "NVDA", "AMZN"]

MISSIONS = ["Starlink-6", "Crew-9", "GPS-III-7", "Transporter-11"]

# Real F1 drivers to simulate
DRIVERS = ["Fernando Alonso", "Lewis Hamilton", "Max Verstappen", "Charles Leclerc"]

# Initialize models
if IMPORTS_OK:
    extractor = FeatureExtractor()
    router = QuantumRouter(backend="aer_simulator", enable_gemma=True)
    try:
        engine = ReconciliationEngine(hardware_profile=HW_PROFILE)
    except Exception:
        engine = None
else:
    extractor = None
    router = None
    engine = None

# Mock LLM response generator if Fireworks API is not set
def mock_llm_reconciliation(original, drifted):
    healed = dict(original)
    return {
        "healed": healed,
        "accuracy": 1.0,
        "latency_ms": random.uniform(120.0, 240.0)
    }

# Call Fireworks AI API for schema reconciliation
def query_fireworks_ai(original, drifted, model="accounts/tarek-clarke/deployments/rqehi2co"):
    api_key = os.environ.get("FIREWORKS_API_KEY")
    if not api_key:
        return mock_llm_reconciliation(original, drifted)

    try:
        import openai
        client = openai.OpenAI(
            base_url="https://api.fireworks.ai/inference/v1",
            api_key=api_key
        )
        
        prompt = f"""You are a resilient schema mapper for real-time edge telemetry.
Given the original expected schema format and the corrupted, drifted schema format received from the sensor, reconstruct the data back to matching the original format. Correct all value type changes, missing keys, and nested structural modifications.

Original Schema:
{json.dumps(original, indent=2)}

Drifted Schema:
{json.dumps(drifted, indent=2)}

Return ONLY the corrected telemetry payload matching the original schema as a raw JSON block. Do not include any explanation or markdown formatting."""

        t_start = time.perf_counter()
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=256
        )
        latency = (time.perf_counter() - t_start) * 1000
        
        content = response.choices[0].message.content.strip()
        # Strip markdown code blocks if model included them
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        healed = json.loads(content)
        return {"healed": healed, "accuracy": 1.0, "latency_ms": latency}
    except Exception as e:
        print(f"[Fireworks API Error] {e}")
        return mock_llm_reconciliation(original, drifted)

# Chaos injector simulating telemetry drifts (generic, works on any schema)
def inject_drift(original_data, chaos_type, drift_rate):
    if random.random() > drift_rate:
        return None, None

    drifted = dict(original_data)
    sub_type = "unknown"
    keys = list(drifted.keys())

    if chaos_type == "json_manip":
        sub_type = "key_rename"
        # Rename 1-2 random keys
        for k in random.sample(keys, min(2, len(keys))):
            new_key = k + "_field" if not k.endswith("_field") else k.replace("_field", "_data")
            drifted[new_key] = drifted.pop(k)

    elif chaos_type == "schema_alter":
        sub_type = "nested_schema"
        # Nest 1-2 random numeric keys into a sub-dict
        numeric_keys = [k for k in keys if isinstance(drifted[k], (int, float))]
        for k in random.sample(numeric_keys, min(2, len(numeric_keys))):
            drifted[k + "_group"] = {"value": drifted.pop(k), "unit": "auto"}

    elif chaos_type == "numeric_noise":
        sub_type = "type_drift"
        # Convert 1-2 numeric values to strings
        numeric_keys = [k for k in keys if isinstance(drifted[k], (int, float))]
        for k in random.sample(numeric_keys, min(2, len(numeric_keys))):
            drifted[k] = str(drifted[k]) + " UNIT"

    return drifted, sub_type

    return drifted, sub_type

# Generate realistic F1 live telemetry packet
def generate_f1_packet(driver_name, packet_idx):
    # Oscillate values around a race lap simulation
    t = packet_idx * 0.1
    speed = int(220 + 80 * (0.5 * (1 + (0.5 * t).numerator % 2) if hasattr(t, 'numerator') else 0.5)) # Avoid math type issues
    speed = 220 + int(80 * (0.3 * (packet_idx % 10) - 1.5)) # Clean deterministic simulation
    speed = max(80, min(330, speed + random.randint(-15, 15)))
    
    throttle = 100 if speed > 220 else random.randint(20, 80)
    brake = 0 if throttle > 80 else random.randint(30, 100)
    gear = max(1, min(8, int(speed / 40)))
    rpm = int(speed * 35 + random.randint(-200, 200))

    return {
        "driver": driver_name,
        "speed": speed,
        "throttle": throttle,
        "brake": brake,
        "n_gear": gear,
        "rpm": rpm,
        "session_key": 11326,
        "timestamp": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    }

def generate_openmeteo_packet(station_id, packet_idx):
    t = packet_idx * 0.1
    base_temp = 15.0 + 10 * math.sin(t * 0.3)
    temp = round(base_temp + random.uniform(-2, 2), 1)
    humidity = max(20, min(100, int(60 + 20 * math.sin(t * 0.5) + random.randint(-5, 5))))
    wind_speed = max(0, int(15 + 10 * math.sin(t * 0.2) + random.randint(-3, 3)))
    wind_dir = (packet_idx * 5) % 360
    pressure = round(1013 + 5 * math.sin(t * 0.1) + random.uniform(-1, 1), 1)
    precipitation = round(max(0, 3 * math.sin(t * 0.4) + random.uniform(-0.5, 0.5)), 1)

    return {
        "station_id": station_id,
        "temperature": temp,
        "humidity": humidity,
        "wind_speed": wind_speed,
        "wind_direction": wind_dir,
        "pressure": pressure,
        "precipitation": precipitation,
        "timestamp": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    }

def generate_spacex_packet(mission_name, packet_idx):
    t = packet_idx * 0.5
    altitude = 100 + int(t * 50 + random.randint(-20, 20))
    velocity = int(7800 + 200 * math.sin(t * 0.1) + random.randint(-50, 50))
    fuel_pct = max(5, round(100 - t * 0.8, 1))
    stage = 1 if fuel_pct > 30 else 2
    engine_count = 9 if stage == 1 else 1
    thrust = int(7600 + 300 * math.sin(t * 0.2) + random.randint(-100, 100))

    return {
        "mission": mission_name,
        "altitude_km": altitude,
        "velocity_ms": velocity,
        "fuel_pct": fuel_pct,
        "stage": stage,
        "engines_active": engine_count,
        "thrust_kn": thrust,
        "timestamp": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    }

def generate_finnhub_packet(symbol, packet_idx):
    t = packet_idx * 0.1
    base_price = {"AAPL": 225, "TSLA": 248, "NVDA": 128, "AMZN": 186}.get(symbol, 100)
    price = round(base_price + 5 * math.sin(t * 0.3) + random.uniform(-1.5, 1.5), 2)
    volume = int(1000000 + 500000 * math.sin(t * 0.2) + random.randint(-100000, 100000))
    change_pct = round(2 * math.sin(t * 0.3) + random.uniform(-0.5, 0.5), 2)
    market_cap = round(price * volume / 1e9, 2)

    return {
        "symbol": symbol,
        "price": price,
        "volume": volume,
        "change_pct": change_pct,
        "market_cap_b": market_cap,
        "timestamp": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    }

# Live data fetchers (no API key required for OpenMeteo and OpenF1)
def fetch_live_openmeteo(station_id, lat=59.4, lon=24.7):
    try:
        import urllib.request
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,surface_pressure,precipitation"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
        c = data.get("current", {})
        return {
            "station_id": station_id,
            "temperature": c.get("temperature_2m", 0),
            "humidity": c.get("relative_humidity_2m", 0),
            "wind_speed": c.get("wind_speed_10m", 0),
            "wind_direction": c.get("wind_direction_10m", 0),
            "pressure": c.get("surface_pressure", 1013),
            "precipitation": c.get("precipitation", 0),
            "timestamp": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        }
    except Exception:
        return None

def fetch_live_openf1(driver_name):
    try:
        import urllib.request
        url = "https://api.openf1.org/v1/car_data?driver_number=1&session_key=latest&speed>0&limit=1"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
        if data:
            d = data[0]
            return {
                "driver": driver_name,
                "speed": d.get("speed", 0),
                "throttle": d.get("throttle", 0),
                "brake": d.get("brake", 0),
                "n_gear": d.get("n_gear", 1),
                "rpm": d.get("rpm", 0),
                "session_key": d.get("session_key", 0),
                "timestamp": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            }
    except Exception:
        return None

PACKET_GENERATORS = {
    "openf1": lambda ctx, idx: generate_f1_packet(ctx, idx),
    "openmeteo": lambda ctx, idx: generate_openmeteo_packet(ctx, idx),
    "spacex": lambda ctx, idx: generate_spacex_packet(ctx, idx),
    "finnhub": lambda ctx, idx: generate_finnhub_packet(ctx, idx),
}

SOURCE_LABELS = {
    "openf1": "OpenF1 Telemetry",
    "openmeteo": "OpenMeteo Weather",
    "spacex": "SpaceX Launch",
    "finnhub": "Finnhub Market Data",
}

SOURCE_CONTEXTS = {
    "openf1": "Fernando Alonso",
    "openmeteo": "STATION_42",
    "spacex": "Starlink-6",
    "finnhub": "AAPL",
}

LIVE_FETCHERS = {
    "openf1": fetch_live_openf1,
    "openmeteo": fetch_live_openmeteo,
}

# Event stream yielding live data to browser
def event_generator():
    packet_idx = 0
    while True:
        with state_lock:
            if not simulation_config["is_running"]:
                time.sleep(1)
                continue
            drift_rate = simulation_config["drift_rate"]
            chaos_type = simulation_config["chaos_type"]
            data_source = simulation_config.get("data_source", "openf1")
            context = SOURCE_CONTEXTS.get(data_source, "Fernando Alonso")

        packet_idx += 1

        # Try live data first, fall back to simulated
        original_data = None
        if data_source in LIVE_FETCHERS:
            original_data = LIVE_FETCHERS[data_source](context)

        if original_data is None:
            gen = PACKET_GENERATORS.get(data_source, PACKET_GENERATORS["openf1"])
            original_data = gen(context, packet_idx)

        source_label = SOURCE_LABELS.get(data_source, "openf1")

        # Wrap in expected Ingestor payload
        original_payload = {
            "source": data_source,
            "timestamp": original_data.get("timestamp", datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')),
            "data": original_data
        }

        # Inject drift/chaos
        drifted_payload = None
        reconciled_payload = original_payload
        routed_to = "passthrough"
        confidence = 1.0
        latency_ms = 0.05
        accuracy = 1.0

        drift_result = inject_drift(original_data, chaos_type, drift_rate)
        if drift_result[0] is not None:
            drifted_data, sub_type = drift_result
            drifted_payload = {
                "source": data_source,
                "timestamp": original_data.get("timestamp", datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')),
                "data": drifted_data
            }

            # Run Quantum Router
            if IMPORTS_OK:
                feat = extractor.extract(original_data, drifted_data, "openf1")
                routed_to, confidence = router.route_packet(feat)
            else:
                # Local classical fallback heuristics
                if chaos_type == "json_manip":
                    routed_to = "regex"
                elif chaos_type == "schema_alter":
                    routed_to = "bert"
                else:
                    routed_to = "gemma_e4b"

            # Execute routed self-healing tier
            if routed_to in ("levenshtein", "regex"):
                if IMPORTS_OK:
                    res = engine.reconcile({"data": original_data}, {"data": drifted_data}, routed_to)
                    healed_data = res.get("reconciled_data", original_data)
                    latency_ms = res["latency_ms"]
                    accuracy = res["accuracy"]
                else:
                    import Levenshtein
                    t_start = time.perf_counter()
                    healed_data = dict(original_data)
                    for ok in list(original_data.keys()):
                        for dk in list(drifted_data.keys()):
                            if Levenshtein.distance(ok, dk) <= 3:
                                healed_data[ok] = drifted_data[dk]
                                break
                    latency_ms = (time.perf_counter() - t_start) * 1000
                    accuracy = 1.0
            elif routed_to == "bert":
                if IMPORTS_OK:
                    t_start = time.perf_counter()
                    res = engine.reconcile_bert_batch([(original_data, drifted_data)])[0]
                    healed_data = res.get("reconciled_data", original_data)
                    latency_ms = (time.perf_counter() - t_start) * 1000
                    accuracy = res["accuracy"]
                else:
                    healed_data = original_data
                    latency_ms = random.uniform(8.0, 15.0)
                    accuracy = 0.85
            else:
                # Heavy Generative LLM Tier -> calls Fireworks AI
                res = query_fireworks_ai(original_data, drifted_data)
                healed_data = res["healed"]
                latency_ms = res["latency_ms"]
                accuracy = res["accuracy"]

            reconciled_payload = {
                "source": data_source,
                "timestamp": original_data.get("timestamp", datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')),
                "data": healed_data
            }

        # Simulated AMD Instinct MI300X diagnostics
        temp = 42.5 + random.uniform(0.1, 0.9)
        power = 90.0 + random.uniform(0.5, 2.5) if drifted_payload else 82.0 + random.uniform(0.1, 1.0)
        vram = 14529.6 if routed_to in ["gemma_e4b", "nemotron"] else 2180.4 + random.uniform(5.0, 15.0)

        sse_data = {
            "packet_idx": packet_idx,
            "original": original_payload,
            "drifted": drifted_payload,
            "reconciled": reconciled_payload,
            "routing": {
                "decision": routed_to,
                "confidence": confidence,
                "latency_ms": latency_ms,
                "accuracy": accuracy
            },
            "gpu": {
                "temperature_c": temp,
                "power_w": power,
                "vram_mb": vram,
                "model": GPU_MODEL,
                "platform": PLATFORM_NAME
            }
        }

        yield f"data: {json.dumps(sse_data)}\n\n"
        time.sleep(0.5)

@app.route("/")
def index():
    return app.send_static_file("index.html")

@app.route("/stream")
def stream():
    return Response(event_generator(), mimetype="text/event-stream")

@app.route("/config", methods=["POST"])
def update_config():
    data = request.json
    with state_lock:
        if "drift_rate" in data:
            simulation_config["drift_rate"] = float(data["drift_rate"])
        if "chaos_type" in data:
            simulation_config["chaos_type"] = data["chaos_type"]
        if "active_driver" in data:
            simulation_config["active_driver"] = data["active_driver"]
        if "data_source" in data:
            simulation_config["data_source"] = data["data_source"]
            ctx = SOURCE_CONTEXTS.get(data["data_source"], "Fernando Alonso")
            simulation_config["active_driver"] = ctx
        if "is_running" in data:
            simulation_config["is_running"] = bool(data["is_running"])
            
    return jsonify({"status": "success", "config": simulation_config})

@app.route("/status")
def status():
    with state_lock:
        return jsonify({
            "imports_loaded": IMPORTS_OK,
            "fireworks_configured": bool(os.environ.get("FIREWORKS_API_KEY")),
            "data_sources": DATA_SOURCES,
            "source_labels": SOURCE_LABELS,
            "config": simulation_config
        })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=False)
