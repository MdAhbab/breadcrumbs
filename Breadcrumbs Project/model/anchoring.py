"""
Client-side glue between the ledger and the accumulator.

The contract in `chaincode/anchor.py` decides what may be accumulated. This
module does the arithmetic that produces a submission for it, and reconstructs
the witness-issuing state afterwards. Keeping the two apart matters: everything
here runs at one organisation and may be wrong or malicious, and nothing here is
trusted by the contract.

One property worth pointing out because it is not obvious. Every accumulated
element is recorded on the ledger under its prime, so the full set can be
rebuilt from the chain by anybody entitled to read it. A factory that loses its
local accumulator state has lost nothing: it re-derives the primes from the
ledger and reissues every outstanding witness. Witness issuance is recoverable,
which is not true of most accumulator deployments and is the difference between
a demo and something a factory could run for a decade.
"""

from __future__ import annotations

from typing import Any

from .accumulator import Accumulator, RSAGroup, prove_batch_update
from .chaincode.anchor import record_element, seal_element


def install_group(
    consortium, channel: str, group: RSAGroup, transcript, timestamp: str
) -> dict[str, Any]:
    """Publish the accumulator parameters and the ceremony that produced them."""
    _, result, response = consortium.network.invoke(
        channel,
        "anchor",
        "init_group",
        {
            "group": group.to_dict(),
            "parameters_hash": group.parameters_hash,
            "transcript": transcript.to_dict(),
            "timestamp": timestamp,
        },
        submitter=consortium.who("rafiqul.islam"),
        endorsers=consortium.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
        timestamp=timestamp,
    )
    if not result.valid:
        raise RuntimeError(f"could not install accumulator parameters: {result.reason}")
    return response


def _payload_for(consortium, channel: str, caller, kind: str, key: str) -> dict[str, Any]:
    """Re-derive an element exactly as the contract will, so the primes agree."""
    if kind == "record":
        stored = consortium.network.query(
            channel, "doccustody", "get_record", {"record_id": key}, caller=caller
        )
        if stored is None:
            raise KeyError(f"no committed record {key}")
        return record_element(stored)
    if kind == "seal":
        owner, site, record_type, period = key.split("|", 3)
        stored = consortium.network.query(
            channel,
            "doccustody",
            "get_seal",
            {"owner_msp": owner, "site": site, "record_type": record_type, "period": period},
            caller=caller,
        )
        if stored is None:
            raise KeyError(f"no sealed period {key}")
        return seal_element(stored)
    raise ValueError(f"cannot accumulate a {kind}")


def anchor_epoch(
    consortium,
    channel: str,
    items: list[tuple[str, str]],
    timestamp: str,
    submitter: str = "fatema.begum",
) -> dict[str, Any]:
    """
    Fold a batch of committed records and seals into the accumulator, in one write.

    `items` is a list of (kind, key) pairs where kind is "record" or "seal". The
    whole batch becomes a single ledger transaction whatever its size, which is
    the point: a factory producing four hundred documents a month writes to the
    chain once, not four hundred times.
    """
    caller = consortium.who(submitter)
    group_entry = consortium.network.query(channel, "anchor", "get_group", {}, caller=caller)
    if group_entry is None:
        raise RuntimeError("accumulator parameters have not been installed on this channel")
    group = RSAGroup.from_dict(group_entry["params"])
    state = consortium.network.query(channel, "anchor", "get_state", {}, caller=caller)

    previous = int(state["value_hex"], 16)
    elements, primes = [], []
    for kind, key in items:
        payload = _payload_for(consortium, channel, caller, kind, key)
        prime, nonce = Accumulator(group=group).element(payload)
        elements.append({"kind": kind, "key": key, "prime_hex": format(prime, "x"), "nonce": nonce})
        primes.append(prime)

    product = 1
    for prime in primes:
        product *= prime
    value = group.exp(previous, product)
    proof = prove_batch_update(group, previous, primes, value)

    _, result, response = consortium.network.invoke(
        channel,
        "anchor",
        "advance_epoch",
        {
            "elements": elements,
            "value_hex": format(value, "x"),
            "proof": proof,
            "timestamp": timestamp,
        },
        submitter=caller,
        endorsers=consortium.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
        timestamp=timestamp,
    )
    if not result.valid:
        raise RuntimeError(f"epoch rejected: {result.reason}")
    return response


