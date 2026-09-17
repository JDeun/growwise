from __future__ import annotations

import threading
import time


class CircuitOpenError(RuntimeError):
    """Raised when a dependency circuit is open and callers should fall back immediately."""


class FailureCircuit:
    """Small thread-safe consecutive-failure circuit breaker.

    GrowWise treats local AI as optional. After repeated provider failures, requests must stop
    blocking on a dependency that is already known to be unhealthy. The first call after the
    cooldown acts as a half-open probe: success resets the circuit; failure reopens it.
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
        self._lock = threading.Lock()

    def before_call(self) -> None:
        now = time.monotonic()
        with self._lock:
            if self._open_until > now:
                remaining = self._open_until - now
                raise CircuitOpenError(f"dependency circuit is open for another {remaining:.1f}s")
            if self._open_until:
                self._open_until = 0.0

    def record_success(self) -> None:
        with self._lock:
            self._failure_count = 0
            self._open_until = 0.0

    def record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            if self._failure_count >= self.failure_threshold:
                self._open_until = time.monotonic() + self.recovery_seconds
