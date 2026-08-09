from src.routing.canonical_vqc import (
    ABSTAIN_CLASS_INDEX,
    DEFAULT_CLASS_NAMES,
    build_unitary_circuit,
    logical_qubit_count,
    output_qubit_count,
    qnn_interpret,
)


def test_six_route_protocol_uses_three_output_qubits():
    assert len(DEFAULT_CLASS_NAMES) == 6
    assert output_qubit_count(len(DEFAULT_CLASS_NAMES)) == 3
    assert logical_qubit_count(10, len(DEFAULT_CLASS_NAMES)) == 13


def test_reserved_state_decodes_to_abstain():
    _, _, _, output_qubits = build_unitary_circuit()
    interpret = qnn_interpret(output_qubits)
    assert interpret(6 << 10) == ABSTAIN_CLASS_INDEX
    assert interpret(7 << 10) == ABSTAIN_CLASS_INDEX
