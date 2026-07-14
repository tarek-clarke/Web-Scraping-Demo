#!/usr/bin/env python3
"""
Resilient RAP Framework Interactive Quickstart Bootstrapper
Allows users to configure target HPC hosts (LUMI, Jupiter, Marenostrum 5)
and Quantum backend routing properties (IBM, VLQ, or Local Simulators).
"""

import os
import sys
import subprocess

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    print("=" * 70)
    print("   RESILIENT RAP FRAMEWORK: MULTI-SUPERCOMPUTER QUICKSTART BOOTSTRAP   ")
    print("=" * 70)
    print()

def ask_choice(title, options):
    print(f"--- {title} ---")
    for idx, opt in enumerate(options, 1):
        print(f"  [{idx}] {opt}")
    print()
    while True:
        try:
            choice = input(f"Select option (1-{len(options)}): ").strip()
            val = int(choice)
            if 1 <= val <= len(options):
                return val
        except ValueError:
            pass
        print(f"Invalid input. Please choose a number between 1 and {len(options)}.")

def ask_secret(prompt):
    import getpass
    val = getpass.getpass(prompt).strip()
    return val

def run_command(cmd, env=None):
    try:
        subprocess.run(cmd, env=env, check=True)
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Command failed with exit status {e.returncode}")
        sys.exit(e.returncode)