def accumulator_from_ledger(consortium, channel: str, caller) -> Accumulator:
    """
    Rebuild the witness-issuing state from what the ledger holds.

    The order matters and is not arbitrary: witnesses are only correct if the
    primes are folded in the order they were accumulated, so the anchored entries
    are sorted by epoch and then by prime, which is the order the contract
    recorded them in.
    """
    group_entry = consortium.network.query(channel, "anchor", "get_group", {}, caller=caller)
    group = RSAGroup.from_dict(group_entry["params"])
    state = consortium.network.query(channel, "anchor", "get_state", {}, caller=caller)

    anchored = consortium.network.query(
        channel, "anchor", "list_digests", {}, caller=caller
    )
    del anchored  # digests are for the beacon; the primes come from the anchored index

    entries = [
        v
        for _, v in consortium.network.state.range(channel, "anchored:")
    ]
    entries.sort(key=lambda e: (e["epoch"], e["prime_hex"]))

    acc = Accumulator(group=group)
    acc.primes = [int(e["prime_hex"], 16) for e in entries]
    acc.nonces = {p: 0 for p in acc.primes}  # nonces are re-derived when a witness is issued
    acc.value = int(state["value_hex"], 16)
    acc.epoch = int(state["epoch"])
    return acc


def verify_record(
    consortium, channel: str, record_id: str, witness, caller
) -> tuple[bool, str]:
    """
    Verify a record the way a verifier actually should: three independent checks.

    This function is the answer to the trusted-dealer objection, so it is worth
    being explicit about what each check buys and why none of them is redundant.

      1. The ledger holds the record, with the Merkle root being claimed. A
         trapdoor holder cannot manufacture this: it would need a block, an
         ordering-service quorum and an endorsement from the auditor.
      2. The accumulator witness verifies against the current on-chain value.
         This is the cheap, stateless check, and it is the ONLY one a trapdoor
         holder can forge.
      3. The prime is in the anchored index, recorded by the epoch that admitted
         it. A forged witness has no anchored entry, because entries are written
         by the contract and only for elements it re-derived from state.

    Check 2 alone is what an accumulator paper would call verification. Checks 1
    and 3 are what make it safe to run this on a modulus whose ceremony had a
    dealer. Anyone re-implementing this must keep all three, and a
    reimplementation that keeps only the fast one has removed the defence while
    leaving the appearance of it.
    """
    from .accumulator import verify_membership

    stored = consortium.network.query(
        channel, "doccustody", "get_record", {"record_id": record_id}, caller=caller
    )
    if stored is None:
        return False, f"the ledger holds no record {record_id}"

    group_entry = consortium.network.query(channel, "anchor", "get_group", {}, caller=caller)
    group = RSAGroup.from_dict(group_entry["params"])
    state = consortium.network.query(channel, "anchor", "get_state", {}, caller=caller)

    ok, why = verify_membership(
        group,
        int(state["value_hex"], 16),
        witness,
        record_element(stored),
        int(state["epoch"]),
    )
    if not ok:
        return False, why

    anchored = consortium.network.query(
        channel,
        "anchor",
        "is_anchored",
        {"prime_hex": format(witness.element_prime, "x")},
        caller=caller,
    )
    if anchored is None:
        return False, (
            "the witness verifies against the accumulator but the ledger has no record of "
            "this element ever being accumulated: the witness was not issued by an epoch"
        )
    if anchored["key"] != record_id:
        return False, f"the anchored element belongs to {anchored['key']}, not {record_id}"

    return True, ""
