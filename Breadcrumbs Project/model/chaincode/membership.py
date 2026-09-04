"""
membership chaincode: who is in the consortium.

Membership used to be a Python constant. The governance screen could carry a
motion to admit a factory, three members could endorse it, the motion would go
green, and nothing anywhere would change: the new member did not appear in the
register, did not appear on the network map, and was not on the ledger at all.
The one screen in the product about collective decisions was the one screen
where decisions had no effect.

So the member set lives here. Admission is a transaction, it names the motion
that authorised it, and it is subject to an endorsement policy like everything
else, which is the property the governance screen has been claiming all along:
whoever runs the infrastructure cannot add or remove a member alone.

Suspension is a status change and never a deletion. A member that was admitted
in March and suspended in July was still a member in April, and a register that
loses that fact cannot answer questions about April.
"""

from __future__ import annotations

from typing import Any

from ..ledger.network import ChaincodeError, Context

MEMBER = "member:"

KINDS = {"factory", "buyer", "auditor", "consortium", "regulator"}
STATUSES = {"active", "suspended"}


def _key(msp_id: str) -> str:
    return MEMBER + msp_id


def seed_member(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    """
    Write a founding member.

    Separate from `admit_member` because the founders were not admitted by a
    motion: there was no consortium yet to carry one. Pretending otherwise would
    put a fabricated proposal id on the ledger, and an invented record on the
    ledger is exactly what this product exists to make impossible.
    """
    ctx.require(
        ctx.msp.org_kind(ctx.caller_msp) == "consortium",
        "only the consortium may seed the founding register",
    )
    msp_id = args["msp_id"]
    ctx.require(ctx.get(_key(msp_id)) is None, f"{msp_id} is already on the register")
    ctx.require(args["kind"] in KINDS, f"unknown member kind {args['kind']}")

    entry = {
        "msp_id": msp_id,
        "name": args["name"],
        "kind": args["kind"],
        "country": args["country"],
        "status": "active",
        "founding": True,
        "admitted_at": args["timestamp"],
        "admitted_by": None,
        "proposal_id": None,
        "history": [{"what": "founding member", "at": args["timestamp"]}],
    }
    ctx.put(_key(msp_id), entry)
    return entry


def admit_member(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    """
    Admit an organisation, on the authority of a motion that carried.

    The endorsement policy is what makes this real rather than ceremonial. It
    requires three organisations, so the consortium administrator pressing the
    button is not sufficient, and neither is any pair of factories.
    """
    msp_id = args["msp_id"]
    ctx.require(ctx.get(_key(msp_id)) is None, f"{msp_id} is already on the register")
    ctx.require(args["kind"] in KINDS, f"unknown member kind {args['kind']}")
    # A motion is the only thing that authorises an admission, so it is required
    # rather than optional: without it the register cannot say why anyone is on
    # it, which is the question the register exists to answer.
    ctx.require(bool(args.get("proposal_id")), "an admission must name the motion that carried")

    entry = {
        "msp_id": msp_id,
        "name": args["name"],
        "kind": args["kind"],
        "country": args["country"],
        "status": "active",
        "founding": False,
        "admitted_at": args["timestamp"],
        "admitted_by": sorted(args.get("endorsers", [])),
        "proposal_id": args["proposal_id"],
        "history": [
            {
                "what": f"admitted by motion {args['proposal_id']}",
                "at": args["timestamp"],
            }
        ],
    }
    ctx.put(_key(msp_id), entry)
    return entry


def set_status(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    """
    Suspend a member, or restore one, with the motion and the reason attached.

    Never a delete. A register that forgets a suspended member cannot answer
    what its membership was last quarter, and that is the question anyone
    auditing a decision from last quarter will ask.
    """
    msp_id = args["msp_id"]
    entry = ctx.get(_key(msp_id))
    ctx.require(entry is not None, f"{msp_id} is not on the register")
    status = args["status"]
    ctx.require(status in STATUSES, f"unknown status {status}")
    ctx.require(bool(args.get("proposal_id")), "a status change must name the motion that carried")
    ctx.require(bool(args.get("reason")), "a status change must carry a reason")

    updated = dict(entry)
    updated["status"] = status
    updated["history"] = list(entry["history"]) + [
        {
            "what": f"{status} by motion {args['proposal_id']}: {args['reason']}",
            "at": args["timestamp"],
        }
    ]
    ctx.put(_key(msp_id), updated)
    return updated


def get_member(ctx: Context, args: dict[str, Any]) -> dict[str, Any] | None:
    return ctx.get(_key(args["msp_id"]))


def list_members(ctx: Context, args: dict[str, Any]) -> list[dict[str, Any]]:
    """The register, in a stable order so every peer returns the same list."""
    entries = [v for _, v in ctx.range(MEMBER) if v is not None]
    kind = args.get("kind")
    if kind:
        entries = [e for e in entries if e["kind"] == kind]
    status = args.get("status")
    if status:
        entries = [e for e in entries if e["status"] == status]
    return sorted(entries, key=lambda e: e["msp_id"])


_ROUTES = {
    "seed_member": seed_member,
    "admit_member": admit_member,
    "set_status": set_status,
    "get_member": get_member,
    "list_members": list_members,
}


def membership(ctx: Context, function: str, args: dict[str, Any]) -> Any:
    fn = _ROUTES.get(function)
    if fn is None:
        raise ChaincodeError(f"membership has no function {function}")
    return fn(ctx, args)
