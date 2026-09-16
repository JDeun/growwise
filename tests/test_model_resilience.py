from __future__ import annotations

import pytest

from growwise.model import resilience
from growwise.model.resilience import CircuitOpenError, FailureCircuit


def test_failure_circuit_opens_then_allows_half_open_probe(monkeypatch) -> None:
    clock = [100.0]
    monkeypatch.setattr(resilience.time, "monotonic", lambda: clock[0])
    circuit = FailureCircuit(failure_threshold=2, recovery_seconds=5.0)

    circuit.before_call()
    circuit.record_failure()
    circuit.before_call()
    circuit.record_failure()

    with pytest.raises(CircuitOpenError):
        circuit.before_call()

    clock[0] += 5.1
    circuit.before_call()
    circuit.record_success()
    circuit.before_call()


def test_failure_circuit_resets_consecutive_failures_after_success(monkeypatch) -> None:
    monkeypatch.setattr(resilience.time, "monotonic", lambda: 200.0)
    circuit = FailureCircuit(failure_threshold=2, recovery_seconds=5.0)

    circuit.record_failure()
    circuit.record_success()
    circuit.record_failure()
    circuit.before_call()
