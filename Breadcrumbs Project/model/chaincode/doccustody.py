"""
doccustody chaincode: document commitments, access grants, verification receipts.

What this contract stores is the whole argument of the report's Table 2. It holds
root hashes, record type, period, site, and who was granted access to what. It
does not hold the document, the rows, any worker's name, or any wage. Those stay
in the factory's own encrypted storage, because an append-only ledger and a
deletion right cannot both be satisfied for personal data.

Access grants are on-chain for a reason worth saying out loud: a buyer must not
be able to deny that access was granted, and a factory must not be able to deny
granting it. A grant held in a vendor's database satisfies neither party.

Determinism: no clocks, no randomness. Every timestamp arrives as an argument
from the client so all endorsers see the same value.
"""

from __future__ import annotations

from typing import Any

from ..ledger.network import ChaincodeError, Context

RECORD = "record:"
GRANT = "grant:"
RECEIPT = "receipt:"

VALID_TYPES = {
    "payroll_register",
    "safety_inspection",
    "chemical_inventory",
    "machine_maintenance",
    "compliance_certificate",
}


def _require_factory(ctx: Context) -> None:
    kind = ctx.msp.org_kind(ctx.caller_msp)
    ctx.require(kind == "factory", f"{ctx.caller_msp} is not a factory organisation")


def _require_owner(ctx: Context, record: dict[str, Any]) -> None:
    ctx.require(
        record["owner_msp"] == ctx.caller_msp,
        f"{ctx.caller_msp} does not own {record['record_id']}",
    )