def main():
    clear_screen()
    print_header()

    # Step 1: Select the Supercomputer Host (where the container or run is executing)
    hpc_choices = [
        "LUMI (AMD Instinct MI250X - ROCm/HIP)",
        "Jupiter (NVIDIA GH200 - CUDA)",
        "Marenostrum 5 (Heterogeneous CUDA/ROCm partitions)",
        "Local Workstation / CPU Fallback"
    ]
    hpc_idx = ask_choice("Select host Supercomputer environment", hpc_choices)
    hpc_selected = hpc_choices[hpc_idx - 1]

    # Step 2: Configure Quantum Backend Execution
    q_choices = [
        "Local Qiskit Aer Simulator (Offline / No Allocation Required)",
        "IBM Quantum Physical QPU (Heron/Marrakesh/Fez - Requires API Key)",
        "VLQ (FiQCI/VTT Lumi-Q 53-qubit Remote Endpoint)"
    ]
    print()
    q_idx = ask_choice("Select Quantum Backend target", q_choices)
    q_selected = q_choices[q_idx - 1]

    # Setup defaults for env variables
    run_env = os.environ.copy()
    run_env["ACCELERATOR_HOST"] = hpc_selected
    
    # Configure variables based on HPC Host selection
    if hpc_idx == 1:
        run_env["ACCELERATOR_TYPE"] = "ROCm"
        run_env["HSA_ENABLE_SDMA"] = "0"
        run_env["CHAOS_DEVICE"] = "cuda:1"  # Target second partition of MI250X
    elif hpc_idx == 2:
        run_env["ACCELERATOR_TYPE"] = "CUDA"
        run_env["CHAOS_DEVICE"] = "cuda:0"
    elif hpc_idx == 3:
        run_env["ACCELERATOR_TYPE"] = "CUDA"  # Default MN5 partition
        run_env["CHAOS_DEVICE"] = "cuda:0"
    else:
        run_env["ACCELERATOR_TYPE"] = "CPU"
        run_env["CHAOS_DEVICE"] = "cpu"

    backend_flag = "aer_simulator"
    if q_idx == 2:
        backend_flag = "ibm_quantum"
        print("\n--- IBM Quantum Authentication ---")
        token = ask_secret("Enter IBM Quantum API Key (input will be hidden): ")
        if not token:
            print("[WARNING] No key provided. Falling back to Local Simulator.")
            backend_flag = "aer_simulator"
        else:
            run_env["QISKIT_IBM_TOKEN"] = token
            run_env["QISKIT_IBM_CHANNEL"] = "ibm_quantum_platform"
    elif q_idx == 3:
        backend_flag = "lumi_q"
        print("\n--- VLQ / Lumi-Q Configuration ---")
        endpoint = input("Enter Lumi-Q FiQCI endpoint URL: ").strip()
        if not endpoint:
            print("[WARNING] No endpoint configured. Falling back to Local Simulator.")
            backend_flag = "aer_simulator"
        else:
            run_env["LUMIQ_ENDPOINT"] = endpoint

    print()
    print("=" * 70)
    print("   CONFIGURATION COMPLETE   ")
    print("=" * 70)
    print(f"Host Hardware  : {hpc_selected}")
    print(f"Quantum Target : {q_selected}")
    print(f"Backend Flag   : --backend {backend_flag}")
    print("=" * 70)
    print()

    run_choices = [
        "Run benchmark matrix now inside Docker container",
        "Generate a SLURM job script for this configuration",
        "Exit and print environment command line"
    ]
    run_idx = ask_choice("Choose next action", run_choices)

    if run_idx == 1:
        # Build Docker command
        docker_cmd = [
            "docker", "run", "--rm", "-it",
            "--device=/dev/kfd", "--device=/dev/dri", # Add GPU access devices
            "-e", f"ACCELERATOR_TYPE={run_env.get('ACCELERATOR_TYPE')}",
            "-e", f"CHAOS_DEVICE={run_env.get('CHAOS_DEVICE')}"
        ]
        if "QISKIT_IBM_TOKEN" in run_env:
            docker_cmd += [
                "-e", f"QISKIT_IBM_TOKEN={run_env['QISKIT_IBM_TOKEN']}",
                "-e", f"QISKIT_IBM_CHANNEL={run_env['QISKIT_IBM_CHANNEL']}"
            ]
        if "LUMIQ_ENDPOINT" in run_env:
            docker_cmd += ["-e", f"LUMIQ_ENDPOINT={run_env['LUMIQ_ENDPOINT']}"]

        docker_cmd += [
            "resilient-rap:latest",
            "python3", "run_matrix.py", "--backend", backend_flag
        ]
        
        print("\nLaunching Docker container:")
        # Hide key in printed command representation
        safe_print_cmd = [c if not c.startswith("QISKIT_IBM_TOKEN=") else "QISKIT_IBM_TOKEN=********" for c in docker_cmd]
        print(" ".join(safe_print_cmd))
        print()
        
        # Execute Docker runner
        run_command(docker_cmd, env=run_env)

    elif run_idx == 2:
        slurm_file = "submit_quickstart.slurm"
        with open(slurm_file, "w") as f:
            f.write("#!/bin/bash\n")
            f.write(f"#SBATCH --job-name=rap-quickstart\n")
            f.write(f"#SBATCH --output=rap_quickstart_%j.out\n")
            f.write(f"#SBATCH --error=rap_quickstart_%j.err\n")
            f.write(f"#SBATCH --nodes=1\n")
            f.write(f"#SBATCH --time=00:30:00\n")
            if hpc_idx == 1:
                f.write(f"#SBATCH --partition=dev-g\n")
                f.write(f"#SBATCH --gpus=1\n")
            elif hpc_idx in (2, 3):
                f.write(f"#SBATCH --partition=gpu\n")
                f.write(f"#SBATCH --gres=gpu:1\n")
            f.write("\n# Load host runtime modules\n")
            if hpc_idx == 1:
                f.write("module load LUMI/25.09\n")
                f.write("module load partition/G\n")
                f.write("module load rocm/6.3.4\n")
                f.write("module load cray-python/3.10.10\n")
            f.write("\nsource .venv-lumi/bin/activate || source .venv/bin/activate\n")
            
            # Write environment exports
            f.write(f"\nexport ACCELERATOR_TYPE=\"{run_env.get('ACCELERATOR_TYPE')}\"\n")
            f.write(f"export CHAOS_DEVICE=\"{run_env.get('CHAOS_DEVICE')}\"\n")
            if "QISKIT_IBM_TOKEN" in run_env:
                f.write(f"export QISKIT_IBM_TOKEN=\"{run_env['QISKIT_IBM_TOKEN']}\"\n")
                f.write(f"export QISKIT_IBM_CHANNEL=\"{run_env['QISKIT_IBM_CHANNEL']}\"\n")
            if "LUMIQ_ENDPOINT" in run_env:
                f.write(f"export LUMIQ_ENDPOINT=\"{run_env['LUMIQ_ENDPOINT']}\"\n")

            f.write(f"\n# Run benchmarks\n")
            f.write(f"python3 run_matrix.py --backend {backend_flag} --max-packets-per-api 500 --phases quantum\n")
        
        print(f"\n[SUCCESS] Generated SLURM script: {slurm_file}")
        print(f"To launch, run: sbatch {slurm_file}")

    else:
        print("\nConfigured environment command:")
        env_str = f"ACCELERATOR_TYPE={run_env.get('ACCELERATOR_TYPE')} CHAOS_DEVICE={run_env.get('CHAOS_DEVICE')} "
        if "QISKIT_IBM_TOKEN" in run_env:
            env_str += f"QISKIT_IBM_TOKEN=******** QISKIT_IBM_CHANNEL=ibm_quantum_platform "
        if "LUMIQ_ENDPOINT" in run_env:
            env_str += f"LUMIQ_ENDPOINT={run_env['LUMIQ_ENDPOINT']} "
        print(f"{env_str}python3 run_matrix.py --backend {backend_flag}")

if __name__ == "__main__":
    main()
