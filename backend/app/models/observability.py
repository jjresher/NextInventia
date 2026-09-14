from typing import Literal

from pydantic import BaseModel


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, str]


class ScalarMetric(BaseModel):
    name: str
    labels: dict[str, str]
    value: float


class DurationValue(BaseModel):
    count: int
    sum_seconds: float
    max_seconds: float


class DurationMetric(BaseModel):
    name: str
    labels: dict[str, str]
    value: DurationValue


class MetricsSnapshot(BaseModel):
    counters: list[ScalarMetric]
    gauges: list[ScalarMetric]
    durations: list[DurationMetric]
