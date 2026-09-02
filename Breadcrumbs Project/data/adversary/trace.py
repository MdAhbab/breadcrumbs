"""
Adversary Trace manager and mutual consistency orchestrator (§7).

Maintains a timeline of adversary actions that are mutually consistent with the
generated documents in the corpus.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ..config import CorpusConfig
from ..sites import SITE_KEYS
from ..timeline import PeriodInfo
from .attacks import AdversaryEvent, AttackFactory


class AdversaryTraceManager:
    """Coordinates attack events and enforces mutual consistency with document artifacts."""

    def __init__(self, config: CorpusConfig):
        self.config = config
        self.events: list[AdversaryEvent] = []

    def record_event(self, event: AdversaryEvent) -> None:
        """Add an event to the chronological adversary trace."""
        self.events.append(event)

    def generate_timeline_attacks(
        self,
        period_info: PeriodInfo,
        period_docs: list[Any],
        rng: np.random.Generator,
    ) -> list[Any]:
        """
        Evaluate and inject adversary attacks for a single period and its documents.

        Returns any additional or modified document versions produced by attacks.
        """
        extra_docs: list[Any] = []
        if not period_docs:
            return extra_docs

        for site_key in SITE_KEYS:
            site_docs = [d for d in period_docs if d.site == site_key]
            if not site_docs:
                continue

            # Check if attack triggers for this site & period
            if float(rng.random()) < self.config.attack_rate:
                attack_choice = int(rng.integers(0, 5))
                difficulty = self.config.attack_difficulty

                if attack_choice == 0:
                    # Withholding attack (§7.2)
                    disclosed_ids, withheld_ids, event = AttackFactory.create_withholding(
                        site_docs, site_key, period_info.period, difficulty, rng
                    )
                    self.record_event(event)
                    # Mark withheld documents
                    for d in site_docs:
                        if d.doc_id in withheld_ids:
                            d.is_withheld = True

                elif attack_choice == 1:
                    # Retroactive edit attack (§7.1)
                    target_doc = site_docs[0]
                    is_benign = float(rng.random()) < self.config.benign_amendment_ratio
                    mod_rows, event = AttackFactory.create_retroactive_edit(
                        target_doc.doc_id, site_key, period_info.period, target_doc.rows, difficulty, is_benign, rng
                    )
                    self.record_event(event)
                    # Create second version of document
                    # In python package adapter, Document class is defined in generator
                    version_doc = type(target_doc)(
                        doc_id=f"{target_doc.doc_id}-v2",
                        record_type=target_doc.record_type,
                        site=target_doc.site,
                        period=target_doc.period,
                        rows=mod_rows,
                        label=0 if is_benign else 1,
                        anomaly_kind="retroactive_edit" if not is_benign else None,
                        anomaly_row=event.parameters.get("target_row"),
                        severity=difficulty,
                        site_key=target_doc.site_key,
                        wave=target_doc.wave,
                        is_withheld=False,
                        version=2,
                    )
                    extra_docs.append(version_doc)

                elif attack_choice == 2:
                    # Backdated seal (§7.3)
                    event = AttackFactory.create_backdated_seal(site_key, period_info.period, difficulty, rng)
                    self.record_event(event)

                elif attack_choice == 3:
                    # Witness collusion (§7.4)
                    target_doc = site_docs[0]
                    witness_type = str(rng.choice(["honest", "lazy", "colluding"], p=[0.5, 0.3, 0.2]))
                    event = AttackFactory.create_witness_collusion(
                        target_doc.doc_id, site_key, period_info.period, witness_type, difficulty
                    )
                    self.record_event(event)

                elif attack_choice == 4:
                    # Late amendment abuse (§7.8)
                    amendment_count = int(rng.integers(15, 60))
                    event = AttackFactory.create_late_amendment_abuse(
                        site_key, period_info.period, amendment_count, difficulty
                    )
                    self.record_event(event)

        return extra_docs

    def to_list(self) -> list[dict[str, Any]]:
        """Serialize all adversary events canonically."""
        return [e.to_dict() for e in self.events]
