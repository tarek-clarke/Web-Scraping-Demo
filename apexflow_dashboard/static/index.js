// Chart instances
let telemetryChart;
let latencyChart;

// Chart history arrays
const chartHistoryLimit = 20;
const speedData = [];
const throttleData = [];
const brakeData = [];
const chartLabels = [];

const gemmaLatencyData = [];
const bertLatencyData = [];
const localLatencyLabels = [];

// Dynamic chart labels per data source
const CHART_LABELS = {
    "openf1": ["Speed (km/h)", "Throttle (%)", "Brake (%)"],
    "openmeteo": ["Temperature (°C)", "Humidity (%)", "Wind Speed (km/h)"],
    "spacex": ["Altitude (km)", "Velocity (m/s)", "Fuel (%)"],
    "finnhub": ["Price ($)", "Volume", "Change (%)"],
};

let currentSource = "openf1";

// Initialize SSE Stream Connection
let eventSource;
let isRunning = true;

// DOM Elements
const driverSelect = document.getElementById("driver-select");
const sourceSelect = document.getElementById("source-select");
const sliderDrift = document.getElementById("slider-drift");
const driftValueText = document.getElementById("drift-rate-value");
const btnPause = document.getElementById("btn-pause");

const statusRouter = document.getElementById("status-router");
const statusFireworks = document.getElementById("status-fireworks");
const statusDriver = document.getElementById("status-driver");

const textRoutingDecision = document.getElementById("routing-decision");
const textRoutingConfidence = document.getElementById("routing-confidence");
const textRoutingLatency = document.getElementById("routing-latency");
const progressBarRouter = document.getElementById("router-progress");

const textGpuTemp = document.getElementById("gpu-temp");
const textGpuPower = document.getElementById("gpu-power");
const textGpuVram = document.getElementById("gpu-vram");
const textGpuPlatform = document.getElementById("gpu-platform-tag");

const codeOriginal = document.getElementById("json-original");
const codeDrifted = document.getElementById("json-drifted");
const codeReconciled = document.getElementById("json-reconciled");

const apiKeyInput = document.getElementById("api-key-input");
const btnSetKey = document.getElementById("btn-set-key");
const btnClearKey = document.getElementById("btn-clear-key");

// Initialize charts using Chart.js CDN
function initCharts() {
    // 1. Telemetry Chart
    const ctxTelemetry = document.getElementById("chart-telemetry").getContext("2d");
    telemetryChart = new Chart(ctxTelemetry, {
        type: 'line',
        data: {
            labels: chartLabels,
            datasets: [
                {
                    label: 'Speed (km/h)',
                    data: speedData,
                    borderColor: '#00bcd4',
                    backgroundColor: 'rgba(0, 188, 212, 0.1)',
                    borderWidth: 2,
                    tension: 0.3,
                    fill: true
                },
                {
                    label: 'Throttle (%)',
                    data: throttleData,
                    borderColor: '#24d29b',
                    backgroundColor: 'rgba(36, 210, 155, 0.05)',
                    borderWidth: 1.5,
                    tension: 0.3,
                    fill: false
                },
                {
                    label: 'Brake (%)',
                    data: brakeData,
                    borderColor: '#ff4772',
                    backgroundColor: 'rgba(255, 71, 114, 0.05)',
                    borderWidth: 1.5,
                    tension: 0.3,
                    fill: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { display: false },
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#90a4ae' }
                }
            },
            plugins: {
                legend: {
                    labels: { color: '#f1f3f9', font: { family: 'Outfit' } }
                }
            }
        }
    });

    // 2. Latency Comparison Chart
    const ctxLatency = document.getElementById("chart-latency").getContext("2d");
    latencyChart = new Chart(ctxLatency, {
        type: 'bar',
        data: {
            labels: localLatencyLabels,
            datasets: [
                {
                    label: 'Routed Reconciler (Local Edge)',
                    data: bertLatencyData,
                    backgroundColor: '#24d29b',
                    borderColor: '#24d29b',
                    borderWidth: 1
                },
                {
                    label: 'Fireworks AI (Cloud LLM)',
                    data: gemmaLatencyData,
                    backgroundColor: 'rgba(0, 188, 212, 0.6)',
                    borderColor: '#00bcd4',
                    borderWidth: 1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { display: false },
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#90a4ae' }
                }
            },
            plugins: {
                legend: {
                    labels: { color: '#f1f3f9', font: { family: 'Outfit' } }
                }
            }
        }
    });
}

