"""
anchor chaincode: the accumulator, the epoch, and the time beacon.

This is where the mathematics in `model/accumulator/` stops being a library and
becomes something the consortium enforces. Three jobs:

  1. Hold the accumulator value, and advance it one epoch at a time.
  2. Refuse to accumulate anything the ledger does not already hold.
  3. Carry the delay-function beacon that bounds how fast history can be made.

JOB 2 IS THE ONE THAT MATTERS. An accumulator is a set commitment and nothing
stops a writer committing to a set of their own invention. What binds it to
reality is that this contract re-derives each element from the record or seal
already in the world state, and re-checks that the element hashes to the prime
being accumulated. A prime for a record nobody committed does not get in. That
check is what makes a membership witness mean "this was committed" rather than
merely "somebody put this in the accumulator".

WHY AN EPOCH AND NOT A TRANSACTION. Accumulating one record at a time would put
one ledger write behind every document, which is the cost model that makes
people give up on blockchains for high-volume record-keeping. Instead a factory
batches an epoch's worth and submits one update carrying a proof of
exponentiation, which the contract verifies in constant time whatever the epoch
size. The measured effect is in `results/accumulator.json`.

DETERMINISM. Everything here is integer arithmetic and hashing. No floats, no
clocks, no randomness; timestamps arrive as arguments as they do everywhere else
in this codebase. Primality testing uses fixed bases for exactly this reason —
see `model/accumulator/hashprime.py`.
"""

from __future__ import annotations

from typing import Any

from ..accumulator import RSAGroup, verify_batch_update, verify_prime
from ..accumulator import vdf as delay
from ..ledger.crypto import TAG_SEAL, canonical, h
from ..ledger.network import ChaincodeError, Context

GROUP = "acc_group"
STATE = "acc_state"
DIGEST = "epoch_digest:"
ANCHORED = "anchored:"

RECORD = "record:"
SEAL = "seal:"


# --------------------------------------------------------------------------
# What gets accumulated
# --------------------------------------------------------------------------
def record_element(record: dict[str, Any]) -> dict[str, Any]:
    """
    The canonical thing a record contributes to the accumulator.

    Deliberately not the whole record. It carries the identifier, the Merkle root
    and the bucket — enough that a witness proves *this document, with this
    content, in this reporting period* — and nothing that a later legitimate
    change to status or supersession would disturb. An element derived from
    mutable fields would be invalidated by ordinary bookkeeping, and every
    outstanding witness with it.
    """
    return {
        "type": "record",
        "record_id": record["record_id"],
        "merkle_root": record["merkle_root"],
        "bucket": record["bucket"],
        "owner_msp": record["owner_msp"],
    }


def seal_element(seal: dict[str, Any]) -> dict[str, Any]:
    """
    The canonical thing a period seal contributes.

    The seal's *version* is included, so an amended period accumulates a new,
    distinct element rather than mutating an old one. A verifier can therefore
    prove which version of a period seal was in force at a given epoch, which is
    what makes the amendment history checkable rather than merely readable.
    """
    return {
        "type": "seal",
        "bucket": seal["bucket"],
        "version": seal["version"],
        "record_count": seal["record_count"],
        "records_root": seal["records_root"],
    }


