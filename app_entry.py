# Entrypoint for Docker container to support 'src' imports
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

if __name__ == "__main__":
    from src.circuit_breaker import TelemetryCircuitBreaker
    print("OK")
