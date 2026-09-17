from __future__ import annotations

import threading

import pytest

from growwise.model import resilience
from growwise.model.resilience import CircuitOpenError, FailureCircuit


def test_failure_circuit_opens_then_allows_half_open_probe(monkeypatch) -> None:
    clock = [100.0]
    monkeypatch.setattr(resilience.time, "monotonic", lambda: clock[0])
    circuit = FailureCircuit(failure_threshold=2, recovery_seconds=5.0)

    first = circuit.before_call()
    assert circuit.record_failure(first)
    second = circuit.before_call()
    assert circuit.record_failure(second)

    with pytest.raises(CircuitOpenError):
        circuit.before_call()

    clock[0] += 5.1
    probe = circuit.before_call()
    assert probe.half_open_probe is True
    assert circuit.record_success(probe)

    normal = circuit.before_call()
    assert normal.half_open_probe is False


def test_failure_circuit_resets_consecutive_failures_after_success(monkeypatch) -> None:
    monkeypatch.setattr(resilience.time, "monotonic", lambda: 200.0)
    circuit = FailureCircuit(failure_threshold=2, recovery_seconds=5.0)

    first = circuit.before_call()
    assert circuit.record_failure(first)
    success = circuit.before_call()
    assert circuit.record_success(success)
    second = circuit.before_call()
    assert circuit.record_failure(second)
    circuit.before_call()


def test_half_open_probe_is_single_flight_across_concurrent_callers(monkeypatch) -> None:
    clock = [300.0]
    monkeypatch.setattr(resilience.time, "monotonic", lambda: clock[0])
    circuit = FailureCircuit(failure_threshold=1, recovery_seconds=5.0)

    initial = circuit.before_call()
    assert circuit.record_failure(initial)
    clock[0] += 5.1

    workers = 8
    barrier = threading.Barrier(workers)
    permits = []
    rejected = []
    guard = threading.Lock()

    def attempt() -> None:
        barrier.wait()
        try:
            permit = circuit.before_call()
        except CircuitOpenError:
            with guard:
                rejected.append(True)
            return
        with guard:
            permits.append(permit)

    threads = [threading.Thread(target=attempt) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=1)
        assert not thread.is_alive()

    assert len(permits) == 1
    assert len(rejected) == workers - 1
    assert permits[0].half_open_probe is True
    assert circuit.record_success(permits[0])


def test_stale_pre_open_completion_cannot_mutate_new_generation(monkeypatch) -> None:
    clock = [400.0]
    monkeypatch.setattr(resilience.time, "monotonic", lambda: clock[0])
    circuit = FailureCircuit(failure_threshold=1, recovery_seconds=5.0)

    opener = circuit.before_call()
    stale = circuit.before_call()
    assert circuit.record_failure(opener)

    assert circuit.record_success(stale) is False
    with pytest.raises(CircuitOpenError):
        circuit.before_call()

    clock[0] += 5.1
    probe = circuit.before_call()
    assert probe.half_open_probe is True

    # A request admitted before the circuit opened must not consume or fail the newer probe.
    assert circuit.record_failure(stale) is False
    with pytest.raises(CircuitOpenError, match="probe"):
        circuit.before_call()
    assert circuit.record_success(probe)


def test_failed_half_open_probe_reopens_for_full_cooldown(monkeypatch) -> None:
    clock = [500.0]
    monkeypatch.setattr(resilience.time, "monotonic", lambda: clock[0])
    circuit = FailureCircuit(failure_threshold=1, recovery_seconds=5.0)

    initial = circuit.before_call()
    assert circuit.record_failure(initial)
    clock[0] += 5.1

    probe = circuit.before_call()
    assert circuit.record_failure(probe)
    with pytest.raises(CircuitOpenError):
        circuit.before_call()

    clock[0] += 5.1
    retry_probe = circuit.before_call()
    assert retry_probe.half_open_probe is True
