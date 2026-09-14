from __future__ import annotations

import json
import logging
from collections import defaultdict
from threading import Lock
from typing import Any

SAFE_LOG_FIELDS = {
    "correlation_id",
    "dependency",
    "duration_ms",
    "error_type",
    "method",
    "model",
    "route",
    "source",
    "stack_trace",
    "status",
}


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: str | int | float,
) -> None:
    unexpected = set(fields) - SAFE_LOG_FIELDS
    if unexpected:
        raise ValueError(f"Unsafe structured log fields: {sorted(unexpected)}")
    payload: dict[str, Any] = {"event": event}
    payload.update(fields)
    logger.log(level, json.dumps(payload, ensure_ascii=True, sort_keys=True))


class MetricsRegistry:
    """Small process-local registry with bounded labels for MVP operations."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: defaultdict[tuple, float] = defaultdict(float)
        self._gauges: defaultdict[tuple, float] = defaultdict(float)
        self._durations: dict[tuple, dict[str, float]] = {}

    @staticmethod
    def _key(name: str, labels: dict[str, str]) -> tuple:
        return (name, *sorted(labels.items()))

    @staticmethod
    def _entry(key: tuple, value: Any) -> dict[str, Any]:
        name, *label_pairs = key
        return {"name": name, "labels": dict(label_pairs), "value": value}

    def increment(self, name: str, amount: float = 1, **labels: str) -> None:
        with self._lock:
            self._counters[self._key(name, labels)] += amount

    def add_gauge(self, name: str, amount: float, **labels: str) -> None:
        with self._lock:
            key = self._key(name, labels)
            self._gauges[key] = max(0, self._gauges[key] + amount)

    def observe(self, name: str, duration_seconds: float, **labels: str) -> None:
        with self._lock:
            key = self._key(name, labels)
            values = self._durations.setdefault(
                key,
                {"count": 0, "sum_seconds": 0, "max_seconds": 0},
            )
            values["count"] += 1
            values["sum_seconds"] += duration_seconds
            values["max_seconds"] = max(values["max_seconds"], duration_seconds)

    def snapshot(self) -> dict[str, list[dict[str, Any]]]:
        with self._lock:
            return {
                "counters": [
                    self._entry(key, value)
                    for key, value in sorted(self._counters.items())
                ],
                "gauges": [
                    self._entry(key, value)
                    for key, value in sorted(self._gauges.items())
                ],
                "durations": [
                    self._entry(key, dict(value))
                    for key, value in sorted(self._durations.items())
                ],
            }


class NullMetrics(MetricsRegistry):
    def __init__(self) -> None:
        pass

    def increment(self, name: str, amount: float = 1, **labels: str) -> None:
        pass

    def add_gauge(self, name: str, amount: float, **labels: str) -> None:
        pass

    def observe(self, name: str, duration_seconds: float, **labels: str) -> None:
        pass

    def snapshot(self) -> dict[str, list[dict[str, Any]]]:
        return {"counters": [], "gauges": [], "durations": []}


NULL_METRICS = NullMetrics()
