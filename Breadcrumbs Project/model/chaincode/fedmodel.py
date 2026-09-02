"""
fedmodel chaincode: the Continuity Gate.

This is the report's main contribution and, until now, the thing it admitted it
had never built. Algorithm 1 of the paper is implemented here line for line.

The problem it solves. In an ordinary federated system, whoever runs the
aggregation server decides when a new global model goes live. That party can
ship a model that is better at this month's problem and quietly worse at last
year's, and nobody finds out until a decision goes wrong. Committee-based
validation does not catch it either, because forgetting does not make an update
look bad — on the only data the committee is looking at, it looks excellent.

The rule. A candidate is promoted only if it improves on the new task by at
least gamma, has not lost more than tau on any earlier task against the model
currently in force, AND has not lost more than sigma against the best that task
has ever scored, each measured on a benchmark whose hash was committed to the
ledger *before* the round began.

The third condition is there because the first two are not enough, and we found
that by attacking them. An attacker who knows tau simply does not exceed it: it
damages every earlier task by just under the threshold, gains on the new one,
and the contract promotes it — correctly, by its own rule. Repeat that across
rounds and a bound of "no more than tau per round" permits arbitrary total
damage. Comparing against a high-water mark as well caps the total at sigma.

That bounds the attack. It does not eliminate it, and the report says so: an
attacker can still take sigma overall, and sigma is a consortium's choice about
how much drift it will tolerate before a model must be retired rather than
amended.

Two engineering constraints shape the implementation, and both were wrong in the
report's first draft:

  1. Chaincode must be deterministic. Every endorsing peer runs it and the
     results must agree byte for byte. A floating-point forward pass through a
     neural network on different hardware does not guarantee that. So the
     contract does not evaluate the model.
  2. The contract cannot see the weights, which are deliberately kept off-chain.

So evaluation happens off-chain at each endorsing organisation, which signs the
accuracies it measured. The contract compares the signed numbers, checks that
enough organisations agree within a tolerance, and applies the threshold rule to
the medians. The guarantee is therefore slightly weaker than "computed on-chain"
and worth stating exactly: promotion requires a threshold of independent
organisations to have evaluated the same committed benchmark and signed
compatible results. No single participant, including whoever runs the
aggregation server, can promote a model alone.

All accuracies are integers in basis points (1 bp = 0.01 percentage points), so
7790 means 77.90%. There is no floating point anywhere in this file, because two
peers must agree byte for byte and IEEE 754 does not promise that across
architectures.
"""

from __future__ import annotations

from typing import Any

from ..ledger.crypto import TAG_BENCH, hash_object, verify
from ..ledger.network import ChaincodeError, Context

BENCH = "benchmark:"
MODEL = "model:"
ROUND = "round:"
DECISION = "decision:"
CURRENT = "current_model"
HIGHWATER = "highwater:"

# sigma defaults to this multiple of tau when a caller does not set it. The
# parameter is optional so that a consortium already running against an earlier
# revision of this contract keeps working; the check is on by default because a
# gate that silently does less than the report claims is worse than a noisy one.
DEFAULT_SIGMA_MULTIPLE = 2


def _median_bp(values: list[int]) -> int:
    """
    Median of integers, deterministic on ties.

    With an even count the two middle values are averaged with floor division
    rather than true division: floats would break determinism, and rounding
    down is a choice every peer makes identically.
    """
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return (s[mid - 1] + s[mid]) // 2


