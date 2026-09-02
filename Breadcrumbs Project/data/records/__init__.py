"""
Record generators for the five compliance record types.
"""

from .chemical import generate_chemical_records
from .maintenance import generate_maintenance_records
from .payroll import generate_payroll_records
from .production import generate_production_records
from .safety import generate_safety_records

__all__ = [
    "generate_payroll_records",
    "generate_safety_records",
    "generate_chemical_records",
    "generate_maintenance_records",
    "generate_production_records",
]
