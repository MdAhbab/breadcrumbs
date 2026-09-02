"""
Timeline, wave partitioning, seasonality, within-wave drift, and recurrence modeling.

Tracks 36 monthly reporting periods from 2025-01 to 2027-12 across 3 distinct continual learning waves:
- Wave 1 (2025-01 -> 2025-12): Payroll arithmetic & statutory overtime violations
- Wave 2 (2026-01 -> 2026-12): Forged safety certificate check digits & backdating
- Wave 3 (2027-01 -> 2027-12): Chemical misreporting (arithmetic, outliers) & late Wave-1 recurrence
"""

from __future__ import annotations

from dataclasses import dataclass

from .sites import PEAK_SEASON_MONTHS


@dataclass(frozen=True)
class PeriodInfo:
    """Metadata and operational context for a single monthly reporting period."""

    period: str         # "YYYY-MM"
    year: int           # 2025, 2026, 2027
    month: int          # 1..12
    wave: int           # 1, 2, 3
    period_index: int   # 0..35
    is_peak_season: bool
    wave_progress: float  # 0.0 (start of wave) -> 1.0 (end of wave), for within-wave drift
    is_recurrence_window: bool  # True for late Wave 3 (2027-09 to 2027-12)


def generate_timeline(start_period: str = "2025-01", end_period: str = "2027-12") -> list[PeriodInfo]:
    """Generate chronological list of monthly periods with wave and seasonal attributes."""
    start_y, start_m = map(int, start_period.split("-"))
    end_y, end_m = map(int, end_period.split("-"))

    periods: list[PeriodInfo] = []
    idx = 0
    curr_y, curr_m = start_y, start_m

    while (curr_y < end_y) or (curr_y == end_y and curr_m <= end_m):
        period_str = f"{curr_y:04d}-{curr_m:02d}"

        # Wave assignment
        if curr_y <= 2025:
            wave = 1
            wave_progress = (curr_m - 1) / 11.0
        elif curr_y == 2026:
            wave = 2
            wave_progress = (curr_m - 1) / 11.0
        else:
            wave = 3
            wave_progress = (curr_m - 1) / 11.0

        is_peak = curr_m in PEAK_SEASON_MONTHS
        is_recurrence = (wave == 3) and (curr_m >= 9)  # Q4 of 2027

        periods.append(
            PeriodInfo(
                period=period_str,
                year=curr_y,
                month=curr_m,
                wave=wave,
                period_index=idx,
                is_peak_season=is_peak,
                wave_progress=min(max(wave_progress, 0.0), 1.0),
                is_recurrence_window=is_recurrence,
            )
        )

        idx += 1
        curr_m += 1
        if curr_m > 12:
            curr_m = 1
            curr_y += 1

    return periods


# Canonical 36-month timeline
ALL_PERIODS = generate_timeline("2025-01", "2027-12")
PERIOD_MAP = {p.period: p for p in ALL_PERIODS}
