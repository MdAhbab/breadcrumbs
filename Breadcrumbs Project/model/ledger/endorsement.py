"""
Endorsement policies: how many, and which, organisations must agree.

This is the mechanism that makes "no single participant can decide" true rather
than aspirational. A policy is a small expression tree:

    OutOf(3, ["ApexTextileMSP", "NoorGarmentsMSP", "BVCertificationMSP",
              "PrimarkSourcingMSP", "BGMEAConsortiumMSP"])

    AND(OR("ApexTextileMSP", "NoorGarmentsMSP"), "BVCertificationMSP")

Evaluation counts *distinct organisations*, never distinct signatures. That
distinction is the whole security property. If five signatures from five
employees of one factory satisfied a 3-of-5 policy, the policy would be
decoration. Every satisfied() call below deduplicates by MSP ID first.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .block import Endorsement
from .crypto import load_public, verify
from .identity import MSP


class Policy:
    """Base class. A policy answers one question: is this set of orgs enough?"""

    def satisfied_by(self, orgs: set[str]) -> bool:
        raise NotImplementedError

    def describe(self) -> str:
        raise NotImplementedError

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError


@dataclass
class SignedBy(Policy):
    """Exactly one named organisation."""

    msp_id: str

    def satisfied_by(self, orgs: set[str]) -> bool:
        return self.msp_id in orgs

    def describe(self) -> str:
        return self.msp_id

    def to_dict(self) -> dict[str, Any]:
        return {"type": "SignedBy", "msp_id": self.msp_id}


@dataclass
class OutOf(Policy):
    """n of the listed sub-policies. AND is n=len, OR is n=1."""

    n: int
    rules: list[Policy]

    def satisfied_by(self, orgs: set[str]) -> bool:
        return sum(1 for r in self.rules if r.satisfied_by(orgs)) >= self.n

    def describe(self) -> str:
        inner = ", ".join(r.describe() for r in self.rules)
        if self.n == len(self.rules):
            return f"AND({inner})"
        if self.n == 1:
            return f"OR({inner})"
        return f"{self.n}-of({inner})"

    def to_dict(self) -> dict[str, Any]:
        return {"type": "OutOf", "n": self.n, "rules": [r.to_dict() for r in self.rules]}


def AND(*rules: Policy | str) -> OutOf:
    parsed = [SignedBy(r) if isinstance(r, str) else r for r in rules]
    return OutOf(len(parsed), parsed)


def OR(*rules: Policy | str) -> OutOf:
    parsed = [SignedBy(r) if isinstance(r, str) else r for r in rules]
    return OutOf(1, parsed)


def NOutOf(n: int, rules: Iterable[Policy | str]) -> OutOf:
    parsed = [SignedBy(r) if isinstance(r, str) else r for r in rules]
    return OutOf(n, parsed)


def policy_from_dict(d: dict[str, Any]) -> Policy:
    if d["type"] == "SignedBy":
        return SignedBy(d["msp_id"])
    return OutOf(d["n"], [policy_from_dict(r) for r in d["rules"]])


class EndorsementValidator:
    """
    Checks endorsements against both cryptography and policy.

    Order matters. Signatures are verified before the policy is evaluated, so a
    forged signature can never contribute its organisation to the count.
    """

    def __init__(self, msp: MSP):
        self.msp = msp

    def valid_orgs(
        self, payload: dict[str, Any], endorsements: list[Endorsement]
    ) -> tuple[set[str], list[str]]:
        """
        Returns (organisations with at least one good signature, rejection notes).
        """
        good: set[str] = set()
        notes: list[str] = []
        for e in endorsements:
            try:
                pub = load_public(e.public_key)
            except ValueError:
                notes.append(f"{e.identity_id}: malformed public key")
                continue
            if not verify(pub, payload, e.signature):
                notes.append(f"{e.identity_id}: signature does not verify")
                continue
            if e.msp_id not in self.msp.authorities:
                notes.append(f"{e.identity_id}: unknown MSP {e.msp_id}")
                continue
            good.add(e.msp_id)
        return good, notes

    def check(
        self, payload: dict[str, Any], endorsements: list[Endorsement], policy: Policy
    ) -> tuple[bool, str]:
        """Returns (ok, reason)."""
        orgs, notes = self.valid_orgs(payload, endorsements)
        if not policy.satisfied_by(orgs):
            got = ", ".join(sorted(orgs)) or "none"
            detail = f" ({'; '.join(notes)})" if notes else ""
            return False, f"policy {policy.describe()} not satisfied by [{got}]{detail}"
        return True, ""