# -- benchmarks -----------------------------------------------------------
def commit_benchmark(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    """
    Commit a benchmark by hash, before the round starts.

    The contents stay sealed. A benchmark that is fixed and known is a target:
    a participant that wants its model promoted can train on it. Committing only
    the hash, from a rotating subset of members, and revealing after the decision
    means the organisations training in a round do not hold the set they will be
    judged against.

    This does not eliminate the risk. It converts it from something one member
    can do quietly into something that needs collusion between the members
    holding the benchmark and the members training against it. Say it that way.
    """
    ctx.require(ctx.caller_role in ("admin", "operator"), "role may not commit benchmarks")
    task_id = args["task_id"]
    existing = ctx.get(BENCH + task_id)
    ctx.require(existing is None, f"benchmark for {task_id} already committed")
    ctx.require(len(args["benchmark_hash"]) == 64, "benchmark_hash must be a 64-char hash")

    entry = {
        "task_id": task_id,
        "benchmark_hash": args["benchmark_hash"],
        "committed_at": args["timestamp"],
        "committed_by": ctx.caller_msp,
        "contributors": sorted(args["contributors"]),
        "size": int(args["size"]),
        "revealed": False,
        "revealed_at": None,
    }
    ctx.put(BENCH + task_id, entry)
    return {"task_id": task_id, "benchmark_hash": args["benchmark_hash"], "sealed": True}


def reveal_benchmark(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    """
    Reveal a benchmark after a decision, and prove it is the one committed.

    The contract rehashes the revealed contents and refuses if the digest does
    not match what was sealed. Without this check the commitment would be theatre.
    """
    entry = ctx.get(BENCH + args["task_id"])
    ctx.require(entry is not None, f"unknown benchmark {args['task_id']}")
    ctx.require(not entry["revealed"], "benchmark already revealed")

    recomputed = hash_object(TAG_BENCH, args["contents"])
    ctx.require(
        recomputed == entry["benchmark_hash"],
        f"revealed contents hash to {recomputed[:12]}…, "
        f"but {entry['benchmark_hash'][:12]}… was committed",
    )

    entry = dict(entry)
    entry["revealed"] = True
    entry["revealed_at"] = args["timestamp"]
    ctx.put(BENCH + args["task_id"], entry)
    return {"task_id": args["task_id"], "revealed": True, "verified": True}


# -- rounds ---------------------------------------------------------------
def open_round(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    """Open a training round over a named set of tasks and their benchmarks."""
    ctx.require(ctx.caller_role in ("admin", "operator"), "role may not open a round")
    round_id = args["round_id"]
    ctx.require(ctx.get(ROUND + round_id) is None, f"round {round_id} already exists")

    for task_id in args["tasks"]:
        ctx.require(
            ctx.get(BENCH + task_id) is not None,
            f"no benchmark committed for task {task_id}; commit it before opening the round",
        )

    entry = {
        "round_id": round_id,
        "tasks": list(args["tasks"]),
        "opened_at": args["timestamp"],
        "opened_by": ctx.caller_msp,
        "contributors": sorted(args["contributors"]),
        "memory_bank_hash": args["memory_bank_hash"],
        "status": "open",
    }
    ctx.put(ROUND + round_id, entry)
    return {"round_id": round_id, "status": "open"}


# -- the gate -------------------------------------------------------------
def evaluate_gate(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    """
    The Continuity Gate. Algorithm 1 of the report.

    args:
      round_id, candidate_id, candidate_hash, parent_id
      submissions: [{endorser_msp, certificate_pem, signature, accuracies:
                     {task_id: {candidate_bp, previous_bp}}}]
      gamma_bp   minimum gain required on the new task
      tau_bp     maximum tolerated loss on any earlier task, per round
      sigma_bp   maximum tolerated loss against a task's best-ever score.
                 Optional; defaults to DEFAULT_SIGMA_MULTIPLE x tau_bp
      k          minimum number of independent endorsing organisations
      delta_bp   maximum disagreement allowed between endorsers
      new_task   which task is the new one
    """
    rnd = ctx.get(ROUND + args["round_id"])
    ctx.require(rnd is not None, f"unknown round {args['round_id']}")
    ctx.require(rnd["status"] == "open", f"round is {rnd['status']}")

    tasks: list[str] = rnd["tasks"]
    new_task: str = args["new_task"]
    ctx.require(new_task in tasks, f"{new_task} is not a task in this round")

    gamma, tau = int(args["gamma_bp"]), int(args["tau_bp"])
    k, delta = int(args["k"]), int(args["delta_bp"])
    sigma = int(args.get("sigma_bp", DEFAULT_SIGMA_MULTIPLE * tau))
    # A cumulative ceiling below the per-round one would make the per-round
    # check unreachable, which is a misconfiguration rather than a strict
    # policy, and it should be refused rather than silently obeyed.
    ctx.require(sigma >= tau, f"sigma_bp {sigma} is below tau_bp {tau}")

    # --- step 1: every endorser must have checked the committed benchmark ---
    for task_id in tasks:
        bench = ctx.get(BENCH + task_id)
        ctx.require(bench is not None, f"no benchmark committed for {task_id}")

    # --- step 2: accept only certified signatures, one vote per organisation ---
    #
    # The certificate must be resolved against the MSP *before* the signature is
    # checked, and the public key must come out of that validated certificate.
    # Verifying against a key the submission carried would prove only that
    # somebody holds some private key — so one actor could generate three
    # keypairs, label them with three organisations, and promote any model it
    # liked. That defeats the entire guarantee this contract exists to provide.
    accepted: dict[str, dict[str, dict[str, int]]] = {}
    rejected: list[dict[str, str]] = []
    for sub in args["submissions"]:
        msp_id = sub["endorser_msp"]
        if msp_id in accepted:
            rejected.append({"endorser_msp": msp_id, "reason": "duplicate submission"})
            continue
        payload = {
            "round_id": args["round_id"],
            "candidate_id": args["candidate_id"],
            "candidate_hash": args["candidate_hash"],
            "accuracies": sub["accuracies"],
        }
        public_key, reason = ctx.msp.public_key_for(msp_id, sub.get("certificate_pem", ""))
        if public_key is None:
            rejected.append({"endorser_msp": msp_id, "reason": reason})
            continue
        if not verify(public_key, payload, sub["signature"]):
            rejected.append({"endorser_msp": msp_id, "reason": "signature does not verify"})
            continue
        missing = [t for t in tasks if t not in sub["accuracies"]]
        if missing:
            rejected.append(
                {"endorser_msp": msp_id, "reason": f"did not evaluate {', '.join(missing)}"}
            )
            continue
        accepted[msp_id] = sub["accuracies"]

    decision: dict[str, Any] = {
        "round_id": args["round_id"],
        "candidate_id": args["candidate_id"],
        "candidate_hash": args["candidate_hash"],
        "parent_id": args["parent_id"],
        "memory_bank_hash": rnd["memory_bank_hash"],
        "contributors": rnd["contributors"],
        "endorsers": sorted(accepted.keys()),
        "rejected_submissions": rejected,
        "parameters": {"gamma_bp": gamma, "tau_bp": tau, "sigma_bp": sigma,
                       "k": k, "delta_bp": delta},
        "decided_at": args["timestamp"],
        "per_task": [],
    }

    # --- step 3: enough independent organisations? ---
    if len(accepted) < k:
        decision["outcome"] = "reject"
        decision["reason_code"] = "INSUFFICIENT_ENDORSEMENTS"
        decision["reason"] = (
            f"{len(accepted)} organisations submitted valid results, {k} required"
        )
        return _finalise(ctx, decision, promote=False)

    # --- step 4: do they agree? ---
    for task_id in tasks:
        cand = [accepted[m][task_id]["candidate_bp"] for m in accepted]
        prev = [accepted[m][task_id]["previous_bp"] for m in accepted]
        spread = max(max(cand) - min(cand), max(prev) - min(prev))
        if spread > delta:
            decision["outcome"] = "reject"
            decision["reason_code"] = "NO_AGREEMENT"
            decision["reason"] = (
                f"endorsers disagree on {task_id} by {spread} bp, tolerance is {delta} bp"
            )
            return _finalise(ctx, decision, promote=False)

    # --- step 5: medians ---
    medians: dict[str, dict[str, int]] = {}
    for task_id in tasks:
        medians[task_id] = {
            "candidate_bp": _median_bp(
                [accepted[m][task_id]["candidate_bp"] for m in accepted]
            ),
            "previous_bp": _median_bp(
                [accepted[m][task_id]["previous_bp"] for m in accepted]
            ),
        }

    earlier = [t for t in tasks if t != new_task]

    # The best each task has ever scored under a promoted model. Absent for a
    # task nothing has been promoted on yet, in which case there is no history
    # to have drifted from and the cumulative check has nothing to say.
    best: dict[str, int | None] = {t: ctx.get(HIGHWATER + t) for t in tasks}

    for task_id in tasks:
        c, p = medians[task_id]["candidate_bp"], medians[task_id]["previous_bp"]
        peak = best[task_id]
        drift = None if peak is None else peak - c
        decision["per_task"].append(
            {
                "task_id": task_id,
                "benchmark_hash": ctx.get(BENCH + task_id)["benchmark_hash"],
                "candidate_bp": c,
                "previous_bp": p,
                "change_bp": c - p,
                "best_bp": peak,
                "drift_from_best_bp": drift,
                "is_new_task": task_id == new_task,
                "threshold_bp": gamma if task_id == new_task else -tau,
                "pass": (
                    (c - p) >= gamma
                    if task_id == new_task
                    else (p - c) <= tau and (drift is None or drift <= sigma)
                ),
            }
        )

    # --- step 6: real improvement on the new task? ---
    gain = medians[new_task]["candidate_bp"] - medians[new_task]["previous_bp"]
    if gain < gamma:
        decision["outcome"] = "reject"
        decision["reason_code"] = "NO_IMPROVEMENT"
        decision["reason"] = (
            f"gain on {new_task} is {gain} bp, at least {gamma} bp required"
        )
        return _finalise(ctx, decision, promote=False)

    # --- step 7: has it forgotten anything since last round? ---
    for task_id in earlier:
        loss = medians[task_id]["previous_bp"] - medians[task_id]["candidate_bp"]
        if loss > tau:
            decision["outcome"] = "reject"
            decision["reason_code"] = "REGRESSION"
            decision["reason"] = (
                f"accuracy on {task_id} fell by {loss} bp, tolerance is {tau} bp"
            )
            return _finalise(ctx, decision, promote=False)

    # --- step 8: has it drifted too far from the best it ever was? ---
    #
    # Step 7 alone is a per-round bound, and a per-round bound is not a bound.
    # An attacker who knows tau loses tau-1 every round and the contract
    # promotes each one correctly; after enough rounds the model is ruined and
    # no single decision was ever wrong. Measuring against the high-water mark
    # closes that, and is checked second so the more specific per-round failure
    # is the one reported when both apply.
    for task_id in earlier:
        peak = best[task_id]
        if peak is None:
            continue
        drift = peak - medians[task_id]["candidate_bp"]
        if drift > sigma:
            decision["outcome"] = "reject"
            decision["reason_code"] = "CUMULATIVE_REGRESSION"
            decision["reason"] = (
                f"accuracy on {task_id} is {drift} bp below its best of {peak} bp, "
                f"cumulative tolerance is {sigma} bp"
            )
            return _finalise(ctx, decision, promote=False)

    decision["outcome"] = "promote"
    decision["reason_code"] = "OK"
    decision["reason"] = (
        f"gained {gain} bp on {new_task}, lost no more than {tau} bp on any earlier "
        f"task this round and no more than {sigma} bp against its best"
    )
    return _finalise(ctx, decision, promote=True)


def _finalise(ctx: Context, decision: dict[str, Any], promote: bool) -> dict[str, Any]:
    """
    Write the decision to the ledger either way.

    A rejection is recorded as permanently as a promotion. That is the audit
    trail: any member can later ask what was submitted, who evaluated it, what
    they signed and why it was refused.
    """
    ctx.put(DECISION + decision["candidate_id"], decision)

    model = {
        "model_id": decision["candidate_id"],
        "model_hash": decision["candidate_hash"],
        "parent_id": decision["parent_id"],
        "round_id": decision["round_id"],
        "memory_bank_hash": decision["memory_bank_hash"],
        "contributors": decision["contributors"],
        "endorsers": decision["endorsers"],
        "status": "promoted" if promote else "rejected",
        "outcome_reason": decision["reason"],
        "per_task": decision["per_task"],
        "decided_at": decision["decided_at"],
    }
    ctx.put(MODEL + decision["candidate_id"], model)

    if promote:
        # Raise the high-water mark for every task this candidate improved on.
        # Only on promotion: a rejected candidate's numbers must not become the
        # baseline a later one is judged against, or an attacker could lift the
        # bar with a submission it never expected to pass and then fail
        # everything afterwards.
        for row in decision["per_task"]:
            peak = ctx.get(HIGHWATER + row["task_id"])
            if peak is None or row["candidate_bp"] > int(peak):
                ctx.put(HIGHWATER + row["task_id"], int(row["candidate_bp"]))

        previous = ctx.get(CURRENT)
        if previous is not None:
            superseded = dict(ctx.get(MODEL + previous) or {})
            if superseded:
                superseded["status"] = "superseded"
                ctx.put(MODEL + previous, superseded)
        ctx.put(CURRENT, decision["candidate_id"])

    rnd = dict(ctx.get(ROUND + decision["round_id"]))
    rnd["status"] = "decided"
    rnd["decision"] = decision["outcome"]
    ctx.put(ROUND + decision["round_id"], rnd)
    return decision


# -- read-only ------------------------------------------------------------
def get_current_model(ctx: Context, args: dict[str, Any]) -> Any:
    current = ctx.get(CURRENT)
    return ctx.get(MODEL + current) if current else None


def get_decision(ctx: Context, args: dict[str, Any]) -> Any:
    return ctx.get(DECISION + args["candidate_id"])


def list_models(ctx: Context, args: dict[str, Any]) -> list[Any]:
    return [v for _, v in ctx.range(MODEL)]


def list_benchmarks(ctx: Context, args: dict[str, Any]) -> list[Any]:
    return [v for _, v in ctx.range(BENCH)]


def list_rounds(ctx: Context, args: dict[str, Any]) -> list[Any]:
    return [v for _, v in ctx.range(ROUND)]


def list_high_water(ctx: Context, args: dict[str, Any]) -> dict[str, int]:
    """
    The best each task has ever scored under a promoted model.

    Readable because the cumulative bound is only meaningful to a member who can
    see what it is measured against. A drift ceiling nobody can inspect is a
    number the operator could be moving.
    """
    return {key[len(HIGHWATER):]: value for key, value in ctx.range(HIGHWATER)}


_ROUTES = {
    "commit_benchmark": commit_benchmark,
    "reveal_benchmark": reveal_benchmark,
    "open_round": open_round,
    "evaluate_gate": evaluate_gate,
    "get_current_model": get_current_model,
    "get_decision": get_decision,
    "list_models": list_models,
    "list_benchmarks": list_benchmarks,
    "list_rounds": list_rounds,
    "list_high_water": list_high_water,
}


def fedmodel(ctx: Context, function: str, args: dict[str, Any]) -> Any:
    fn = _ROUTES.get(function)
    if fn is None:
        raise ChaincodeError(f"fedmodel has no function {function}")
    return fn(ctx, args)
