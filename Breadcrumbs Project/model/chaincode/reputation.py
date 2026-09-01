"""
reputation chaincode: contribution scores.

Scores weight a participant's influence on aggregation and gate access to the
shared model. They are on-chain because a participant could otherwise be quietly
downgraded by whoever runs the server, which is the same failure the Continuity
Gate exists to prevent.

The report is explicit about a conflict here and this file inherits it. Secure
aggregation hides individual updates and reveals only their sum. Contribution
scoring requires attributing quality to named participants. Trimmed-mean
robustness requires ranking those contributions. The second and third need to see
what the first is designed to hide, so all three cannot hold at once. This
implementation assumes the first deployment's choice: the aggregator can read
updates, and privacy rests on clipping, added noise and locally engineered
features rather than cryptographic hiding.

Scores are integers in basis points, for the same determinism reason as the gate.
"""

from __future__ import annotations

from typing import Any

from ..ledger.network import ChaincodeError, Context

SCORE = "score:"
EVENT = "repevent:"

START_SCORE = 5000  # 50.00, neutral
MAX_SCORE = 10000
MIN_SCORE = 0

# What each event is worth, in basis points.
WEIGHTS = {
    "round_participation": 150,
    "update_accepted": 100,
    "benchmark_contributed": 250,
    "endorsement_provided": 120,
    "update_trimmed_as_outlier": -200,
    "endorsement_disagreed": -150,
    "grant_scope_violation": -600,
    "unavailable_for_round": -100,
    # Witnessing. The asymmetry between these two numbers is the mechanism, not an
    # accident of tuning: attesting honestly earns a little, and attesting to
    # something that turns out to be false costs roughly four years of it. A
    # witness with nothing to lose is a rubber stamp, and a rubber stamp is worse
    # than no witness at all because it looks like a control.
    "witness_attested": 180,
    "witness_of_falsified_record": -800,
    "record_falsified": -1200,
    "disclosure_mismatch": -900,
    # Amending a sealed period is legitimate and sometimes necessary. It is priced
    # rather than forbidden, so that a factory which genuinely finds a record late
    # can declare it, while one that amends constantly pays for the privilege.
    "seal_amended": -120,
}


def _clamp(v: int) -> int:
    return max(MIN_SCORE, min(MAX_SCORE, v))


def register_member(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    """Start a member at a neutral score."""
    ctx.require(
        ctx.msp.org_kind(ctx.caller_msp) == "consortium",
        "only the consortium may register members",
    )
    msp_id = args["msp_id"]
    ctx.require(ctx.get(SCORE + msp_id) is None, f"{msp_id} already registered")
    entry = {
        "msp_id": msp_id,
        "score_bp": START_SCORE,
        "rounds": 0,
        "registered_at": args["timestamp"],
        "history": [],
    }
    ctx.put(SCORE + msp_id, entry)
    return entry


def record_event(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    """
    Apply one scoring event.

    Only the consortium organisation may write these, and every event is kept in
    the member's history so a score can always be explained rather than merely
    asserted.
    """
    ctx.require(
        ctx.msp.org_kind(ctx.caller_msp) == "consortium",
        "only the consortium may record reputation events",
    )
    event_type = args["event_type"]
    ctx.require(event_type in WEIGHTS, f"unknown event type {event_type}")

    entry = ctx.get(SCORE + args["msp_id"])
    ctx.require(entry is not None, f"unknown member {args['msp_id']}")

    delta = WEIGHTS[event_type]
    entry = dict(entry)
    entry["history"] = list(entry["history"]) + [
        {
            "event_type": event_type,
            "delta_bp": delta,
            "round_id": args.get("round_id"),
            "at": args["timestamp"],
        }
    ]
    entry["score_bp"] = _clamp(entry["score_bp"] + delta)
    if event_type == "round_participation":
        entry["rounds"] = entry["rounds"] + 1
    ctx.put(SCORE + args["msp_id"], entry)
    return {"msp_id": args["msp_id"], "score_bp": entry["score_bp"], "delta_bp": delta}


def aggregation_weights(ctx: Context, args: dict[str, Any]) -> dict[str, int]:
    """
    Turn scores into aggregation weights for a named set of participants.

    Weights are returned in basis points summing to 10000, computed with integer
    arithmetic and the remainder given to the highest scorer, so every peer
    derives the identical weighting.
    """
    members: list[str] = sorted(args["participants"])
    scores: list[int] = []
    for m in members:
        entry = ctx.get(SCORE + m)
        ctx.require(entry is not None, f"unknown member {m}")
        # A floor of 1 keeps a zero-scored member in the federation with minimal
        # influence rather than silently dropping it.
        scores.append(max(1, entry["score_bp"]))

    total = sum(scores)
    weights = [s * 10000 // total for s in scores]
    remainder = 10000 - sum(weights)
    if remainder:
        weights[scores.index(max(scores))] += remainder
    return dict(zip(members, weights, strict=True))


def get_score(ctx: Context, args: dict[str, Any]) -> Any:
    return ctx.get(SCORE + args["msp_id"])


def list_scores(ctx: Context, args: dict[str, Any]) -> list[Any]:
    return [v for _, v in ctx.range(SCORE)]


_ROUTES = {
    "register_member": register_member,
    "record_event": record_event,
    "aggregation_weights": aggregation_weights,
    "get_score": get_score,
    "list_scores": list_scores,
}


def reputation(ctx: Context, function: str, args: dict[str, Any]) -> Any:
    fn = _ROUTES.get(function)
    if fn is None:
        raise ChaincodeError(f"reputation has no function {function}")
    return fn(ctx, args)
