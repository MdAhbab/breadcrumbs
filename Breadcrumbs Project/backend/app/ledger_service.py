"""
The bridge from HTTP to the chain.

One rule governs this module: it never reimplements a rule that lives in
chaincode. Whether a grant covers a field, whether a model may be promoted,
whether an organisation may commit a record — all of that is decided by the
contract, and this layer's job is to carry the question there and translate the
answer into an HTTP response. A validation shortcut here that "helpfully"
pre-checks a rule would be a second source of truth, and the two would drift.

The consortium is built once per process and held in memory with a SQLite-backed
world state, so the ledger survives a restart of the API.
"""

from __future__ import annotations

import threading
from typing import Any

from model.consortium import GATE_ORGS, Consortium, build
from model.ledger import ChaincodeError

from .config import ROLES, settings

_lock = threading.Lock()
_consortium: Consortium | None = None


def consortium() -> Consortium:
    """The process-wide consortium, built on first use."""
    global _consortium
    with _lock:
        if _consortium is None:
            _consortium = build(db_path=settings.ledger_path)
        return _consortium


def identity_for(role: str):
    return consortium().who(ROLES[role]["identity"])


def doc_endorsers():
    return consortium().endorsers(["ApexTextileMSP", "BVCertificationMSP"])


def gate_endorsers():
    return consortium().endorsers(GATE_ORGS[:3])


class LedgerError(Exception):
    """A chaincode refusal, carried up with its reason intact."""

    def __init__(self, message: str, code: str = "CHAINCODE_REJECTED"):
        super().__init__(message)
        self.message = message
        self.code = code


def invoke(
    channel: str,
    chaincode: str,
    function: str,
    args: dict[str, Any],
    role: str,
    endorsers=None,
    timestamp: str = "2026-08-31T00:00:00Z",
) -> dict[str, Any]:
    """
    Submit a transaction and return what the ledger recorded.

    Both failure modes are surfaced rather than flattened into one: a chaincode
    refusal (the rule said no) and a validation failure (the endorsement policy
    or the read set said no). They mean different things to a user and the
    interface shows different screens for them.
    """
    c = consortium()
    endorsers = endorsers or doc_endorsers()
    try:
        block, result, response = c.network.invoke(
            channel, chaincode, function, args, identity_for(role), endorsers, timestamp
        )
    except ChaincodeError as exc:
        raise LedgerError(str(exc)) from exc

    if not result.valid:
        raise LedgerError(result.reason or result.code, code=result.code)

    return {
        "response": response,
        "tx_id": result.tx_id,
        "block": block.number if block else None,
        "validation": result.code,
    }


def query(
    channel: str, chaincode: str, function: str, args: dict[str, Any], role: str
) -> Any:
    """Read-only. Simulated and discarded; nothing is ordered or committed."""
    try:
        return consortium().network.query(
            channel, chaincode, function, args, identity_for(role)
        )
    except ChaincodeError as exc:
        raise LedgerError(str(exc)) from exc


# -- explorer -------------------------------------------------------------
def chain_summary() -> list[dict[str, Any]]:
    c = consortium()
    out = []
    for name, channel in c.network.channels.items():
        ok, why = channel.verify_chain()
        out.append(
            {
                "channel": name,
                "height": channel.height,
                "head_hash": channel.head.block_hash,
                "integrity_ok": ok,
                "integrity_detail": why,
                "members": channel.config.get("members", []),
            }
        )
    return out


def blocks(channel: str, limit: int = 25, offset: int = 0) -> list[dict[str, Any]]:
    ch = consortium().network.channels[channel]
    selected = list(reversed(ch.blocks))[offset : offset + limit]
    return [
        {
            "number": b.number,
            "block_hash": b.block_hash,
            "previous_hash": b.previous_hash,
            "data_hash": b.data_hash,
            "timestamp": b.timestamp,
            "proposer": b.proposer,
            "transaction_count": len(b.transactions),
            "transactions": [
                {
                    "tx_id": t.tx_id,
                    "chaincode": t.chaincode,
                    "function": t.function,
                    "submitter": t.submitter,
                    "endorsers": sorted({e.msp_id for e in t.endorsements}),
                    "validation": (
                        ch.validation[t.tx_id].code if t.tx_id in ch.validation else "VALID"
                    ),
                    "valid": (
                        ch.validation[t.tx_id].valid if t.tx_id in ch.validation else True
                    ),
                    "reads": [r.key for r in t.read_set],
                    "writes": [w.key for w in t.write_set],
                }
                for t in b.transactions
            ],
        }
        for b in selected
    ]


def block(channel: str, number: int) -> dict[str, Any] | None:
    for b in blocks(channel, limit=10_000):
        if b["number"] == number:
            return b
    return None
