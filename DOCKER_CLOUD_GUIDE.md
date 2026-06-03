# Docker Cloud Deployment Guide

## Quick Start

### 1. Build and Deploy (CUDA)

```bash
cd deploy
./docker-cloud-deploy.sh docker-compose.cloud.yml cuda
```

### 2. Build and Deploy (ROCm)

```bash
cd deploy
./docker-cloud-deploy.sh docker-compose.yml rocm
```

### 3. Build and Deploy (CPU)

```bash
cd deploy
./docker-cloud-deploy.sh docker-compose.yml cpu
```

## Manual Steps

### Build Image

```bash
# CUDA
docker-compose -f docker-compose.cloud.yml build rap-cuda

# ROCm
docker-compose -f docker-compose.yml build rap-rocm

# CPU
docker-compose -f docker-compose.yml build rap-cpu
```

### Download Models

```bash
docker-compose -f docker-compose.cloud.yml run --rm rap-cuda bash -c "
    cd /app/models &&
    curl -L -O https://pub-66196916eecb44259146d96cf3604b80.r2.dev/models/gemma4-e4b-it.gguf &&
    curl -L -O https://pub-66196916eecb44259146d96cf3604b80.r2.dev/models/gemma4-31b-gguf.gguf
"
```

### Run Ingestion

```bash
docker-compose -f docker-compose.cloud.yml run --rm rap-cuda bash -c "
    cd /app/go/ingestion && go run main.go
"
```

### Run Matrix

```bash
docker-compose -f docker-compose.cloud.yml up rap-cuda
```

### Copy Results

```bash
docker cp rap-cuda-cloud:/app/data/reports ./data/reports
```

## Cloud Provider Setup

### AWS (EC2 with NVIDIA GPU)

```bash
# Launch p3.2xlarge (V100) or g5.xlarge (A10G)
aws ec2 run-instances \
    --image-id ami-0c55b159cbfafe1f0 \
    --instance-type g5.xlarge \
    --key-name your-key \
    --security-group-ids sg-xxx

# SSH and install Docker + NVIDIA Container Toolkit
ssh -i your-key.pem ubuntu@<ip>
sudo apt-get update
sudo apt-get install -y docker.io nvidia-container-toolkit
sudo systemctl restart docker
sudo usermod -aG docker $USER

# Clone and run
git clone https://github.com/tarek-clarke/resilient-rap-framework.git
cd resilient-rap-framework
git checkout domain_testing
cd deploy
./docker-cloud-deploy.sh docker-compose.cloud.yml cuda
```

### GCP (Compute Engine with GPU)

```bash
# Create VM with T4 or A100
gcloud compute instances create rap-vm \
    --zone=us-central1-a \
    --machine-type=n1-standard-8 \
    --accelerator=type=nvidia-tesla-t4,count=1 \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --maintenance-policy=TERMINATE

# SSH and install Docker + NVIDIA drivers
gcloud compute ssh rap-vm --zone=us-central1-a
sudo apt-get update
sudo apt-get install -y docker.io nvidia-container-toolkit
sudo systemctl restart docker
sudo usermod -aG docker $USER

# Clone and run
git clone https://github.com/tarek-clarke/resilient-rap-framework.git
cd resilient-rap-framework
git checkout domain_testing
cd deploy
./docker-cloud-deploy.sh docker-compose.cloud.yml cuda
```

### Azure (VM with GPU)

```bash
# Create NC6s_v3 (V100) or NC4as_T4_v3 (T4)
az vm create \
    --resource-group myResourceGroup \
    --name rap-vm \
    --image Canonical:0001-com-ubuntu-server-jammy:22_04-lts:latest \
    --size Standard_NC6s_v3 \
    --admin-username azureuser

# SSH and install Docker + NVIDIA drivers
ssh azureuser@<ip>
sudo apt-get update
sudo apt-get install -y docker.io nvidia-container-toolkit
sudo systemctl restart docker
sudo usermod -aG docker $USER

# Clone and run
git clone https://github.com/tarek-clarke/resilient-rap-framework.git
cd resilient-rap-framework
git checkout domain_testing
cd deploy
./docker-cloud-deploy.sh docker-compose.cloud.yml cuda
```

## Environment Variables

Override batch size and concurrent runs:

```bash
BATCH_SIZE=64 CONCURRENT_RUNS=20 docker-compose -f docker-compose.cloud.yml up rap-cuda
```

## Monitoring

### View Logs

```bash
docker-compose -f docker-compose.cloud.yml logs -f rap-cuda
```

### Check GPU Usage

```bash
docker exec rap-cuda-cloud nvidia-smi
```

### Check Health

```bash
docker inspect --format='{{.State.Health.Status}}' rap-cuda-cloud
```

## Troubleshooting

### CUDA Out of Memory

Reduce batch size:
```bash
BATCH_SIZE=16 docker-compose -f docker-compose.cloud.yml up rap-cuda
```

### Models Not Found

Re-download:
```bash
docker-compose -f docker-compose.cloud.yml run --rm rap-cuda bash -c "
    cd /app/models && ./download_from_r2.sh
"
```

### Container Won't Start

Check logs:
```bash
docker-compose -f docker-compose.cloud.yml logs rap-cuda
```

### GPU Not Detected

Verify NVIDIA Container Toolkit:
```bash
docker run --rm --gpus all nvidia/cuda:12.3.0-base-ubuntu22.04 nvidia-smi
```

## Cost Estimates

| Provider | Instance | GPU | Cost/Hour | Matrix Time | Total Cost |
|----------|----------|-----|-----------|-------------|------------|
| AWS | g5.xlarge | A10G | $1.01 | 30 min | $0.51 |
| AWS | p3.2xlarge | V100 | $3.06 | 25 min | $1.28 |
| GCP | n1-standard-8 + T4 | T4 | $0.95 | 35 min | $0.55 |
| Azure | NC6s_v3 | V100 | $3.06 | 25 min | $1.28 |

## Cleanup

```bash
# Stop containers
docker-compose -f docker-compose.cloud.yml down

# Remove volumes
docker-compose -f docker-compose.cloud.yml down -v

# Remove images
docker rmi resilient-rap:cuda
```
