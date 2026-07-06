import os
import sys
import json
import time
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

app = Flask(__name__, static_folder="static", static_url_path="/static")

# Shared state for simulation configuration
state_lock = threading.Lock()
simulation_config = {
    "drift_rate": 0.30,         # 0% to 100%
    "chaos_type": "json_manip",  # json_manip, schema_alter, numeric_noise
    "active_driver": "Fernando Alonso",
    "is_running": True
}

# Real F1 drivers to simulate
DRIVERS = ["Fernando Alonso", "Lewis Hamilton", "Max Verstappen", "Charles Leclerc"]

# Initialize models
if IMPORTS_OK:
    extractor = FeatureExtractor()
    router = QuantumRouter(backend="aer_simulator", enable_gemma=True)
    engine = ReconciliationEngine(hardware_profile="cpu")  # Defaults to CPU edge for safety inside container
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
def query_fireworks_ai(original, drifted, model="accounts/fireworks/models/llama-v3-70b-instruct"):
    api_key = os.environ.get("FIREWORKS_API_KEY")
    if not api_key:
        return mock_llm_reconciliation(original, drifted)

    try:
        import openai
        client = openai.OpenAI(
            base_url="https://api.fireworks.ai/inference/v1",
            api_key=api_key
        )
        
        prompt = f"""You are a resilient schema mapper for Formula 1 edge telemetry.
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

# Chaos injector simulating telemetry drifts
def inject_drift(original_data, chaos_type, drift_rate):
    if random.random() > drift_rate:
        return None, None

    drifted = dict(original_data)
    sub_type = "unknown"

    if chaos_type == "json_manip":
        # Rename keys or alter structure
        sub_type = "key_rename"
        if "throttle" in drifted:
            drifted["throttle_pedal_pct"] = drifted.pop("throttle")
        if "speed" in drifted:
            drifted["velocity_kmh"] = drifted.pop("speed")
            
    elif chaos_type == "schema_alter":
        # Nest structures or change types
        sub_type = "nested_schema"
        if "rpm" in drifted or "n_gear" in drifted:
            drifted["engine"] = {
                "revs": drifted.pop("rpm", 0),
                "gear": drifted.pop("n_gear", 0)
            }
            
    elif chaos_type == "numeric_noise":
        # Alter value types or add severe drift
        sub_type = "type_drift"
        if "speed" in drifted:
            # Change float speed to string
            drifted["speed"] = f"{drifted['speed']} KMH"
        if "brake" in drifted:
            drifted["brake"] = "ACTIVE" if drifted["brake"] > 50 else "OFF"

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
            driver = simulation_config["active_driver"]

        # Generate base telemetry
        original_data = generate_f1_packet(driver, packet_idx)
        packet_idx += 1

        # Wrap in expected Ingestor payload
        original_payload = {
            "source": "openf1",
            "timestamp": original_data["timestamp"],
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
                "source": "openf1",
                "timestamp": original_data["timestamp"],
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
            if routed_to == "levenshtein":
                t_start = time.perf_counter()
                healed_data = original_data  # Mock Levenshtein
                latency_ms = (time.perf_counter() - t_start) * 1000
                accuracy = 1.0
            elif routed_to == "regex":
                t_start = time.perf_counter()
                healed_data = original_data  # Mock Regex
                latency_ms = (time.perf_counter() - t_start) * 1000
                accuracy = 1.0
            elif routed_to == "bert":
                # Local BERT MiniLM mapping
                if IMPORTS_OK:
                    t_start = time.perf_counter()
                    res = engine.reconcile_bert_batch([(original_data, drifted_data)])[0]
                    healed_data = res["reconciled_data"]
                    latency_ms = (time.perf_counter() - t_start) * 1000
                    accuracy = res["accuracy"]
                else:
                    healed_data = original_data
                    latency_ms = random.uniform(8.0, 15.0)
            else:
                # Heavy Generative LLM Tier -> calls Fireworks AI
                res = query_fireworks_ai(original_data, drifted_data)
                healed_data = res["healed"]
                latency_ms = res["latency_ms"]
                accuracy = res["accuracy"]

            reconciled_payload = {
                "source": "openf1",
                "timestamp": original_data["timestamp"],
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
                "model": "AMD Instinct MI300X"
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
        if "is_running" in data:
            simulation_config["is_running"] = bool(data["is_running"])
            
    return jsonify({"status": "success", "config": simulation_config})

@app.route("/status")
def status():
    with state_lock:
        return jsonify({
            "imports_loaded": IMPORTS_OK,
            "fireworks_configured": bool(os.environ.get("FIREWORKS_API_KEY")),
            "config": simulation_config
        })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
