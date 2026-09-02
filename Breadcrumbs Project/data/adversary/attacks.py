"""
Adversary attack models and artifact generators (§7).

Implements the 8 canonical adversary attacks against the ledger axis:
1. retroactive_edit: stealth modifications vs declared benign amendments
2. withholding: disclosing M < N documents, hiding anomalous records
3. backdated_seal: period closed late but timestamped as closed on time
4. witness_collusion: honest vs lazy vs colluding counter-signatories
5. equivocation: divergent history views served to distinct consortium members
6. cross_document_fraud: paired cross-record inconsistency with valid single docs
7. duplicate_submission: double commitments across channels or doc IDs
8. late_amendment_abuse: high frequency trivial amendments masking a payload
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class AdversaryEvent:
    """A single discrete adversary event logged in adversary_trace.json."""

    event_id: str
    timestamp: str
    site: str
    period: str
    attack_type: str
    target_doc_id: str | None
    is_malicious: bool
    difficulty: float
    parameters: dict[str, Any]
    ground_truth_verdict: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "site": self.site,
            "period": self.period,
            "attack_type": self.attack_type,
            "target_doc_id": self.target_doc_id,
            "is_malicious": self.is_malicious,
            "difficulty": round(self.difficulty, 4),
            "parameters": self.parameters,
            "ground_truth_verdict": self.ground_truth_verdict,
        }


class AttackFactory:
    """Constructs attack scenarios and coordinates dual document generation."""

    @staticmethod
    def create_retroactive_edit(
        doc_id: str,
        site: str,
        period: str,
        original_rows: list[dict[str, Any]],
        difficulty: float,
        is_benign: bool,
        rng: np.random.Generator,
    ) -> tuple[list[dict[str, Any]], AdversaryEvent]:
        """Generate a modified version of an existing document and record the delta."""
        mod_rows = [dict(r) for r in original_rows]
        target_idx = int(rng.integers(0, len(mod_rows)))
        r = mod_rows[target_idx]

        if "net_pay_bdt" in r:
            # Edit payroll row
            old_net = float(r["net_pay_bdt"])
            # If careful/difficult, change is subtle
            delta = round(old_net * (0.02 if difficulty > 0.6 else 0.15), 2)
            new_net = old_net - delta if is_benign else old_net + delta
            r["net_pay_bdt"] = round(new_net, 2)
            delta_desc = {"field": "net_pay_bdt", "old": old_net, "new": round(new_net, 2)}
        elif "closing_kg" in r:
            old_kg = float(r["closing_kg"])
            new_kg = round(old_kg * 0.95, 2)
            r["closing_kg"] = new_kg
            delta_desc = {"field": "closing_kg", "old": old_kg, "new": new_kg}
        else:
            delta_desc = {"field": "notes", "old": r.get("notes", ""), "new": "Corrected record entry"}
            r["notes"] = "Corrected record entry"

        event = AdversaryEvent(
            event_id=f"adv-edit-{doc_id}",
            timestamp=f"{period}-28T18:00:00Z",
            site=site,
            period=period,
            attack_type="retroactive_edit",
            target_doc_id=doc_id,
            is_malicious=not is_benign,
            difficulty=difficulty,
            parameters={
                "target_row": target_idx,
                "delta": delta_desc,
                "declared_as_amendment": is_benign,
            },
            ground_truth_verdict="benign_amendment" if is_benign else "detected_unauthorized_mutation",
        )
        return mod_rows, event

    @staticmethod
    def create_withholding(
        period_docs: list[Any],
        site: str,
        period: str,
        difficulty: float,
        rng: np.random.Generator,
    ) -> tuple[list[str], list[str], AdversaryEvent]:
        """
        Partition a period's documents into disclosed and withheld subsets.
        Anomalous documents are preferentially withheld.
        """
        all_ids = [d.doc_id for d in period_docs]
        anomalous_ids = [d.doc_id for d in period_docs if d.label == 1]
        clean_ids = [d.doc_id for d in period_docs if d.label == 0]

        # Adversary attempts to hide anomalies
        if anomalous_ids:
            withheld_ids = list(anomalous_ids)
            # If careful/high difficulty, withhold some clean docs too to disguise count change
            if difficulty > 0.5 and len(clean_ids) > 2:
                n_extra = min(len(clean_ids) // 4, 2)
                withheld_ids.extend([clean_ids[i] for i in range(n_extra)])
        else:
            # Randomly withhold 1 clean document
            withheld_ids = [clean_ids[0]] if clean_ids else []

        disclosed_ids = [did for did in all_ids if did not in withheld_ids]

        event = AdversaryEvent(
            event_id=f"adv-withhold-{site}-{period}",
            timestamp=f"{period}-30T23:59:59Z",
            site=site,
            period=period,
            attack_type="withholding",
            target_doc_id=withheld_ids[0] if withheld_ids else None,
            is_malicious=True,
            difficulty=difficulty,
            parameters={
                "total_produced": len(all_ids),
                "total_disclosed": len(disclosed_ids),
                "total_withheld": len(withheld_ids),
                "withheld_doc_ids": withheld_ids,
                "disclosed_doc_ids": disclosed_ids,
            },
            ground_truth_verdict="withholding_violation",
        )
        return disclosed_ids, withheld_ids, event

    @staticmethod
    def create_backdated_seal(
        site: str,
        period: str,
        difficulty: float,
        rng: np.random.Generator,
    ) -> AdversaryEvent:
        """Simulate closing a period late while attempting to forge an on-time seal."""
        claimed_close = f"{period}-28T23:59:59Z"
        days_late = int(rng.integers(5, 25))
        actual_close = f"{period}-28T23:59:59Z + {days_late} days"

        return AdversaryEvent(
            event_id=f"adv-seal-{site}-{period}",
            timestamp=claimed_close,
            site=site,
            period=period,
            attack_type="backdated_seal",
            target_doc_id=None,
            is_malicious=True,
            difficulty=difficulty,
            parameters={
                "claimed_closed_at": claimed_close,
                "actual_closed_at": actual_close,
                "days_late": days_late,
            },
            ground_truth_verdict="backdated_seal_detected",
        )

    @staticmethod
    def create_witness_collusion(
        doc_id: str,
        site: str,
        period: str,
        witness_type: str,  # "honest" | "lazy" | "colluding"
        difficulty: float,
    ) -> AdversaryEvent:
        """Simulate witness counter-signatures across the 3 behavioral profiles."""
        return AdversaryEvent(
            event_id=f"adv-witness-{doc_id}",
            timestamp=f"{period}-20T14:00:00Z",
            site=site,
            period=period,
            attack_type="witness_collusion",
            target_doc_id=doc_id,
            is_malicious=(witness_type == "colluding"),
            difficulty=difficulty,
            parameters={
                "witness_type": witness_type,
                "counter_signatory": "WIT-03",
                "attestation_valid": witness_type != "colluding",
            },
            ground_truth_verdict=f"witness_{witness_type}",
        )

    @staticmethod
    def create_equivocation(
        site: str,
        period: str,
        doc_id: str,
        difficulty: float,
    ) -> AdversaryEvent:
        """Simulate dual history views presented to different consortium participants."""
        return AdversaryEvent(
            event_id=f"adv-equiv-{site}-{period}",
            timestamp=f"{period}-25T10:00:00Z",
            site=site,
            period=period,
            attack_type="equivocation",
            target_doc_id=doc_id,
            is_malicious=True,
            difficulty=difficulty,
            parameters={
                "channel_a_view": f"root_hash_a_{doc_id}",
                "channel_b_view": f"root_hash_b_{doc_id}",
                "fork_block_height": 1420,
            },
            ground_truth_verdict="equivocation_fork_detected",
        )

    @staticmethod
    def create_late_amendment_abuse(
        site: str,
        period: str,
        amendment_count: int,
        difficulty: float,
    ) -> AdversaryEvent:
        """Simulate spamming high volumes of trivial amendments to obscure a fraudulent change."""
        return AdversaryEvent(
            event_id=f"adv-amend-abuse-{site}-{period}",
            timestamp=f"{period}-29T16:00:00Z",
            site=site,
            period=period,
            attack_type="late_amendment_abuse",
            target_doc_id=None,
            is_malicious=True,
            difficulty=difficulty,
            parameters={
                "amendment_frequency": amendment_count,
                "noise_amendments": amendment_count - 1,
                "substantive_amendments": 1,
            },
            ground_truth_verdict="high_frequency_amendment_anomaly",
        )
