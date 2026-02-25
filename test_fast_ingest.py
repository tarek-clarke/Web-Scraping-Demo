import fast_ingest
import torch

# Example telemetry packet (10 channels)
packet = [120.0, 8000.0, 50.0, 500.0, 90.0, 1000.0, 22.0, 1000.0, 80.0, 2.0]
lo = [80.0, 4000.0, 0.0, 100.0, 70.0, 150.0, 19.0, 0.0, 55.0, -6.0]
hi = [360.0, 15500.0, 100.0, 1100.0, 130.0, 2800.0, 28.0, 65535.0, 200.0, 6.0]

try:
    print("PyTorch version:", torch.__version__)
    print("ROCm HIP version:", getattr(torch.version, "hip", None))
    print("CUDA available:", torch.cuda.is_available())
    if torch.cuda.is_available():
        print("GPU device name:", torch.cuda.get_device_name(0))
    else:
        print("No GPU detected or ROCm runtime missing.")

    # Test fast_ingest.normalize
    tensor = fast_ingest.normalize(packet, lo, hi)
    print("Result tensor device:", tensor.device)
    print("Result tensor shape:", tensor.shape)
    print("Result tensor:", tensor)
except Exception as e:
    print("Error during fast_ingest test:", e)