# --------------------------------------------------------------------------
# setup
# --------------------------------------------------------------------------
def init_group(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    """
    Install the accumulator parameters and the transcript of how they were made.

    The transcript is stored, not just its hash. A member joining in year three
    needs to be able to read who was in the room when the modulus was generated
    and decide for itself what the accumulator is worth — and a hash of a
    document nobody kept is not a record, it is a gesture.
    """
    ctx.require(
        ctx.msp.org_kind(ctx.caller_msp) == "consortium",
        "only the consortium may install accumulator parameters",
    )
    ctx.require(ctx.get(GROUP) is None, "accumulator parameters are already installed")

    params = args["group"]
    group = RSAGroup.from_dict(params)
    ctx.require(
        group.parameters_hash == args["parameters_hash"],
        "the parameters do not hash to the value supplied",
    )
    ctx.require(
        args["transcript"]["parameters_hash"] == args["parameters_hash"],
        "the ceremony transcript describes different parameters",
    )

    ctx.put(GROUP, {"params": params, "transcript": args["transcript"]})
    ctx.put(
        STATE,
        {
            "value_hex": format(group.normalise(group.generator), "x"),
            "epoch": 0,
            "size": 0,
            "parameters_hash": args["parameters_hash"],
            "updated_at": args["timestamp"],
        },
    )
    return {"parameters_hash": args["parameters_hash"], "epoch": 0}


def _group(ctx: Context) -> RSAGroup:
    stored = ctx.get(GROUP)
    ctx.require(stored is not None, "accumulator parameters have not been installed")
    return RSAGroup.from_dict(stored["params"])


# --------------------------------------------------------------------------
# advancing
# --------------------------------------------------------------------------
def advance_epoch(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    """
    Fold a batch of committed records and seals into the accumulator.

    args:
      elements  [{kind: "record"|"seal", key, prime_hex, nonce}]
      value_hex the claimed new accumulator value
      proof     the proof of exponentiation for the update
      timestamp

    The contract does three things in order and every one of them can refuse.
    It re-derives each element from the world state, so nothing enters the
    accumulator that the ledger does not already hold. It re-checks that each
    element hashes to the prime being claimed, so a valid record cannot be
    smuggled in under someone else's prime. And it verifies the update proof,
    so the new value is the old one raised to exactly those primes and no others.
    """
    ctx.require(ctx.caller_role in ("operator", "admin"), "role may not advance the accumulator")
    group = _group(ctx)
    state = ctx.get(STATE)
    ctx.require(state is not None, "the accumulator has no state")

    previous = int(state["value_hex"], 16)
    claimed = int(args["value_hex"], 16)
    entries = args["elements"]
    ctx.require(bool(entries), "an epoch must accumulate at least one element")

    primes: list[int] = []
    seen: set[int] = set()
    accumulated: list[dict[str, Any]] = []

    for entry in entries:
        kind, key = entry["kind"], entry["key"]
        if kind == "record":
            stored = ctx.get(RECORD + key)
            ctx.require(stored is not None, f"no committed record {key}")
            payload = record_element(stored)
        elif kind == "seal":
            stored = ctx.get(SEAL + key)
            ctx.require(stored is not None, f"no sealed period {key}")
            payload = seal_element(stored)
        else:
            raise ChaincodeError(f"cannot accumulate a {kind}")

        prime = int(entry["prime_hex"], 16)
        ctx.require(
            verify_prime(payload, prime, int(entry["nonce"])),
            f"{kind} {key} does not hash to the prime submitted for it",
        )
        ctx.require(prime not in seen, f"{kind} {key} appears twice in this epoch")
        anchored_key = ANCHORED + format(prime, "x")
        ctx.require(ctx.get(anchored_key) is None, f"{kind} {key} is already accumulated")

        seen.add(prime)
        primes.append(prime)
        accumulated.append({"kind": kind, "key": key, "prime_hex": entry["prime_hex"]})

    ctx.require(
        verify_batch_update(group, previous, primes, claimed, args["proof"]),
        "the update proof does not show this value follows from the previous one",
    )

    epoch = int(state["epoch"]) + 1
    for element in accumulated:
        ctx.put(ANCHORED + element["prime_hex"], {"epoch": epoch, **element})

    new_state = {
        "value_hex": args["value_hex"],
        "epoch": epoch,
        "size": int(state["size"]) + len(primes),
        "parameters_hash": state["parameters_hash"],
        "updated_at": args["timestamp"],
    }
    ctx.put(STATE, new_state)

    digest = {
        "epoch": epoch,
        "accumulator_hex": args["value_hex"],
        "size": new_state["size"],
        "element_count": len(primes),
        "previous_hex": state["value_hex"],
        "sealed_at": args["timestamp"],
        "parameters_hash": state["parameters_hash"],
    }
    digest["digest"] = h(TAG_SEAL, canonical(digest))
    ctx.put(DIGEST + str(epoch), digest)
    return {"epoch": epoch, "accumulated": len(primes), "digest": digest["digest"]}


# --------------------------------------------------------------------------
# the beacon
# --------------------------------------------------------------------------
def publish_beacon(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    """
    Attach a proof that real time passed between two epochs.

    Hash chains prove order, not duration. Without this, a colluding majority
    could sit down on a Sunday, manufacture eight months of plausible history
    with whatever dates it liked, and nothing in the chain would object. A
    verifiable delay function makes that cost eight months of sequential
    squaring on the fastest hardware in existence.

    Stated honestly, and it belongs in the report the same way: this bounds how
    *fast* history can be produced. It does not fix history to a calendar. That
    needs the epoch digest to leave the consortium and be held by somebody with
    no stake in it, which is what `iterations` being an agreed channel parameter
    rather than a per-submission choice is meant to support.
    """
    group = _group(ctx)
    epoch = int(args["epoch"])
    digest = ctx.get(DIGEST + str(epoch))
    ctx.require(digest is not None, f"epoch {epoch} has no digest")
    ctx.require("beacon" not in digest, f"epoch {epoch} already carries a beacon")

    previous = ctx.get(DIGEST + str(epoch - 1))
    seed_source = previous["digest"] if previous else digest["parameters_hash"]
    x = group.element_from({"beacon_seed": seed_source, "epoch": epoch})

    y = int(args["output_hex"], 16)
    ok, why = delay.verify(group, x, y, args["proof"])
    ctx.require(ok, f"delay proof rejected: {why}")
    ctx.require(
        int(args["proof"]["iterations"]) >= int(args["minimum_iterations"]),
        "the delay proof claims less work than the consortium requires per epoch",
    )

    updated = dict(digest)
    updated["beacon"] = {
        "input_hex": format(x, "x"),
        "output_hex": args["output_hex"],
        "iterations": int(args["proof"]["iterations"]),
        "proof": args["proof"],
        "published_at": args["timestamp"],
        "published_by": ctx.caller_msp,
    }
    ctx.put(DIGEST + str(epoch), updated)
    return {"epoch": epoch, "iterations": updated["beacon"]["iterations"], "verified": True}


# --------------------------------------------------------------------------
# read-only
# --------------------------------------------------------------------------
def get_state(ctx: Context, args: dict[str, Any]) -> Any:
    return ctx.get(STATE)


def get_group(ctx: Context, args: dict[str, Any]) -> Any:
    return ctx.get(GROUP)


def get_digest(ctx: Context, args: dict[str, Any]) -> Any:
    return ctx.get(DIGEST + str(args["epoch"]))


def list_digests(ctx: Context, args: dict[str, Any]) -> list[Any]:
    return sorted((v for _, v in ctx.range(DIGEST)), key=lambda d: d["epoch"])


def is_anchored(ctx: Context, args: dict[str, Any]) -> Any:
    return ctx.get(ANCHORED + args["prime_hex"])


_ROUTES = {
    "init_group": init_group,
    "advance_epoch": advance_epoch,
    "publish_beacon": publish_beacon,
    "get_state": get_state,
    "get_group": get_group,
    "get_digest": get_digest,
    "list_digests": list_digests,
    "is_anchored": is_anchored,
}


def anchor(ctx: Context, function: str, args: dict[str, Any]) -> Any:
    fn = _ROUTES.get(function)
    if fn is None:
        raise ChaincodeError(f"anchor has no function {function}")
    return fn(ctx, args)
