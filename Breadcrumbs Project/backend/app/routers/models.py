"""
The learning plane over HTTP — the screens the existing frontend has none of.

Model registry, rounds, benchmarks, memory bank, and the Continuity Gate
decision. The gate endpoint is the one the demo runs from: it takes signed
evaluations and returns exactly what the contract recorded, including the
per-task table the interface renders.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from model.consortium import MODEL_CHANNEL

from .. import ledger_service as ledger
from ..auth import CurrentUser, require_capability

router = APIRouter(prefix="/model", tags=["model"])


def now() -> str:
    """A real timestamp, passed to the contract as an argument."""
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class BenchmarkRequest(BaseModel):
    task_id: str
    benchmark_hash: str = Field(min_length=64, max_length=64)
    contributors: list[str]
    size: int


class RoundRequest(BaseModel):
    round_id: str
    tasks: list[str]
    contributors: list[str]
    memory_bank_hash: str


class GateRequest(BaseModel):
    round_id: str
    candidate_id: str
    candidate_hash: str
    parent_id: str
    new_task: str
    submissions: list[dict[str, Any]]
    gamma_bp: int = 200
    tau_bp: int = 500
    k: int = 3
    delta_bp: int = 100
    # The cumulative bound: how far a task may fall below the best it has ever
    # reached under a promoted model. Optional, because the contract defaults it
    # to twice tau_bp; named here so a consortium can tighten it deliberately
    # rather than only ever getting the default. The contract refuses a sigma
    # below tau, which would make the per-round check unreachable.
    sigma_bp: int | None = None


@router.get("/current")
def current_model(user: CurrentUser) -> dict | None:
    require_capability(user, "read_model")
    return ledger.query(
        MODEL_CHANNEL, "fedmodel", "get_current_model", {}, user.role
    )


@router.get("/registry")
def registry(user: CurrentUser) -> list[dict]:
    """
    Every model version, promoted and rejected alike.

    Rejected versions stay visible with their reason. The audit trail is the
    feature: a registry that only lists what shipped cannot answer "what did you
    try, and why was it refused?".
    """
    require_capability(user, "read_model")
    return ledger.query(MODEL_CHANNEL, "fedmodel", "list_models", {}, user.role)


@router.get("/rounds")
def rounds(user: CurrentUser) -> list[dict]:
    require_capability(user, "read_model")
    return ledger.query(MODEL_CHANNEL, "fedmodel", "list_rounds", {}, user.role)


@router.get("/benchmarks")
def benchmarks(user: CurrentUser) -> list[dict]:
    """
    Committed benchmarks, sealed or revealed.

    A sealed row shows only its hash. That is the anti-gaming design: the
    organisations training in a round do not hold the set they will be judged
    against, so training on the benchmark requires collusion rather than being
    something any member can do quietly.
    """
    require_capability(user, "read_model")
    return ledger.query(MODEL_CHANNEL, "fedmodel", "list_benchmarks", {}, user.role)


@router.get("/decisions/{candidate_id}")
def decision(candidate_id: str, user: CurrentUser) -> dict:
    require_capability(user, "read_model")
    found = ledger.query(
        MODEL_CHANNEL, "fedmodel", "get_decision", {"candidate_id": candidate_id}, user.role
    )
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no decision for {candidate_id}")
    return found


@router.post("/benchmarks", status_code=status.HTTP_201_CREATED)
def commit_benchmark(body: BenchmarkRequest, user: CurrentUser) -> dict:
    require_capability(user, "write_model")
    try:
        return ledger.invoke(
            MODEL_CHANNEL, "fedmodel", "commit_benchmark",
            {**body.model_dump(), "timestamp": now()},
            role=user.role, endorsers=ledger.gate_endorsers(), timestamp=now(),
        )
    except ledger.LedgerError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, exc.message) from exc


@router.post("/rounds", status_code=status.HTTP_201_CREATED)
def open_round(body: RoundRequest, user: CurrentUser) -> dict:
    require_capability(user, "write_model")
    try:
        return ledger.invoke(
            MODEL_CHANNEL, "fedmodel", "open_round",
            {**body.model_dump(), "timestamp": now()},
            role=user.role, endorsers=ledger.gate_endorsers(), timestamp=now(),
        )
    except ledger.LedgerError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, exc.message) from exc


@router.post("/gate")
def evaluate_gate(body: GateRequest, user: CurrentUser) -> dict:
    """
    Run the Continuity Gate.

    The contract does not evaluate the model — it cannot, because the weights are
    off-chain and a floating-point forward pass is not identical across hardware.
    Each endorsing organisation evaluates the candidate itself against the
    committed benchmark and signs what it measured; the contract verifies those
    signatures, requires enough distinct organisations, checks they agree, takes
    medians and applies the threshold rule.
    """
    require_capability(user, "write_model")
    try:
        # An unset sigma_bp must not reach the contract as an explicit null,
        # or `args.get("sigma_bp", default)` finds the key and returns None.
        arguments = {k: v for k, v in body.model_dump().items() if v is not None}
        result = ledger.invoke(
            MODEL_CHANNEL, "fedmodel", "evaluate_gate",
            {**arguments, "timestamp": now()},
            role=user.role, endorsers=ledger.gate_endorsers(), timestamp=now(),
        )
    except ledger.LedgerError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, exc.message) from exc

    decision = result["response"]
    return {
        **decision,
        "tx_id": result["tx_id"],
        "block": result["block"],
        "guarantee": (
            "Promotion required a threshold of independent organisations to have "
            "evaluated the same committed benchmark and signed compatible results. "
            "No single participant, including whoever ran the aggregation, can "
            "promote a model alone."
        ),
    }


@router.get("/high-water")
def high_water(user: CurrentUser) -> dict:
    """
    The best each task has ever scored under a promoted model.

    The gate's cumulative bound is measured against these, and a ceiling nobody
    can inspect is a number the operator could be moving. Serving them is what
    makes the drift figure on a decision checkable rather than assertable.

    `null` for a task means nothing has ever been promoted on it, so there is no
    history to have drifted from — which is a different statement from zero and
    the interface has to say so.
    """
    require_capability(user, "read_model")
    marks = ledger.query(MODEL_CHANNEL, "fedmodel", "list_high_water", {}, user.role)
    rounds_list = ledger.query(MODEL_CHANNEL, "fedmodel", "list_rounds", {}, user.role)
    tasks = sorted({t for r in rounds_list for t in r["tasks"]})
    return {
        "marks": {task: marks.get(task) for task in tasks},
        "note": (
            "A task's high-water mark only moves when a candidate is promoted, so "
            "a rejected submission cannot raise the bar it will be measured "
            "against next time."
        ),
    }


@router.get("/detector")
def detector_status(user: CurrentUser) -> dict:
    """
    What is actually deployed, and how well it is known to work.

    Separate from the registry on purpose. The registry is the ledger's record
    of which candidate the gate promoted; this is the file on disk that the API
    will really load and run. They can disagree — a promoted model that was
    never exported, or an artefact trained after the last gate decision — and a
    product that showed only the first would be reporting an intention rather
    than a deployment.
    """
    require_capability(user, "read_model")
    from .. import detector

    return detector.status()


@router.get("/memory-bank")
def memory_bank(user: CurrentUser) -> dict:
    """
    What the shared memory holds, and the honest label for it.

    The privacy note is served from the model package rather than written here,
    so no interface can quietly soften it.
    """
    require_capability(user, "read_model")
    from model.ai import MemoryBank

    rounds_list = ledger.query(MODEL_CHANNEL, "fedmodel", "list_rounds", {}, user.role)
    return {
        "anchored_hashes": [
            {"round_id": r["round_id"], "memory_bank_hash": r["memory_bank_hash"]}
            for r in rounds_list
        ],
        "privacy_note": MemoryBank.privacy_note(),
        "contains": "cluster centres, spreads and counts per category. No original record.",
    }