def commit_record(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    """Commit a document's Merkle root and its metadata. Nothing else."""
    _require_factory(ctx)
    ctx.require(ctx.caller_role in ("operator", "admin"), "role may not commit records")

    record_id = args["record_id"]
    ctx.require(ctx.get(RECORD + record_id) is None, f"{record_id} already committed")
    ctx.require(
        args["record_type"] in VALID_TYPES,
        f"unknown record type {args['record_type']}",
    )
    ctx.require(len(args["merkle_root"]) == 64, "merkle_root must be a 64-character hash")
    ctx.require(int(args["row_count"]) > 0, "a record must have at least one row")

    record = {
        "record_id": record_id,
        "owner_msp": ctx.caller_msp,
        "merkle_root": args["merkle_root"],
        "record_type": args["record_type"],
        "period": args["period"],
        "site": args["site"],
        "row_count": int(args["row_count"]),
        "schema_version": args["schema_version"],
        "committed_at": args["timestamp"],
        "committed_by": ctx.caller.id,
        "status": "committed",
        "superseded_by": None,
    }
    ctx.put(RECORD + record_id, record)
    return {"record_id": record_id, "merkle_root": args["merkle_root"], "status": "committed"}


def supersede_record(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    """
    Mark a record replaced by a later version.

    The old record is not deleted and its root stays verifiable. A correction is
    part of the history, not a replacement for it.
    """
    old = ctx.get(RECORD + args["record_id"])
    ctx.require(old is not None, f"unknown record {args['record_id']}")
    _require_owner(ctx, old)
    new = ctx.get(RECORD + args["new_record_id"])
    ctx.require(new is not None, f"unknown replacement record {args['new_record_id']}")

    old = dict(old)
    old["status"] = "superseded"
    old["superseded_by"] = args["new_record_id"]
    old["supersede_reason"] = args["reason"]
    old["superseded_at"] = args["timestamp"]
    ctx.put(RECORD + args["record_id"], old)
    return {"record_id": args["record_id"], "status": "superseded"}


def grant_access(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    """
    Grant one named organisation the right to verify one named field.

    Scope is a single field, not a document. That is the difference between this
    and sending a PDF, and the contract enforces it rather than trusting the
    application layer to remember.
    """
    record = ctx.get(RECORD + args["record_id"])
    ctx.require(record is not None, f"unknown record {args['record_id']}")
    _require_owner(ctx, record)

    grant_id = args["grant_id"]
    ctx.require(ctx.get(GRANT + grant_id) is None, f"{grant_id} already exists")
    ctx.require(
        args["requester_msp"] in ctx.msp.authorities,
        f"unknown organisation {args['requester_msp']}",
    )
    ctx.require(bool(args.get("field_name")), "a grant must name exactly one field")

    grant = {
        "grant_id": grant_id,
        "record_id": args["record_id"],
        "owner_msp": ctx.caller_msp,
        "requester_msp": args["requester_msp"],
        "purpose_code": args["purpose_code"],
        "field_name": args["field_name"],
        "granted_at": args["timestamp"],
        "expires_at": args["expires_at"],
        "status": "active",
        "revoked_reason": None,
    }
    ctx.put(GRANT + grant_id, grant)
    return {"grant_id": grant_id, "status": "active"}


def revoke_access(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    """Revoke a grant. Permanent and attributable, which is the point."""
    grant = ctx.get(GRANT + args["grant_id"])
    ctx.require(grant is not None, f"unknown grant {args['grant_id']}")
    ctx.require(
        grant["owner_msp"] == ctx.caller_msp
        or ctx.msp.org_kind(ctx.caller_msp) == "consortium",
        "only the record owner or the consortium may revoke a grant",
    )
    ctx.require(grant["status"] == "active", f"grant is already {grant['status']}")

    grant = dict(grant)
    grant["status"] = "revoked"
    grant["revoked_reason"] = args["reason"]
    grant["revoked_at"] = args["timestamp"]
    grant["revoked_by"] = ctx.caller.id
    ctx.put(GRANT + args["grant_id"], grant)
    return {"grant_id": args["grant_id"], "status": "revoked"}


def record_verification(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    """
    Log that a verification happened, and its outcome.

    The contract checks the grant is live and in scope before it will write a
    receipt. A verification outside scope is refused here, not merely logged.
    """
    grant = ctx.get(GRANT + args["grant_id"])
    ctx.require(grant is not None, f"unknown grant {args['grant_id']}")
    ctx.require(
        grant["requester_msp"] == ctx.caller_msp,
        f"grant {args['grant_id']} does not belong to {ctx.caller_msp}",
    )
    ctx.require(grant["status"] == "active", f"grant is {grant['status']}")
    ctx.require(
        grant["field_name"] == args["field_name"],
        f"grant covers {grant['field_name']}, not {args['field_name']}",
    )
    ctx.require(
        args["timestamp"] <= grant["expires_at"],
        f"grant expired on {grant['expires_at']}",
    )

    receipt = {
        "receipt_id": args["receipt_id"],
        "grant_id": args["grant_id"],
        "record_id": grant["record_id"],
        "verifier_msp": ctx.caller_msp,
        "field_name": args["field_name"],
        "result": args["result"],  # "match" or "no_match"
        "computed_root": args["computed_root"],
        "verified_at": args["timestamp"],
    }
    ctx.put(RECEIPT + args["receipt_id"], receipt)
    return receipt


# -- read-only ------------------------------------------------------------
def get_record(ctx: Context, args: dict[str, Any]) -> Any:
    return ctx.get(RECORD + args["record_id"])


def list_records(ctx: Context, args: dict[str, Any]) -> list[Any]:
    owner = args.get("owner_msp")
    out = [v for _, v in ctx.range(RECORD)]
    return [r for r in out if owner is None or r["owner_msp"] == owner]


def list_grants(ctx: Context, args: dict[str, Any]) -> list[Any]:
    out = [v for _, v in ctx.range(GRANT)]
    if owner := args.get("owner_msp"):
        out = [g for g in out if g["owner_msp"] == owner]
    if requester := args.get("requester_msp"):
        out = [g for g in out if g["requester_msp"] == requester]
    return out


def list_receipts(ctx: Context, args: dict[str, Any]) -> list[Any]:
    out = [v for _, v in ctx.range(RECEIPT)]
    if record_id := args.get("record_id"):
        out = [r for r in out if r["record_id"] == record_id]
    return out


_ROUTES = {
    "commit_record": commit_record,
    "supersede_record": supersede_record,
    "grant_access": grant_access,
    "revoke_access": revoke_access,
    "record_verification": record_verification,
    "get_record": get_record,
    "list_records": list_records,
    "list_grants": list_grants,
    "list_receipts": list_receipts,
}


def doccustody(ctx: Context, function: str, args: dict[str, Any]) -> Any:
    fn = _ROUTES.get(function)
    if fn is None:
        raise ChaincodeError(f"doccustody has no function {function}")
    return fn(ctx, args)
