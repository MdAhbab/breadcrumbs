"""
Anomaly injection package for synthetic compliance records.
"""

from .injector import AnomalyInjector
from .taxonomy import (
    ANOMALY_KINDS,
    RECORD_ANOMALY_COMPATIBILITY,
    WAVE_FOCUS_KINDS,
)

__all__ = [
    "ANOMALY_KINDS",
    "AnomalyInjector",
    "RECORD_ANOMALY_COMPATIBILITY",
    "WAVE_FOCUS_KINDS",
]
