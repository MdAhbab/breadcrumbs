"""
Site-correlated realistic messiness and noise generator.

Implements realistic irregularities without breaking document-level or row-level schemas:
- Inconsistent casing in categorical fields
- Trailing whitespace
- Date format permutations (YYYY-MM-DD, DD/MM/YYYY, YYYY/MM/DD)
- Numeric fields stored as formatted strings
- Transliterated Bangla phrases in free-text fields
- Missing/empty optional fields
All scaled by the site's persistent messiness_factor (e.g., Mirpur is noticeably sloppier than Gazipur).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import numpy as np

from .sites import SiteProfile

TRANSLITERATED_BANGLA_NOTES: list[str] = [
    "Thik ache",
    "Chalu kora hoyeche",
    "Shongshodhon proyojon",
    "Agami mashe abar dekhte hobe",
    "Bhalo ache, kono shomoshya nai",
    "Kaj cholche, taratari sesh hobe",
    "Khub bhalo obostha",
    "Notun part lagano hoyeche",
    "Karkhana porishkar kora hoyeche",
    "Machine running smoothly",
    "Routine inspection passed",
    "Need urgent replacement next week",
]


class MessinessEngine:
    """Applies realistic industrial noise to rows in a deterministic, site-correlated manner."""

    def __init__(self, base_rate: float = 0.15):
        self.base_rate = base_rate

    def should_apply(self, site: SiteProfile, rng: np.random.Generator, multiplier: float = 1.0) -> bool:
        """Evaluate if noise should be applied based on site discipline and base rate."""
        threshold = self.base_rate * site.messiness_factor * multiplier
        return float(rng.random()) < min(threshold, 0.85)

    def format_date(self, date_val: dt.date | str, site: SiteProfile, rng: np.random.Generator) -> str:
        """Format date with occasional realistic formatting variations."""
        if isinstance(date_val, str):
            try:
                date_val = dt.date.fromisoformat(date_val)
            except ValueError:
                return date_val

        # ISO format is default (YYYY-MM-DD)
        if not self.should_apply(site, rng, multiplier=0.6):
            return date_val.isoformat()

        fmt_choice = int(rng.integers(0, 4))
        if fmt_choice == 0:
            return date_val.strftime("%d/%m/%Y")
        elif fmt_choice == 1:
            return date_val.strftime("%Y/%m/%d")
        elif fmt_choice == 2:
            return date_val.strftime("%d-%m-%Y")
        else:
            return date_val.isoformat()

    def format_string(self, text: str, site: SiteProfile, rng: np.random.Generator) -> str:
        """Apply casing or trailing whitespace noise."""
        result = text
        if self.should_apply(site, rng, multiplier=0.4):
            case_choice = int(rng.integers(0, 3))
            if case_choice == 0:
                result = result.upper()
            elif case_choice == 1:
                result = result.title()
            elif case_choice == 2:
                result = result.lower()

        if self.should_apply(site, rng, multiplier=0.5):
            spaces = " " * int(rng.integers(1, 4))
            result = result + spaces
        return result

    def format_number(self, val: float | int, site: SiteProfile, rng: np.random.Generator) -> Any:
        """Occasionally store number as string for messy sites."""
        if self.should_apply(site, rng, multiplier=0.25):
            if isinstance(val, int):
                return str(val)
            return f"{val:.2f}"
        return val

    def sample_note(self, site: SiteProfile, rng: np.random.Generator) -> str:
        """Sample free-text note with occasional transliterated Bangla."""
        if rng.random() > 0.40:
            return ""  # Free text is often empty
        idx = int(rng.integers(0, len(TRANSLITERATED_BANGLA_NOTES)))
        note = TRANSLITERATED_BANGLA_NOTES[idx]
        return self.format_string(note, site, rng)
