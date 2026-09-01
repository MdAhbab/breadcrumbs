"""
Measurement plumbing: time things, record them, make them reach the report.

The rule this exists to enforce is that no number in the paper is typed by a
human. A benchmark writes JSON, a converter turns JSON into LaTeX macros, and the
document uses the macros. If a measurement has not been taken, the macro is
undefined and the number renders as `??` on the page, where it cannot be missed.
The alternative — a plausible figure typed into a table during a late night — is
how reports end up with numbers nobody can reproduce.

Every result carries the machine it was measured on. A verification time means
nothing without it, and a judge is entitled to know whether "1.4 ms" came from a
workstation or a laptop on battery.
"""

from __future__ import annotations

import json
import platform
import statistics
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# model/bench/harness.py -> model -> Breadcrumbs Project -> repository root.
# The results live beside main.tex because Overleaf takes a flat upload.
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = REPO_ROOT / "results"


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def machine() -> dict[str, Any]:
    """What the numbers were measured on. Goes into every results file."""
    return {
        "platform": platform.platform(),
        "processor": platform.processor() or platform.machine(),
        "python": platform.python_version(),
        "commit": _git_commit(),
    }


@dataclass
class Timing:
    """One measured operation."""

    label: str
    repeats: int
    median_ms: float
    mean_ms: float
    stdev_ms: float
    min_ms: float
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "repeats": self.repeats,
            "median_ms": round(self.median_ms, 6),
            "mean_ms": round(self.mean_ms, 6),
            "stdev_ms": round(self.stdev_ms, 6),
            "min_ms": round(self.min_ms, 6),
            "note": self.note,
        }


def measure(label: str, fn: Callable[[], Any], repeats: int = 20, note: str = "") -> Timing:
    """
    Time a callable. Reports the median, not the mean.

    The median is the honest summary for this kind of measurement: a garbage
    collection pause or an operating system context switch adds an outlier that
    drags a mean around and says nothing about the operation being measured. The
    minimum is reported too, because for pure computation it is the closest thing
    to the true cost.
    """
    samples: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000.0)
    return Timing(
        label=label,
        repeats=repeats,
        median_ms=statistics.median(samples),
        mean_ms=statistics.fmean(samples),
        stdev_ms=statistics.stdev(samples) if len(samples) > 1 else 0.0,
        min_ms=min(samples),
        note=note,
    )


@dataclass
class Results:
    """
    One benchmark's output.

    `values` holds scalars that become LaTeX macros directly — counts, sizes,
    ratios. `timings` holds measured operations. `series` holds anything indexed
    by a parameter, which becomes a table or a plot rather than a macro.
    """

    name: str
    description: str
    values: dict[str, Any] = field(default_factory=dict)
    timings: list[Timing] = field(default_factory=list)
    series: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    caveats: list[str] = field(default_factory=list)

    def value(self, key: str, v: Any, note: str = "") -> None:
        self.values[key] = {"value": v, "note": note}

    def time(self, label: str, fn: Callable[[], Any], repeats: int = 20, note: str = "") -> Timing:
        t = measure(label, fn, repeats, note)
        self.timings.append(t)
        return t

    def caveat(self, text: str) -> None:
        """
        Record something the number does not say.

        Every benchmark in this project carries at least one, because every
        benchmark in this project is measuring a prototype on one machine, and a
        results file that admits nothing invites a reader to assume the worst.
        """
        self.caveats.append(text)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "machine": machine(),
            "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "values": self.values,
            "timings": [t.to_dict() for t in self.timings],
            "series": self.series,
            "caveats": self.caveats,
        }

    def write(self, directory: Path | None = None) -> Path:
        out_dir = directory or RESULTS_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{self.name}.json"
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n")
        return path


def report(results: Results) -> None:
    """Print a human-readable summary, so a run is useful without opening the JSON."""
    print(f"\n=== {results.name} — {results.description}")
    for key, entry in results.values.items():
        note = f"   ({entry['note']})" if entry["note"] else ""
        print(f"  {key:<38} {entry['value']}{note}")
    for t in results.timings:
        print(f"  {t.label:<38} {t.median_ms:>10.4f} ms   (min {t.min_ms:.4f})")
    for name, rows in results.series.items():
        print(f"  series {name}: {len(rows)} rows")
    for c in results.caveats:
        print(f"  caveat: {c}")
