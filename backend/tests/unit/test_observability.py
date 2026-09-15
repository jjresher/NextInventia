import json
import logging

import pytest

from app.observability import MetricsRegistry, log_event


def metric_value(snapshot, category, name, **labels):
    for item in snapshot[category]:
        if item["name"] == name and item["labels"] == labels:
            return item["value"]
    raise AssertionError(f"Metric not found: {category}/{name}/{labels}")


def test_registry_tracks_counters_gauges_and_durations():
    metrics = MetricsRegistry()

    metrics.increment("requests", route="/test")
    metrics.add_gauge("in_flight", 1, dependency="fake")
    metrics.add_gauge("in_flight", -1, dependency="fake")
    metrics.observe("latency", 0.25, dependency="fake")

    snapshot = metrics.snapshot()
    assert metric_value(snapshot, "counters", "requests", route="/test") == 1
    assert metric_value(snapshot, "gauges", "in_flight", dependency="fake") == 0
    duration = metric_value(snapshot, "durations", "latency", dependency="fake")
    assert duration == {"count": 1, "sum_seconds": 0.25, "max_seconds": 0.25}


def test_structured_logs_accept_only_safe_fields(caplog):
    logger = logging.getLogger("test.observability")
    sensitive = "prompt secreto claim privado api_key=abc"

    with caplog.at_level(logging.INFO, logger=logger.name):
        log_event(logger, logging.INFO, "safe_event", status="ok")

    assert json.loads(caplog.records[0].message) == {
        "event": "safe_event",
        "status": "ok",
    }
    assert sensitive not in caplog.text
    with pytest.raises(ValueError, match="Unsafe structured log fields"):
        log_event(logger, logging.INFO, "unsafe", prompt=sensitive)
