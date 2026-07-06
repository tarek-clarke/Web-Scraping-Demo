# 🏎️ ApexFlow AI Gateway — AMD Instinct™ Containerized Deployment

This directory contains the containerized prototype of **ApexFlow AI**—a self-healing, quantum-routed telemetry ingestion gateway built for the **Unicorn Track**.

The application is fully containerized, ROCm-compatible, and integrates local Qiskit quantum simulations with PyTorch models and Fireworks AI endpoints.

---

## 🚀 Quick Start (Dockerized Run on AMD GPUs)

To run the containerized application on your AMD Instinct (MI250X / MI300X) Developer Cloud instance:

### 1. Set up Environment Variables
Export your Fireworks AI API key:
```bash
export FIREWORKS_API_KEY="your_api_key_here"
```

### 2. Build and Launch the Container
Use `docker-compose` to build the image and start the application. This automatically maps the AMD GPU driver paths (`/dev/kfd`, `/dev/dri`) inside the container:
```bash
docker-compose up --build -d
```

### 3. Establish Port Forwarding
Since your AMD Developer Cloud instance runs headless, forward port `5000` to your local laptop:
```bash
ssh -L 5000:127.0.0.1:5000 user@your-amd-developer-cloud-ip
```

### 4. Open the Dashboard
Open your local web browser and navigate to:
👉 **`http://localhost:5000`**

---

## 🛠️ Local Development (Non-Dockerized Run)

If you wish to test the server locally on your development machine:

### 1. Install Dependencies
Make sure you have PyTorch and Qiskit installed:
```bash
pip install Flask openai numpy pandas transformers qiskit qiskit-aer Levenshtein
```

### 2. Run the App
```bash
python3 app.py
```
The server will start at `http://127.0.0.1:5000`.
