import torch

def test_rocm_gpu():
    print("PyTorch version:", torch.__version__)
    print("ROCm HIP version:", getattr(torch.version, "hip", None))
    print("CUDA available:", torch.cuda.is_available())
    if torch.cuda.is_available():
        print("GPU device name:", torch.cuda.get_device_name(0))
        x = torch.rand(1000, 1000, device="cuda")
        y = torch.rand(1000, 1000, device="cuda")
        z = torch.mm(x, y)
        print("Matrix multiplication successful on GPU.")
    else:
        print("No GPU detected or ROCm runtime missing.")

if __name__ == "__main__":
    test_rocm_gpu()
