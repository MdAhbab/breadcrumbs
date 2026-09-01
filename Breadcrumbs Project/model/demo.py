"""
The full Breadcrumbs cycle, end to end, on a real ledger.

Run:  python -m model.demo

Twelve acts, two or three minutes. Two of them are the ones to watch.

Act 6 is where a factory hands over four of its five payroll registers and the
ledger catches it — not because any document is forged, but because the period
was sealed and the arithmetic no longer adds up. Every notarisation product on
the market reports that disclosure as clean.

Act 11 is where a candidate model that has quietly forgotten an earlier task is
refused by the contract, and no participant, including whoever ran the training,
can overrule it.

Everything here executes. The blocks are real blocks, the signatures are real
RSA-3072 PSS signatures over canonical encodings, the Merkle proof is recomputed
by the verifier from the disclosure alone, the accumulator arithmetic is real
modular exponentiation, and the gate decision is taken by chaincode from
independently signed evaluations. The data is invented, and the script says so on
screen rather than in a footnote.
"""

from __future__ import annotations

import sys
import time
from copy import deepcopy

from .accumulator import Accumulator, run_ceremony, verify_non_membership
from .ai import FederatedTrainer
from .anchoring import anchor_epoch, install_group, verify_record
from .chaincode.anchor import record_element
from .chaincode.witness import attestation_payload, share_commitment
from .consortium import DOCUMENT_CHANNEL, GATE_ORGS, MODEL_CHANNEL, build
from .ledger.crypto import TAG_BENCH, hash_object, sign
from .merkle import MerkleTree, verify_disclosure

W = 78

# The gate parameters the consortium agreed. A candidate must gain at least 2.00
# points on the new task, and may not lose more than 5.00 on any earlier one.
GAMMA_BP = 200
TAU_BP = 500
GREEN, RED, AMBER, DIM, BOLD, OFF = (
    "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[1m", "\033[0m",
)


def act(n: int, title: str) -> None:
    print(f"\n{BOLD}{'─' * W}\n  ACT {n}   {title}\n{'─' * W}{OFF}")


def line(label: str, value: str, colour: str = "") -> None:
    print(f"  {label:<34} {colour}{value}{OFF}")


def pause(seconds: float = 0.35) -> None:
    sys.stdout.flush()
    time.sleep(seconds)


