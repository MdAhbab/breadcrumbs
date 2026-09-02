"""
Anomaly Taxonomy and metadata definitions (§3).

The 9 canonical anomaly kinds:
- arithmetic: stated total does not equal sum of components (graded magnitude)
- checksum: certificate ID or CAS number fails its check digit
- overtime: monthly overtime exceeds the 48-hour statutory ceiling
- backdating: document signed before the event it certifies
- outlier: value sits far from the site's own established normal
- duplication: same worker or machine appears multiple times with conflicting records
- roundness: implausibly round numbers clustered across rows (fabrication tell)
- benford: first-digit distribution deviates from Benford's law
- cross_inconsistency: internally consistent document contradicts another document of the same period
"""

from __future__ import annotations

ANOMALY_KINDS = (
    "arithmetic",
    "checksum",
    "overtime",
    "backdating",
    "outlier",
    "duplication",
    "roundness",
    "benford",
    "cross_inconsistency",
)

# Wave focus mapping (§4)
WAVE_FOCUS_KINDS: dict[int, tuple[str, ...]] = {
    1: ("arithmetic", "overtime", "duplication", "roundness"),
    2: ("checksum", "backdating", "benford"),
    3: ("arithmetic", "outlier", "cross_inconsistency"),
}

# Record type compatibility mapping
RECORD_ANOMALY_COMPATIBILITY: dict[str, tuple[str, ...]] = {
    "payroll_register": (
        "arithmetic",
        "overtime",
        "outlier",
        "duplication",
        "roundness",
        "benford",
        "cross_inconsistency",
    ),
    "safety_inspection": (
        "checksum",
        "backdating",
        "outlier",
        "duplication",
    ),
    "chemical_inventory": (
        "arithmetic",
        "checksum",
        "outlier",
        "roundness",
    ),
    "machine_maintenance": (
        "backdating",
        "duplication",
        "outlier",
    ),
    "production_output": (
        "outlier",
        "benford",
        "cross_inconsistency",
    ),
}