// Update telemetry chart labels based on data source
function updateChartLabels(source) {
    currentSource = source;
    const labels = CHART_LABELS[source] || CHART_LABELS["openf1"];
    if (telemetryChart) {
        telemetryChart.data.datasets[0].label = labels[0];
        telemetryChart.data.datasets[1].label = labels[1];
        telemetryChart.data.datasets[2].label = labels[2];
        telemetryChart.update();
    }
}

// Fetch status from Flask on boot
async function checkBackendStatus() {
    try {
        const response = await fetch("/status");
        const data = await response.json();
        
        // Update credentials status tags
        if (data.imports_loaded) {
            statusRouter.textContent = "AerSimulator";
            statusRouter.className = "badge ok";
        } else {
            statusRouter.textContent = "Classical Mock";
            statusRouter.className = "badge info";
        }

        if (data.fireworks_configured) {
            statusFireworks.textContent = "Fireworks Configured";
            statusFireworks.className = "badge ok";
        } else {
            statusFireworks.textContent = "Local Mock LLM";
            statusFireworks.className = "badge warning";
        }
    } catch (e) {
        console.error("Failed to fetch backend status:", e);
    }
}

// Post configuration changes to backend
async function updateBackendConfig(payload) {
    try {
        await fetch("/config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
    } catch (e) {
        console.error("Failed to update backend config:", e);
    }
}

// Connect to the Flask Server Sent Events (SSE) route
function connectStream() {
    if (eventSource) {
        eventSource.close();
    }

    eventSource = new EventSource("/stream");

    eventSource.onmessage = function(event) {
        const payload = JSON.parse(event.data);
        const srcData = payload.original.data;
        
        // Update context label
        if (statusDriver) {
            const ctxLabel = srcData.driver || srcData.station_id || srcData.mission || srcData.symbol || "Unknown";
            statusDriver.textContent = ctxLabel;
        }
        
        // 1. Update JSON Diff Viewer
        codeOriginal.textContent = JSON.stringify(payload.original.data, null, 2);
        if (payload.drifted) {
            codeDrifted.textContent = JSON.stringify(payload.drifted.data, null, 2);
            codeReconciled.textContent = JSON.stringify(payload.reconciled.data, null, 2);
        } else {
            codeDrifted.textContent = "// Payload Intact (No drift injected)";
            codeReconciled.textContent = "// Payload Intact (No reconciliation needed)";
        }

        // 2. Update Quantum Router Info
        const routedTo = payload.routing.decision;
        textRoutingDecision.textContent = routedTo;
        
        // Add styling based on decision tier
        if (routedTo === "passthrough") {
            textRoutingDecision.className = "decision-badge";
        } else if (routedTo === "bert") {
            textRoutingDecision.className = "decision-badge ok";
        } else {
            textRoutingDecision.className = "decision-badge info"; // LLM Cloud Tier
        }

        textRoutingConfidence.textContent = `${(payload.routing.confidence * 100).toFixed(1)}%`;
        textRoutingLatency.textContent = `${payload.routing.latency_ms.toFixed(2)} ms`;
        progressBarRouter.style.width = `${payload.routing.confidence * 100}%`;

        // 3. Update GPU metrics
        textGpuTemp.textContent = `${payload.gpu.temperature_c.toFixed(1)}°C`;
        textGpuPower.textContent = `${payload.gpu.power_w.toFixed(1)} W`;
        textGpuVram.textContent = `${payload.gpu.vram_mb.toFixed(1)} MB`;
        if (textGpuPlatform && payload.gpu.platform) {
            textGpuPlatform.textContent = "Platform: " + payload.gpu.platform;
        }

        // 4. Update real-time charts history — pick first 3 numeric fields
        const numericVals = Object.values(srcData).filter(v => typeof v === 'number');
        chartLabels.push(payload.packet_idx);
        speedData.push(numericVals[0] || 0);
        throttleData.push(numericVals[1] || 0);
        brakeData.push(numericVals[2] || 0);

        if (chartLabels.length > chartHistoryLimit) {
            chartLabels.shift();
            speedData.shift();
            throttleData.shift();
            brakeData.shift();
        }
        telemetryChart.update();

        // 5. Update latency profiles comparison chart
        localLatencyLabels.push(payload.packet_idx);
        
        if (routedTo in ["gemma_e4b", "nemotron"]) {
            gemmaLatencyData.push(payload.routing.latency_ms);
            bertLatencyData.push(0);
        } else {
            bertLatencyData.push(payload.routing.latency_ms);
            gemmaLatencyData.push(0);
        }

        if (localLatencyLabels.length > chartHistoryLimit) {
            localLatencyLabels.shift();
            gemmaLatencyData.shift();
            bertLatencyData.shift();
        }
        latencyChart.update();
    };

    eventSource.onerror = function() {
        console.error("SSE connection closed or lost. Retrying...");
        eventSource.close();
        setTimeout(connectStream, 2000);
    };
}

// Interactive control events listener
function registerListeners() {
    if (sourceSelect) {
        sourceSelect.addEventListener("change", function() {
            updateBackendConfig({ data_source: this.value });
            updateChartLabels(this.value);
            // Reconnect SSE to pick up new data source
            connectStream();
            // Update context dropdown based on source
            const contexts = {
                "openf1": ["Fernando Alonso", "Lewis Hamilton", "Max Verstappen", "Charles Leclerc"],
                "openmeteo": ["STATION_42", "STATION_07", "STATION_15", "STATION_88"],
                "spacex": ["Starlink-6", "Crew-9", "GPS-III-7", "Transporter-11"],
                "finnhub": ["AAPL", "TSLA", "NVDA", "AMZN"]
            };
            const labels = {
                "openf1": "Select Driver",
                "openmeteo": "Select Station",
                "spacex": "Select Mission",
                "finnhub": "Select Symbol"
            };
            if (driverSelect) {
                driverSelect.innerHTML = "";
                (contexts[this.value] || []).forEach(ctx => {
                    const opt = document.createElement("option");
                    opt.value = ctx;
                    opt.textContent = ctx;
                    driverSelect.appendChild(opt);
                });
                const labelEl = driverSelect.closest(".control-group").querySelector("label");
                if (labelEl) labelEl.textContent = labels[this.value] || "Context";
            }
            // Clear chart history on source switch
            chartLabels.length = 0;
            speedData.length = 0;
            throttleData.length = 0;
            brakeData.length = 0;
            localLatencyLabels.length = 0;
            gemmaLatencyData.length = 0;
            bertLatencyData.length = 0;
        });
    }

    driverSelect.addEventListener("change", function() {
        statusDriver.textContent = this.value.split(" ")[1];
        updateBackendConfig({ active_driver: this.value });
    });

    sliderDrift.addEventListener("input", function() {
        const percent = Math.round(this.value * 100);
        driftValueText.textContent = `${percent}%`;
    });

    sliderDrift.addEventListener("change", function() {
        updateBackendConfig({ drift_rate: this.value });
    });

    // Chaos selection radios
    const radios = document.getElementsByName("chaos-type");
    radios.forEach(radio => {
        radio.addEventListener("change", function() {
            if (this.checked) {
                updateBackendConfig({ chaos_type: this.value });
            }
        });
    });

    // Pause/Play Gateway button
    btnPause.addEventListener("click", function() {
        isRunning = !isRunning;
        if (isRunning) {
            this.textContent = "Pause Gateway";
            this.className = "btn btn-primary";
            updateBackendConfig({ is_running: true });
        } else {
            this.textContent = "Resume Gateway";
            this.className = "btn btn-pause-active";
            updateBackendConfig({ is_running: false });
        }
    });

    // API key handlers
    if (btnSetKey) {
        btnSetKey.addEventListener("click", async function() {
            const key = apiKeyInput.value.trim();
            if (!key) return;
            try {
                const resp = await fetch("/api-key", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ api_key: key })
                });
                const data = await resp.json();
                if (data.fireworks_configured) {
                    statusFireworks.textContent = "Gemma Active";
                    statusFireworks.className = "badge ok";
                    apiKeyInput.value = "";
                }
            } catch (e) {
                console.error("Failed to set API key:", e);
            }
        });
    }

    if (btnClearKey) {
        btnClearKey.addEventListener("click", async function() {
            try {
                await fetch("/api-key", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ api_key: "" })
                });
                statusFireworks.textContent = "No API Key";
                statusFireworks.className = "badge warning";
                apiKeyInput.value = "";
            } catch (e) {
                console.error("Failed to clear API key:", e);
            }
        });
    }
}

// Initial Boot
document.addEventListener("DOMContentLoaded", () => {
    initCharts();
    checkBackendStatus();
    connectStream();
    registerListeners();
});