def main() -> None:
    print(f"\n{BOLD}  BREADCRUMBS{OFF}  ·  permissioned ledger for verifiable factory records")
    print(f"{DIM}  Team CookieMonsters · United International University · 2026")
    print(f"  All data below is invented. No real factory, worker or document.{OFF}")

    # ---------------------------------------------------------------- Act 1
    act(1, "Stand up the consortium")
    consortium = build()
    net = consortium.network
    line("Organisations", str(len(consortium.authorities)))
    for msp_id, ca in consortium.authorities.items():
        print(f"    {DIM}{msp_id:<24}{OFF} {ca.org_name:<30} {DIM}{ca.kind}{OFF}")
    line("Channels", f"{DOCUMENT_CHANNEL}, {MODEL_CHANNEL}")
    line("Ordering nodes", f"{len(net.orderer.nodes)} (quorum {net.orderer.quorum})")
    line("doccustody policy", net.chaincodes["doccustody"].policy.describe())
    line("fedmodel policy", net.chaincodes["fedmodel"].policy.describe())
    pause()

    # ---------------------------------------------------------------- Act 2
    act(2, "A factory commits a payroll register")
    rows = [
        {"worker_ref": f"W-{i:05d}", "net_pay_bdt": 14000 + (i * 7) % 3000}
        for i in range(1847)
    ]
    tree = MerkleTree(rows)
    line("Rows in the register", f"{len(rows):,}")
    line("Merkle root", tree.root[:32] + "…")
    line("What goes on the ledger", "the root, type, period, site. Nothing else.")
    line("What stays in the factory", "every row, encrypted, deletable", DIM)

    block, result, response = net.invoke(
        DOCUMENT_CHANNEL, "doccustody", "commit_record",
        {
            "record_id": "rc-001", "merkle_root": tree.root,
            "record_type": "payroll_register", "period": "2026-07",
            "site": "Gazipur", "row_count": len(rows), "schema_version": "v2.1.0",
            "timestamp": "2026-08-05T09:14:00Z",
        },
        consortium.who("fatema.begum"),
        consortium.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
        "2026-08-05T09:14:00Z",
    )
    line("Committed in block", f"#{block.number}", GREEN)
    line("Validation", result.code, GREEN)
    line("Endorsed by", "ApexTextileMSP, BVCertificationMSP")
    pause()

    # ---------------------------------------------------------------- Act 3
    act(3, "A buyer asks for one number, and gets only that")
    net.invoke(
        DOCUMENT_CHANNEL, "doccustody", "grant_access",
        {
            "grant_id": "g-001", "record_id": "rc-001",
            "requester_msp": "PrimarkSourcingMSP", "purpose_code": "ETH-WAGE-VERIFY",
            "field_name": "net_pay_bdt", "expires_at": "2026-09-30T00:00:00Z",
            "timestamp": "2026-08-20T11:00:00Z",
        },
        consortium.who("fatema.begum"),
        consortium.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
        "2026-08-20T11:00:00Z",
    )
    line("Grant", "Primark Sourcing · net_pay_bdt · ETH-WAGE-VERIFY", GREEN)

    disclosure = tree.prove(21, "rc-001", "net_pay_bdt")
    ok, computed, _ = verify_disclosure(disclosure, tree.root)
    line("Disclosed value", f"{disclosure.value['net_pay_bdt']:,} BDT")
    line("Proof size", f"{len(disclosure.path)} sibling hashes for {len(rows):,} rows")
    line("Rows revealed", f"1 of {len(rows):,}. The other {len(rows) - 1:,} never moved.")
    line("Computed root", computed[:32] + "…")
    line("Matches the ledger", "YES — the record is genuine" if ok else "NO", GREEN if ok else RED)

    tampered = tree.prove(21, "rc-001", "net_pay_bdt")
    tampered.value = {**tampered.value, "net_pay_bdt": 99_999}
    bad_ok, _, _ = verify_disclosure(tampered, tree.root)
    line("If the value were altered", "proof fails" if not bad_ok else "STILL PASSES (bug)",
         GREEN if not bad_ok else RED)
    pause()

    # ---------------------------------------------------------------- Act 4
    act(4, "The consortium adopts the witness rule")
    print(f"    {DIM}A ledger makes a record unchangeable. It says nothing about whether")
    print("    the record was true when written. A second organisation now has to")
    print(f"    counter-sign — and it is assigned, not chosen.{OFF}\n")

    seed_members = ["ApexTextileMSP", "BVCertificationMSP"]
    shares = {"ApexTextileMSP": "a1" * 16, "BVCertificationMSP": "b2" * 16}
    who = {"ApexTextileMSP": "fatema.begum", "BVCertificationMSP": "meera.nair"}
    doc_endorsers = consortium.endorsers(["ApexTextileMSP", "BVCertificationMSP"])

    def doc(fn, args, submitter, ts="2026-08-21T09:00:00Z"):
        return net.invoke(DOCUMENT_CHANNEL, "doccustody", fn, args,
                          consortium.who(submitter), doc_endorsers, ts)

    doc("open_seed_round",
        {"round_id": "seed-q3", "members": seed_members, "sample_percent": 20,
         "quorum": 1, "timestamp": "2026-08-21T09:00:00Z"},
        "rafiqul.islam")
    line("Seed round opened by", "BGMEAConsortiumMSP")
    for msp in seed_members:
        doc("commit_seed_share",
            {"round_id": "seed-q3", "commitment": share_commitment(shares[msp]),
             "timestamp": "2026-08-21T09:00:00Z"}, who[msp])
    line("Shares committed", "hashes only — nobody has revealed anything yet")
    for msp in seed_members:
        _, _, reveal = doc("reveal_seed_share",
                           {"round_id": "seed-q3", "share": shares[msp],
                            "timestamp": "2026-08-21T09:05:00Z"}, who[msp])
    line("Seed", reveal["seed"][:32] + "…", GREEN)
    line("Why commit-reveal", "whoever revealed last could otherwise grind the draw", DIM)
    pause()

    # ---------------------------------------------------------------- Act 5
    act(5, "A record now needs a counter-signature it cannot choose")
    rows2 = [{"worker_ref": f"W-{i:05d}", "net_pay_bdt": 15000 + (i * 11) % 2500}
             for i in range(1204)]
    tree2 = MerkleTree(rows2)
    args2 = {
        "record_id": "rc-002", "merkle_root": tree2.root,
        "record_type": "payroll_register", "period": "2026-07",
        "site": "Gazipur", "row_count": len(rows2), "schema_version": "v2.1.0",
        "timestamp": "2026-08-21T10:00:00Z",
    }
    requirement = net.query(DOCUMENT_CHANNEL, "doccustody", "witness_requirement",
                            {"record_id": "rc-002", "record_type": "payroll_register"},
                            consortium.who("fatema.begum"))
    line("Assigned witness", ", ".join(requirement["witnesses"]), AMBER)
    line("Chosen by", "a hash of the shared seed and the record id — not by the factory")

    try:
        doc("commit_record", args2, "fatema.begum", "2026-08-21T10:00:00Z")
        line("Unwitnessed commit", "ACCEPTED — this is a bug", RED)
    except Exception as exc:
        line("Unwitnessed commit", f"REFUSED — {str(exc)[:46]}", GREEN)

    witness_record = {
        "record_id": "rc-002", "merkle_root": tree2.root,
        "bucket": "ApexTextileMSP|Gazipur|payroll_register|2026-07",
        "owner_msp": "ApexTextileMSP",
    }
    args2["attestations"] = [
        {
            "witness_msp": m, "check_code": "source_system_readback",
            "attested_at": "2026-08-21T10:00:00Z",
            "certificate_pem": consortium.org_identity(m).certificate_pem(),
            "signature": sign(consortium.org_identity(m).private_key,
                              attestation_payload(witness_record, "source_system_readback",
                                                  "2026-08-21T10:00:00Z")),
        }
        for m in requirement["witnesses"]
    ]
    _, result2, resp2 = doc("commit_record", args2, "fatema.begum", "2026-08-21T10:00:00Z")
    line("With the assigned counter-signature", result2.code, GREEN)
    line("The witness claimed", "source_system_readback — a specific, attributable claim")
    line("If rc-002 is later found false", "the witness is slashed too", DIM)
    pause()

    # ---------------------------------------------------------------- Act 6
    act(6, "Seal the period. Then try to hand over only part of it.")
    print(f"    {DIM}This is the one to watch. Every document below is genuine and")
    print(f"    every Merkle proof verifies. The fraud is entirely in the selection.{OFF}\n")

    _, _, sealed = doc("seal_period",
                       {"site": "Gazipur", "record_type": "payroll_register",
                        "period": "2026-07", "record_ids": ["rc-001", "rc-002"],
                        "timestamp": "2026-08-31T18:00:00Z"},
                       "fatema.begum", "2026-08-31T18:00:00Z")
    line("Period sealed", "Gazipur · payroll_register · 2026-07", GREEN)
    line("Records in the period", str(sealed["record_count"]))
    line("Committed root over their ids", sealed["records_root"][:32] + "…")

    honest = net.query(DOCUMENT_CHANNEL, "doccustody", "check_completeness",
                       {"owner_msp": "ApexTextileMSP", "site": "Gazipur",
                        "record_type": "payroll_register", "period": "2026-07",
                        "disclosed_record_ids": ["rc-001", "rc-002"]},
                       consortium.who("james.holloway"))
    line("Buyer shown both registers", "COMPLETE" if honest["complete"] else "INCOMPLETE",
         GREEN if honest["complete"] else RED)

    withheld = net.query(DOCUMENT_CHANNEL, "doccustody", "check_completeness",
                         {"owner_msp": "ApexTextileMSP", "site": "Gazipur",
                          "record_type": "payroll_register", "period": "2026-07",
                          "disclosed_record_ids": ["rc-001"]},
                         consortium.who("james.holloway"))
    print()
    line("Buyer shown only rc-001", "rc-001 itself verifies perfectly", DIM)
    line("Sealed count", str(withheld["sealed_count"]))
    line("Disclosed count", str(withheld["disclosed_count"]))
    line("Sealed root", withheld["sealed_root"][:24] + "…")
    line("Root over what was shown", withheld["computed_root"][:24] + "…")
    line("Complete", "NO — " + withheld["reason"][:52], RED)
    print(f"    {DIM}No document was forged. Nothing was edited. Every other system")
    print(f"    in the comparison table reports this disclosure as clean.{OFF}")
    pause()

    # ---------------------------------------------------------------- Act 7
    act(7, "The whole ledger, in one number")
    group, transcript, _ = run_ceremony(
        "BGMEAConsortiumMSP",
        {"ApexTextileMSP": b"apex-entropy", "BVCertificationMSP": b"bv-entropy"},
        bits=2048,
    )
    install_group(consortium, DOCUMENT_CHANNEL, group, transcript, "2026-09-01T08:00:00Z")
    line("Modulus", f"{group.modulus.bit_length()} bits, from a recorded ceremony")
    line("Ceremony note", "trusted dealer — the transcript says so on-chain", AMBER)

    anchored = anchor_epoch(
        consortium, DOCUMENT_CHANNEL,
        [("record", "rc-001"), ("record", "rc-002"),
         ("seal", "ApexTextileMSP|Gazipur|payroll_register|2026-07")],
        "2026-09-01T08:05:00Z",
    )
    state = net.query(DOCUMENT_CHANNEL, "anchor", "get_state", {},
                      consortium.who("james.holloway"))
    line("Epoch", str(anchored["epoch"]), GREEN)
    line("Elements folded in", f"{anchored['accumulated']} — in ONE ledger write")
    line("Verifier state", f"{(group.modulus.bit_length() + 7) // 8} bytes, whatever the ledger size")

    acc = Accumulator(group=group)
    for entry in sorted((v for _, v in net.state.range(DOCUMENT_CHANNEL, "anchored:")),
                        key=lambda e: (e["epoch"], e["prime_hex"])):
        prime = int(entry["prime_hex"], 16)
        acc.primes.append(prime)
        acc.nonces[prime] = 0
    acc.value = int(state["value_hex"], 16)
    acc.epoch = int(state["epoch"])

    stored = net.query(DOCUMENT_CHANNEL, "doccustody", "get_record", {"record_id": "rc-001"},
                       consortium.who("james.holloway"))
    witness = acc.membership_witness(record_element(stored))
    ok, why = verify_record(consortium, DOCUMENT_CHANNEL, "rc-001", witness,
                            consortium.who("james.holloway"))
    line("rc-001 verifies", "YES — ledger, witness and anchored index all agree" if ok else why,
         GREEN if ok else RED)

    ghost = {"type": "record", "record_id": "ISO45001-CERT-88213", "merkle_root": "0" * 64,
             "bucket": "ApexTextileMSP|Gazipur|compliance_certificate|2026-07",
             "owner_msp": "ApexTextileMSP"}
    absence = acc.non_membership_witness(ghost)
    absent_ok, _ = verify_non_membership(group, acc.value, absence, ghost, acc.epoch)
    print()
    line("A buyer is shown a certificate", "ISO45001-CERT-88213")
    line("Proof of ABSENCE", "verified — it was never committed" if absent_ok else "failed",
         GREEN if absent_ok else RED)
    line("A Merkle tree", "cannot answer this question at any price", DIM)
    pause()

    # ---------------------------------------------------------------- Act 8
    act(8, "Seal the benchmarks before anyone trains")
    admin = consortium.who("rafiqul.islam")
    gate_endorsers = consortium.endorsers(GATE_ORGS[:3])

    print(f"  {DIM}Each task's benchmark is committed by hash and revealed only after the")
    print("  decision. The organisations training this round do not hold the set they")
    print(f"  will be judged against.{OFF}\n")

    trainer = FederatedTrainer(use_replay=True)
    for stage in trainer.stages:
        bench_hash = hash_object(TAG_BENCH, stage.benchmark_payload)
        net.invoke(
            MODEL_CHANNEL, "fedmodel", "commit_benchmark",
            {
                "task_id": stage.task_id, "benchmark_hash": bench_hash,
                "contributors": ["NoorGarmentsMSP", "CrescentFashionMSP"],
                "size": int(len(stage.benchmark_y)),
                "timestamp": "2026-08-19T00:00:00Z",
            },
            admin, gate_endorsers, "2026-08-19T00:00:00Z",
        )
        line(stage.task_id, f"sealed · {bench_hash[:24]}…", GREEN)
    pause()

    # ---------------------------------------------------------------- Act 9
    act(9, "Six factories train, no data moves")
    print(f"  {DIM}Each factory trains locally, clips and noises its update, and the")
    print("  aggregator combines them with a trimmed mean weighted by on-chain")
    print(f"  reputation. Raw records never leave a building.{OFF}\n")

    for stage in (0, 1):
        report = trainer.run_stage(stage)
        acc = trainer.evaluate_all()
        shown = "  ".join(f"{k.split('_')[0]}={v / 100:.1f}" for k, v in acc.items())
        line(f"Stage {stage + 1} · {report.task_id}", shown)

    in_force = trainer.evaluate_all()
    line("Model in force", "m-v7", GREEN)
    line("Memory bank hash", trainer.bank.hash[:32] + "…")
    print(f"\n  {DIM}{trainer.bank.privacy_note()}{OFF}")

    # Stage 3 arrives. Two candidates branch from this same model — the honest
    # comparison, because both are competing to replace m-v7 in the same round.
    candidate_a = deepcopy(trainer)
    candidate_b = deepcopy(trainer)
    candidate_b.use_replay = False  # trained the ordinary way, no rehearsal
    candidate_a.run_stage(2)
    candidate_b.run_stage(2)
    good_accuracies = candidate_a.evaluate_all()
    bad_accuracies = candidate_b.evaluate_all()
    pause()

    # ---------------------------------------------------------------- Act 10
    act(10, "Candidate A goes to the gate")
    print(f"  {DIM}Stage 3 has arrived. Candidate A learned it with rehearsal drawn from")
    print(f"  the shared memory bank. It is judged against m-v7, the model in force.{OFF}\n")
    previous = in_force
    net.invoke(
        MODEL_CHANNEL, "fedmodel", "open_round",
        {
            "round_id": "round-8", "tasks": list(good_accuracies),
            "contributors": [f[0] for f in [("ApexTextileMSP",), ("NoorGarmentsMSP",), ("CrescentFashionMSP",)]],
            "memory_bank_hash": candidate_a.bank.hash,
            "timestamp": "2026-08-20T12:00:00Z",
        },
        admin, gate_endorsers, "2026-08-20T12:00:00Z",
    )
    submissions = candidate_a.signed_evaluations(
        consortium, GATE_ORGS[:3], "round-8", "m-v8-rc1",
        candidate_a.model_hash(), previous, jitter_bp=30,
    )
    line("Independent evaluations", f"{len(submissions)} organisations, each signed")

    _, _, decision = net.invoke(
        MODEL_CHANNEL, "fedmodel", "evaluate_gate",
        {
            "round_id": "round-8", "candidate_id": "m-v8-rc1",
            "candidate_hash": candidate_a.model_hash(), "parent_id": "m-v7",
            "new_task": "chemical_misreporting", "submissions": submissions,
            "gamma_bp": GAMMA_BP, "tau_bp": TAU_BP, "k": 3, "delta_bp": 100,
            "timestamp": "2026-08-20T12:05:00Z",
        },
        admin, gate_endorsers, "2026-08-20T12:05:00Z",
    )
    _print_decision(decision)
    pause()

    # ---------------------------------------------------------------- Act 11
    act(11, "Candidate B has forgotten. Watch the contract refuse it.")
    print(f"  {DIM}This model was trained the ordinary way, without rehearsal. It is the")
    print("  best model yet at the newest problem. It has also lost most of what it")
    print("  knew about wages — and a committee scoring this round's data would not")
    print(f"  notice, because forgetting does not make an update look bad.{OFF}\n")

    print(f"  {DIM}{'task':<34}{'m-v7':>8}{'cand. B':>10}{'change':>9}{OFF}")
    for task in bad_accuracies:
        before, after = in_force[task], bad_accuracies[task]
        delta = (after - before) / 100
        colour = RED if delta < -TAU_BP / 100 else GREEN
        print(
            f"  {task:<34}{before / 100:>7.1f}%{after / 100:>9.1f}%"
            f"{colour}{delta:>+9.1f}{OFF}"
        )

    net.invoke(
        MODEL_CHANNEL, "fedmodel", "open_round",
        {
            "round_id": "round-9", "tasks": list(bad_accuracies),
            "contributors": ["ApexTextileMSP", "NoorGarmentsMSP"],
            "memory_bank_hash": candidate_b.bank.hash,
            "timestamp": "2026-08-21T09:00:00Z",
        },
        admin, gate_endorsers, "2026-08-21T09:00:00Z",
    )
    bad_subs = candidate_b.signed_evaluations(
        consortium, GATE_ORGS[:3], "round-9", "m-v8-rc2",
        candidate_b.model_hash(), in_force, jitter_bp=30,
    )
    _, _, bad_decision = net.invoke(
        MODEL_CHANNEL, "fedmodel", "evaluate_gate",
        {
            "round_id": "round-9", "candidate_id": "m-v8-rc2",
            "candidate_hash": candidate_b.model_hash(), "parent_id": "m-v7",
            "new_task": "chemical_misreporting", "submissions": bad_subs,
            "gamma_bp": GAMMA_BP, "tau_bp": TAU_BP, "k": 3, "delta_bp": 100,
            "timestamp": "2026-08-21T09:05:00Z",
        },
        admin, gate_endorsers, "2026-08-21T09:05:00Z",
    )
    _print_decision(bad_decision)

    current = net.query(
        MODEL_CHANNEL, "fedmodel", "get_current_model", {}, admin
    )
    print()
    line("Model still in force", current["model_id"], GREEN)
    line("Who could override this", "nobody — it is a contract, not a setting", GREEN)

    # ---------------------------------------------------------------- close
    act(12, "The ledger")
    for name, channel in net.channels.items():
        ok, why = channel.verify_chain()
        line(name, f"{channel.height} blocks · integrity {'OK' if ok else 'FAILED: ' + why}",
             GREEN if ok else RED)
    print(f"\n  {DIM}Every decision above can be recomputed by any member from the ledger:")
    print("  the benchmark hashes, the signed metrics, the endorser set and the")
    print(f"  outcome are all committed.{OFF}\n")


