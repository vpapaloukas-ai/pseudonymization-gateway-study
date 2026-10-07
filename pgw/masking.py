"""What the gateway hands to the scorers: the payload that would leave, and what the analyzer found."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Detection:
    entity_type: str
    start: int
    end: int
    score: float


@dataclass(frozen=True)
class Masked:
    payload: str
    detections: tuple[Detection, ...]
