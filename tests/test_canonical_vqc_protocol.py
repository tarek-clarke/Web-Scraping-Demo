from src.routing.canonical_vqc import (
    DEFAULT_CLASS_NAMES,
    build_unitary_circuit,
    logical_qubit_count,
    output_qubit_count,
    qnn_interpret,
)


def test_eight_route_protocol_uses_all_three_output_bits():
    assert len(DEFAULT_CLASS_NAMES) == 8
    assert output_qubit_count(len(DEFAULT_CLASS_NAMES)) == 3
    assert logical_qubit_count(10, len(DEFAULT_CLASS_NAMES)) == 13


def test_all_three_bit_states_decode_to_routes():
    _, _, _, output_qubits = build_unitary_circuit()
    interpret = qnn_interpret(output_qubits)
    assert interpret(6 << 10) == 6
    assert interpret(7 << 10) == 7