def _print_decision(decision: dict) -> None:
    outcome = decision["outcome"]
    colour = GREEN if outcome == "promote" else RED
    verdict = "PROMOTED" if outcome == "promote" else "REJECTED"
    print()
    print(f"  {colour}{BOLD}  {verdict}  {OFF}  {colour}{decision['reason']}{OFF}")
    print(f"  {DIM}reason code: {decision['reason_code']}{OFF}\n")
    if decision["per_task"]:
        print(f"  {DIM}{'task':<32}{'previous':>10}{'candidate':>11}{'change':>9}{'verdict':>9}{OFF}")
        for t in decision["per_task"]:
            mark = "pass" if t["pass"] else "FAIL"
            c = GREEN if t["pass"] else RED
            tag = " (new)" if t["is_new_task"] else ""
            print(
                f"  {t['task_id'] + tag:<32}"
                f"{t['previous_bp'] / 100:>9.1f}%{t['candidate_bp'] / 100:>10.1f}%"
                f"{t['change_bp'] / 100:>+9.1f}{c}{mark:>9}{OFF}"
            )
    print(f"\n  {DIM}endorsed by: {', '.join(decision['endorsers'])}{OFF}")
    print(f"  {DIM}memory bank: {decision['memory_bank_hash'][:32]}…{OFF}")


if __name__ == "__main__":
    main()
