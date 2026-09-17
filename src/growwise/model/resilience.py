from __future__ import annotations

import threading
import time
from dataclasses import dataclass


class CircuitOpenError(RuntimeError):
    """Raised when a dependency circuit is open and callers should fall back immediately."""


@dataclass(frozen=True, slots=True)
class CircuitPermit:
    """Identity for one call admitted by a FailureCircuit generation."""

    generation: int
    half_open_probe: bool = False


class FailureCircuit:
    """Thread-safe consecutive-failure circuit breaker with a fenced half-open probe.

    GrowWise treats local AI as optional. After repeated provider failures, requests stop
    blocking on a dependency already known to be unhealthy. Once the cooldown expires, exactly one
    caller is admitted as the half-open probe; concurrent callers fail fast until that probe
    resolves.

    Every admitted call receives a generation permit. Opening or resolving a half-open generation
    invalidates older permits, so a slow call that started before the circuit changed state cannot
    later close, reopen, or otherwise mutate the newer circuit generation.
    """

    def __init__(self, *, failure_threshold: int, recovery_seconds: float) -> None:
        if failure_threshold <= 0:
            raise ValueError("failure_threshold must be positive")
        if recovery_seconds <= 0:
            raise ValueError("recovery_seconds must be positive")
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self._failure_count = 0
        self._open_until = 0.0
        self._half_open_probe_in_flight = False
        self._generation = 0
        self._lock = threading.Lock()

    def before_call(self) -> CircuitPermit:
        now = time.monotonic()
        with self._lock:
            if self._half_open_probe_in_flight:
                raise CircuitOpenError("dependency circuit half-open probe is already in progress")
            if self._open_until > now:
                remaining = self._open_until - now
                raise CircuitOpenError(f"dependency circuit is open for another {remaining:.1f}s")
            if self._open_until:
                # The cooldown expired. Keep this generation reserved for exactly one probe until
                # its matching permit reports success/failure.
                self._half_open_probe_in_flight = True
                return CircuitPermit(self._generation, half_open_probe=True)
            return CircuitPermit(self._generation)

    def record_success(self, permit: CircuitPermit) -> bool:
        """Record success if ``permit`` still belongs to the active generation."""
        with self._lock:
            if permit.generation != self._generation:
                return False
            if self._half_open_probe_in_flight:
                if not permit.half_open_probe:
                    return False
                self._failure_count = 0
                self._open_until = 0.0
                self._half_open_probe_in_flight = False
                self._generation += 1
                return True
            if permit.half_open_probe or self._open_until:
                return False
            self._failure_count = 0
            return True

    def record_failure(self, permit: CircuitPermit) -> bool:
        """Record failure if ``permit`` still belongs to the active generation."""
        with self._lock:
            if permit.generation != self._generation:
                return False
            if self._half_open_probe_in_flight:
                if not permit.half_open_probe:
                    return False
                self._failure_count = self.failure_threshold
                self._open_until = time.monotonic() + self.recovery_seconds
                self._half_open_probe_in_flight = False
                self._generation += 1
                return True
            if permit.half_open_probe or self._open_until:
                return False

            self._failure_count += 1
            if self._failure_count >= self.failure_threshold:
                self._open_until = time.monotonic() + self.recovery_seconds
                self._generation += 1
            return True
