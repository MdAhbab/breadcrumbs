"""
Breadcrumbs Synthetic Compliance Corpus Generator Package.

Provides realistic synthetic compliance records and adversary traces for evaluating
permissioned blockchain ledgers and federated continual-learning detectors.
"""

from .anomalies.taxonomy import ANOMALY_KINDS
from .config import CorpusConfig
from .generator import Document, DocumentGenerator, StreamingCorpusGenerator
from .partition import FederatedPartitioner
from .sites import RECORD_TYPES, SITE_KEYS, SITE_PROFILES
from .verify import verify_determinism

__all__ = [
    "ANOMALY_KINDS",
    "CorpusConfig",
    "Document",
    "DocumentGenerator",
    "FederatedPartitioner",
    "RECORD_TYPES",
    "SITE_KEYS",
    "SITE_PROFILES",
    "StreamingCorpusGenerator",
    "verify_determinism",
]
