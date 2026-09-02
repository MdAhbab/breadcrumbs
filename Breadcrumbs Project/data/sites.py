"""
Site profiles and industrial domain constants for the RMG factory corpus.

Defines the six invented factory sites in Bangladesh with their persistent,
learnable characteristics (worker counts, wage levels, record mix, and noise profiles).
"""

from __future__ import annotations

from dataclasses import dataclass

# Core RMG statutory anchor numbers
BASE_MINIMUM_WAGE_BDT: float = 12_500.0  # RMG minimum wage anchor
LEGAL_OT_HOURS_MONTHLY: float = 48.0     # 12 hours/week * 4 weeks statutory ceiling
HOURLY_RATE_DIVISOR: float = 208.0       # Standard monthly working hours basis (26 days * 8h)
OVERTIME_PAY_MULTIPLIER: float = 2.0     # Statutory overtime pay multiplier (2x normal rate)

# Peak export season months (August through November)
PEAK_SEASON_MONTHS = (8, 9, 10, 11)


@dataclass(frozen=True)
class SiteProfile:
    """Persistent physical and operational parameters for a single factory site."""

    key: str
    name: str
    worker_count: int
    wage_multiplier: float        # Stable multiplier between 1.0x and 1.15x of 12,500 BDT
    peak_overtime_boost: float    # Seasonal multiplier for overtime during peak export months
    peak_production_boost: float  # Seasonal multiplier for production output
    record_type_weights: dict[str, float]  # Relative generation weight per record type
    messiness_factor: float       # Multiplier on field omission, casing variance, and noise
    buyer_codes: list[str]        # Buyer channels placing orders with this factory
    character_description: str

    @property
    def mean_basic_wage(self) -> float:
        """Site baseline mean wage, strictly maintained over the entire 36-month timeline."""
        return BASE_MINIMUM_WAGE_BDT * self.wage_multiplier


# Defined according to §1 of specification
SITE_PROFILES: dict[str, SiteProfile] = {
    "gazipur": SiteProfile(
        key="gazipur",
        name="Gazipur Knitwear Complex",
        worker_count=2000,
        wage_multiplier=1.08,
        peak_overtime_boost=1.45,
        peak_production_boost=1.35,
        record_type_weights={
            "payroll_register": 1.0,
            "safety_inspection": 0.8,
            "chemical_inventory": 0.9,
            "machine_maintenance": 1.0,
            "production_output": 1.1,
        },
        messiness_factor=0.35,  # High discipline, clean record-keeping
        buyer_codes=["BYR-01", "BYR-02", "BYR-05"],
        character_description="Large knitwear, disciplined records, high overtime in peak season",
    ),
    "ashulia": SiteProfile(
        key="ashulia",
        name="Ashulia Mega Apparel Ltd",
        worker_count=3400,
        wage_multiplier=1.14,
        peak_overtime_boost=1.30,
        peak_production_boost=1.30,
        record_type_weights={
            "payroll_register": 1.2,
            "safety_inspection": 1.0,
            "chemical_inventory": 1.1,
            "machine_maintenance": 1.0,
            "production_output": 1.3,
        },
        messiness_factor=0.90,  # Largest, multi-buyer, occasional sloppiness
        buyer_codes=["BYR-01", "BYR-02", "BYR-03", "BYR-04", "BYR-06"],
        character_description="Largest, multi-buyer, most record types, occasional sloppiness",
    ),
    "narayanganj": SiteProfile(
        key="narayanganj",
        name="Narayanganj Spinning & Weaving",
        worker_count=900,
        wage_multiplier=1.02,
        peak_overtime_boost=1.20,
        peak_production_boost=1.15,
        record_type_weights={
            "payroll_register": 0.8,
            "safety_inspection": 0.7,
            "chemical_inventory": 0.6,
            "machine_maintenance": 2.2,  # Heavy maintenance logs on older machinery
            "production_output": 0.8,
        },
        messiness_factor=0.75,
        buyer_codes=["BYR-03", "BYR-05"],
        character_description="Small, older machinery, heavy maintenance logs",
    ),
    "savar": SiteProfile(
        key="savar",
        name="Savar Fashion Works",
        worker_count=1600,
        wage_multiplier=1.05,
        peak_overtime_boost=1.25,
        peak_production_boost=1.20,
        record_type_weights={
            "payroll_register": 0.9,
            "safety_inspection": 1.6,  # Strong safety culture after past incidents
            "chemical_inventory": 0.9,
            "machine_maintenance": 0.9,
            "production_output": 1.0,
        },
        messiness_factor=0.50,
        buyer_codes=["BYR-02", "BYR-04"],
        character_description="Mid-size, strong safety culture after past incidents",
    ),
    "chattogram": SiteProfile(
        key="chattogram",
        name="Chattogram Portside Dyeing & Finishing",
        worker_count=2800,
        wage_multiplier=1.10,
        peak_overtime_boost=1.35,
        peak_production_boost=1.25,
        record_type_weights={
            "payroll_register": 1.0,
            "safety_inspection": 1.0,
            "chemical_inventory": 2.4,  # Chemical-heavy dyeing operations
            "machine_maintenance": 1.1,
            "production_output": 1.1,
        },
        messiness_factor=0.65,
        buyer_codes=["BYR-01", "BYR-04", "BYR-06"],
        character_description="Port-adjacent, chemical-heavy dyeing operations",
    ),
    "mirpur": SiteProfile(
        key="mirpur",
        name="Mirpur Garment Subcontractors",
        worker_count=700,
        wage_multiplier=1.00,
        peak_overtime_boost=1.15,
        peak_production_boost=1.10,
        record_type_weights={
            "payroll_register": 0.7,
            "safety_inspection": 0.6,
            "chemical_inventory": 0.5,
            "machine_maintenance": 0.7,
            "production_output": 0.7,
        },
        messiness_factor=1.60,  # Smallest, thinnest records, most missing fields
        buyer_codes=["BYR-05", "BYR-06"],
        character_description="Smallest, thinnest records, most missing fields",
    ),
}

SITE_KEYS = tuple(sorted(SITE_PROFILES.keys()))
RECORD_TYPES = (
    "payroll_register",
    "safety_inspection",
    "chemical_inventory",
    "machine_maintenance",
    "production_output",
)
