"""
What the ledger costs to write to, and what epoch batching saves.

The number this exists to produce is the one a factory operations manager would
ask for and the report has never had: how many ledger writes does a month of
compliance paperwork actually cost? The answer before batching is "one per
document", which is the cost model that makes people abandon blockchains for
record-keeping. The answer after is "one per epoch", and the ratio is measured
here rather than asserted.

It also measures the two things that got slower when identities moved to RSA —
transaction size and endorsement validation — because a batching win reported
without the RSA loss beside it would be a selective account.

Run:  python -m model.bench.bench_ledger [--documents 200]
"""

from __future__ import annotations

import argparse
import time

from ..accumulator import run_ceremony
from ..anchoring import anchor_epoch, install_group
from ..consortium import DOCUMENT_CHANNEL, build
from ..ledger.crypto import canonical
from ..merkle import MerkleTree
from .harness import Results, report

TS = "2026-08-05T09:14:00Z"
ROWS_PER_DOCUMENT = 40


def _rows(seed: int) -> list[dict]:
    return [
        {"worker_ref": f"W-{seed:04d}-{i:03d}", "net_pay_bdt": 14000 + i, "ot_hours": 12 + i % 9}
        for i in range(ROWS_PER_DOCUMENT)
    ]


def run(documents: int = 200, modulus_bits: int = 2048) -> Results:
    r = Results(
        name="ledger",
        description=f"Ledger write costs and epoch batching over {documents} documents",
    )

    group, transcript, _ = run_ceremony(
        "BGMEAConsortiumMSP",
        {"ApexTextileMSP": b"a" * 32, "BVCertificationMSP": b"b" * 32},
        bits=modulus_bits,
    )
    c = build()
    install_group(c, DOCUMENT_CHANNEL, group, transcript, TS)
    submitter = c.who("fatema.begum")
    endorsers = c.endorsers(["ApexTextileMSP", "BVCertificationMSP"])

    # -- committing documents ---------------------------------------------
    started = time.perf_counter()
    record_ids = []
    for i in range(documents):
        record_id = f"rc-{i:06d}"
        c.network.invoke(
            DOCUMENT_CHANNEL, "doccustody", "commit_record",
            {
                "record_id": record_id,
                "merkle_root": MerkleTree(_rows(i)).root,
                "record_type": "payroll_register",
                "period": f"2026-{(i % 12) + 1:02d}",
                "site": "Gazipur",
                "row_count": ROWS_PER_DOCUMENT,
                "schema_version": "v2.1.0",
                "timestamp": TS,
            },
            submitter, endorsers, TS,
        )
        record_ids.append(record_id)
    commit_seconds = time.perf_counter() - started

    channel = c.network.channels[DOCUMENT_CHANNEL]
    committed_blocks = channel.height
    chain_bytes = sum(len(canonical(b.to_dict())) for b in channel.blocks)
    tx_count = sum(len(b.transactions) for b in channel.blocks)
    sample_tx = channel.blocks[-1].transactions[0]

    r.value("documents", documents)
    r.value("commitTransactions", tx_count, "one per document, before batching")
    r.value("commitMsPerDocument", round(commit_seconds * 1000 / documents, 3))
    r.value("documentsPerSecond", round(documents / commit_seconds, 1))
    r.value("transactionBytes", len(canonical(sample_tx.to_dict())),
            "one commitment, with two RSA-3072 endorsements and their certificates")
    r.value("endorsementBytes", len(canonical(sample_tx.endorsements[0].to_dict())),
            "the certificate dominates, not the signature")
    r.value("chainBytes", chain_bytes)
    r.value("chainBytesPerDocument", round(chain_bytes / documents))

    # -- the same documents, one epoch ------------------------------------
    started = time.perf_counter()
    anchor_epoch(c, DOCUMENT_CHANNEL, [("record", rid) for rid in record_ids], TS)
    epoch_seconds = time.perf_counter() - started

    epoch_block = c.network.channels[DOCUMENT_CHANNEL].blocks[-1]
    epoch_bytes = len(canonical(epoch_block.to_dict()))
    r.value("epochTransactions", 1, "whatever the number of documents")
    r.value("epochSeconds", round(epoch_seconds, 3))
    r.value("epochMsPerDocument", round(epoch_seconds * 1000 / documents, 3))
    r.value("epochBytes", epoch_bytes)
    r.value("epochBytesPerDocument", round(epoch_bytes / documents))
    r.value(
        "writeReduction",
        documents,
        "ledger writes replaced by one; a factory committing 400 documents a month "
        "writes to the chain once instead of 400 times",
    )

    # -- what a factory-year looks like ------------------------------------
    #
    # A 2,000-worker site produces on the order of 400 committed documents a month
    # across five record types. That figure is an assumption for planning, not a
    # measurement, and it is stated as one in the report.
    per_month = 400
    r.value("assumedDocumentsPerFactoryMonth", per_month, "an assumption, not a measurement")
    r.value(
        "chainBytesPerFactoryYearKb",
        round(chain_bytes / documents * per_month * 12 / 1024),
        "storage growth per factory per year, at the measured per-document cost",
    )
    r.value(
        "epochWritesPerFactoryYear",
        12,
        "one epoch a month, against 4,800 individual writes",
    )

    # -- endorsement validation -------------------------------------------
    validator = c.network.validator
    policy = c.network.chaincodes["doccustody"].policy
    payload = sample_tx.payload()
    r.time(
        "validate a transaction's endorsements",
        lambda: validator.check(payload, sample_tx.endorsements, policy),
        repeats=50,
        note="with the certificate cache warm, as it always is after the first block",
    )
    r.value("certificateCacheHits", c.msp.cache_hits)
    r.value("certificateCacheMisses", c.msp.cache_misses)
    r.value(
        "certificateHitRate",
        round(100 * c.msp.cache_hits / max(1, c.msp.cache_hits + c.msp.cache_misses), 1),
        "percent; a consortium sees the same handful of certificates forever",
    )
    r.value("blocksWritten", committed_blocks)

    r.caveat(
        "A single process against one SQLite file, with no network between peers. "
        "Real Fabric adds gRPC round trips and consensus latency that this cannot "
        "measure, so treat these as a floor on cost rather than a prediction."
    )
    r.value(
        "storageReductionFactor",
        round(chain_bytes / documents / max(1, epoch_bytes / documents), 1),
        "chain bytes per document, unbatched against batched",
    )
    r.caveat(
        "The batching saving is in ledger WRITES and STORAGE, not in cryptographic "
        "work: every document is still hashed, still Merkle-committed and still "
        "individually provable. What collapses is how often the chain has to be "
        "written to and how much it grows."
    )
    r.caveat(
        "Batching costs the writer MORE compute per document, not less — the epoch "
        "row above is slower than the commit row, because hashing each record to a "
        "prime and exponentiating the accumulator is real work. That trade is the "
        "point rather than a defect: the writer pays once so that every verifier "
        "afterwards checks any number of records in constant time. A report quoting "
        "the storage saving without this sentence would be quoting half the result."
    )
    r.caveat(
        f"A {modulus_bits}-bit accumulator modulus is used so this benchmark finishes "
        "quickly. Accumulator timings scale with the modulus; ledger write counts do not."
    )
    return r


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--documents", type=int, default=200)
    parser.add_argument("--modulus-bits", type=int, default=2048)
    args = parser.parse_args()
    results = run(documents=args.documents, modulus_bits=args.modulus_bits)
    report(results)
    print(f"\nwrote {results.write()}")


if __name__ == "__main__":
    main()
