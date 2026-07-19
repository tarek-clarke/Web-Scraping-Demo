#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator

def run_test():
    sim = AerSimulator()
    shots = 100
    
    # Create two simple test circuits (2 qubits each for simplicity)
    qc1 = QuantumCircuit(2, 2)
    qc1.x(0)
    qc1.measure([0, 1], [0, 1])  # Result should be '01' (qiskit reads c1 c0, so 01 means q0 is 1, q1 is 0)

    qc2 = QuantumCircuit(2, 2)
    qc2.x(1)
    qc2.measure([0, 1], [0, 1])  # Result should be '10'
    
    # Run normally
    j1 = sim.run(transpile(qc1, sim), shots=shots).result().get_counts()
    j2 = sim.run(transpile(qc2, sim), shots=shots).result().get_counts()
    print("Sequential run counts:")
    print("qc1:", j1)
    print("qc2:", j2)
    
    # Now pack them into a 4 qubit circuit
    packed_qc = QuantumCircuit(4, 4)
    packed_qc.compose(qc1, qubits=[0, 1], clbits=[0, 1], inplace=True)
    packed_qc.compose(qc2, qubits=[2, 3], clbits=[2, 3], inplace=True)
    
    # Run packed
    packed_counts = sim.run(transpile(packed_qc, sim), shots=shots).result().get_counts()
    print("\nPacked run total counts:", packed_counts)
    
    # Unpack counts
    c1_counts = {}
    c2_counts = {}
    
    for bitstring, count in packed_counts.items():
        # Qiskit bitstrings are big-endian (c3 c2 c1 c0)
        # c3 c2 comes from qc2, c1 c0 comes from qc1
        c2_bits = bitstring[:2]
        c1_bits = bitstring[2:]
        
        c1_counts[c1_bits] = c1_counts.get(c1_bits, 0) + count
        c2_counts[c2_bits] = c2_counts.get(c2_bits, 0) + count
        
    print("\nUnpacked counts:")
    print("qc1:", c1_counts)
    print("qc2:", c2_counts)
    
    assert c1_counts == j1
    assert c2_counts == j2
    print("\n✅ Packing logic verified successfully!")

if __name__ == '__main__':
    run_test()
