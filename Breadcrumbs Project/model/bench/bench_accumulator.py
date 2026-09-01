"""
What the accumulator costs, and what it saves.

This benchmark is written to be able to embarrass its own design. Three of the
comparisons below are ones the accumulator can lose, and they are here because a
performance section that only reports wins is not evidence, it is advertising.
Specifically:

  * Against a Merkle proof, accumulator verification is NOT faster per record.
    Modular exponentiation on a 3072-bit modulus is expensive; SHA-256 is not.
    Where the accumulator wins is in what the verifier has to HOLD and RECEIVE,
    and in answering questions a Merkle tree cannot answer at all.
  * RSA is slower than Ed25519 at everything except the things only it can do.
  * A proof of exponentiation is worthless for a single record and decisive for
    an epoch, and the crossover is a measured quantity rather than a claim.

Run:  python -m model.bench.bench_accumulator [--bits 3072] [--quick]
"""

from __future__ import annotations

import argparse
import time

from ..accumulator import (
    Accumulator,
    AggregateWitness,
    RSAGroup,
    hash_to_prime,
    vdf,
    verify_prime,
)
from ..accumulator.accumulator import (
    _root_factor,
    prove_exponentiation,
    verify_aggregate,
    verify_batch_update,
    verify_exponentiation,
    verify_membership,
)
from ..ledger.crypto import TAG_LEAF, h
from ..merkle import MerkleTree
from .harness import Results, report

HASH_BYTES = 32


def _record(i: int) -> dict:
    return {"record_id": f"rc-{i:06d}", "merkle_root": f"{i:064x}", "period": "2026-07"}


def run(bits: int = 3072, quick: bool = False) -> Results:
    sizes = [25, 50, 100] if quick else [50, 100, 250, 500]
    vdf_iterations = [1_000, 5_000] if quick else [1_000, 10_000, 50_000, 200_000]

    # The naive-witness comparison is quadratic in n AND cubic-ish in the modulus
    # size, so the sizes that finish in seconds at 1024 bits take twenty minutes at
    # 3072. Scaling them down keeps the demonstration — the speed-up ratio is what
    # the table reports, and it is already unambiguous at these sizes — while
    # keeping `make bench` runnable. Reporting a ratio measured at n=50 as though
    # it were measured at n=500 would not be, which is why the table prints n.
    if quick:
        naive_sizes = [25, 50]
    elif bits >= 3072:
        naive_sizes = [20, 40, 80]
    else:
        naive_sizes = [50, 100, 200]

    r = Results(
        name="accumulator",
        description=f"RSA accumulator costs and savings, {bits}-bit modulus",
    )

    print(f"generating a {bits}-bit modulus...")
    t0 = time.perf_counter()
    group, _, _ = RSAGroup.generate_untrusted(bits)
    r.value("modulusBits", bits)
    r.value("modulusGenerationSeconds", round(time.perf_counter() - t0, 3),
            "one-off, at consortium formation")
    r.value("accumulatorStateBytes", (bits + 7) // 8,
            "one group element: the entire verifier state, whatever the ledger size")

    # -- 1. the hash-to-prime asymmetry -----------------------------------
    payload = _record(1)
    prime, nonce = hash_to_prime(payload)
    find = r.time("hash to prime: search", lambda: hash_to_prime(_record(int(time.perf_counter() * 1e6) % 10**6)), repeats=10,
                  note="the writer pays this once per record")
    check = r.time("hash to prime: verify with nonce", lambda: verify_prime(payload, prime, nonce), repeats=50,
                   note="every verifier afterwards pays only this")
    r.value("hashToPrimeSpeedup", round(find.median_ms / max(check.median_ms, 1e-9), 1),
            "search cost divided by verification cost")

    # -- 2. writing --------------------------------------------------------
    acc = Accumulator(group=group)
    r.time("accumulator: add one record", lambda: Accumulator(group=group).add(_record(0)), repeats=10)

    records = [_record(i) for i in range(max(sizes))]
    t0 = time.perf_counter()
    elements, batch_proof = acc.batch_add(records)
    batch_seconds = time.perf_counter() - t0
    r.value("batchAddRecords", len(records))
    r.value("batchAddMsPerRecord", round(batch_seconds * 1000 / len(records), 4))

    # -- 3. issuing witnesses: naive against RootFactor --------------------
    for n in naive_sizes:
        sub = acc.primes[:n]
        naive = r.time(
            f"issue {n} witnesses, one at a time",
            lambda sub=sub: [
                group.exp(group.generator, _product_excluding(sub, i)) for i in range(len(sub))
            ],
            repeats=1,
            note="quadratic; the obvious implementation",
        )
        fast = r.time(
            f"issue {n} witnesses, RootFactor",
            lambda sub=sub: _root_factor(group, group.generator, sub),
            repeats=1,
            note="n log n",
        )
        r.series.setdefault("witnessIssuance", []).append(
            {
                "n": n,
                "naive_ms": round(naive.median_ms, 3),
                "rootfactor_ms": round(fast.median_ms, 3),
                "speedup": round(naive.median_ms / max(fast.median_ms, 1e-9), 2),
            }
        )

    # -- 4. verification, bandwidth and state, against Merkle --------------
    #
    # The comparison is deliberately the realistic one. A light verifier that
    # wants to be sure n records are committed, WITHOUT holding the chain, needs
    # either n block-inclusion proofs or one aggregate witness. Comparing against
    # "look up n hashes in a list you already trust" would be comparing against
    # a verifier that has already assumed the answer.
    for n in sizes:
        subset = records[:n]
        aggregate = acc.aggregate(subset)
        plain = AggregateWitness(primes=aggregate.primes, witness=aggregate.witness, epoch=aggregate.epoch)
        agg_t = r.time(
            f"verify {n} records: aggregate witness with batching proof",
            lambda a=aggregate: verify_aggregate(group, acc.value, a, acc.epoch),
            repeats=3,
        )
        plain_t = r.time(
            f"verify {n} records: aggregate witness, no batching proof",
            lambda a=plain: verify_aggregate(group, acc.value, a, acc.epoch),
            repeats=3,
            note="the naive relation check, for comparison",
        )

        tx_ids = [h(TAG_LEAF, f"tx-{i}".encode()) for i in range(max(1024, n * 4))]
        tree = MerkleTree(tx_ids)
        proofs = [tree.prove(i, "block", "tx") for i in range(n)]
        merkle_t = r.time(
            f"verify {n} records: {n} block-inclusion proofs",
            lambda p=proofs, t=tree: [_verify_path(step, t.root) for step in p],
            repeats=3,
        )

        agg_bytes = (bits + 7) // 8 + n * 32
        merkle_bytes = sum(len(p.path) * HASH_BYTES + HASH_BYTES for p in proofs)
        r.series.setdefault("verification", []).append(
            {
                "n": n,
                "aggregate_ms": round(agg_t.median_ms, 4),
                "aggregate_unproved_ms": round(plain_t.median_ms, 4),
                "merkle_ms": round(merkle_t.median_ms, 4),
                "aggregate_proof_bytes": agg_bytes,
                "merkle_proof_bytes": merkle_bytes,
                "verifier_state_bytes_accumulator": (bits + 7) // 8,
                "verifier_state_bytes_roots": n * HASH_BYTES,
            }
        )

    single = acc.membership_witness(records[0])
    one = r.time(
        "verify one membership witness",
        lambda: verify_membership(group, acc.value, single, records[0], acc.epoch),
        repeats=10,
    )
    r.value("singleWitnessMs", round(one.median_ms, 3))

    largest = max(sizes)
    biggest = next(row for row in r.series["verification"] if row["n"] == largest)
    r.value("aggregateRecords", largest)
    r.value("aggregateProvedMs", biggest["aggregate_ms"],
            "one aggregate witness with its batching proof")
    r.value("aggregateUnprovedMs", biggest["aggregate_unproved_ms"],
            "the same witness checked by the naive relation")
    r.value("merkleProofsMs", biggest["merkle_ms"],
            "the comparison the accumulator loses on raw time")
    r.value("aggregateBatchingSpeedup",
            round(biggest["aggregate_unproved_ms"] / max(biggest["aggregate_ms"], 1e-9), 1))
    r.value("verifierStateRootsBytes", biggest["verifier_state_bytes_roots"],
            "what a verifier would hold without the accumulator")

    # -- 5. the epoch proof -------------------------------------------------
    start = group.normalise(group.generator)
    primes = [p for p, _ in elements]
    poe = r.time(
        f"verify an epoch of {len(primes)} records by proof of exponentiation",
        lambda: verify_batch_update(group, start, primes, acc.value, batch_proof),
        repeats=3,
        note="two exponentiations by a 128-bit prime, whatever the epoch size",
    )
    recompute = r.time(
        "verify the same epoch by recomputing it",
        lambda: group.exp(start, _product(primes)) == acc.value,
        repeats=3,
        note="what a verifier without the proof has to do",
    )
    # Stable names, independent of the batch size. The timing labels above carry
    # the record count in them, which makes the macro they generate change every
    # time the benchmark is run at a different scale — and a report referring to a
    # macro that no longer exists prints ?? for a number that was in fact measured.
    r.value("epochProofMs", round(poe.median_ms, 3),
            "verify an epoch through its proof of exponentiation")
    r.value("epochRecomputeMs", round(recompute.median_ms, 3),
            "verify the same epoch by recomputing it")
    r.value("epochRecords", len(primes))
    r.value("epochProofSpeedup", round(recompute.median_ms / max(poe.median_ms, 1e-9), 2))

    big = 1
    for p in primes:
        big *= p
    r.value("epochExponentBits", big.bit_length(),
            f"the exponent a verifier avoids forming, for {len(primes)} records")

    # -- 6. the delay function ---------------------------------------------
    x = group.element_from({"epoch": 1})
    for iterations in vdf_iterations:
        t0 = time.perf_counter()
        y, proof = vdf.evaluate(group, x, iterations)
        eval_ms = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        ok, _ = vdf.verify(group, x, y, proof)
        verify_ms = (time.perf_counter() - t0) * 1000
        assert ok
        r.series.setdefault("vdf", []).append(
            {
                "iterations": iterations,
                "eval_ms": round(eval_ms, 3),
                "verify_ms": round(verify_ms, 4),
                "ratio": round(eval_ms / max(verify_ms, 1e-9), 1),
            }
        )

    # -- 7. proof of exponentiation crossover -------------------------------
    for n in [1, 2, 5, 10, 25, 50, 100]:
        if n > len(primes):
            break
        exponent = _product(primes[:n])
        result = group.exp(start, exponent)
        proof = prove_exponentiation(group, start, exponent, result)
        with_proof = _median_ms(
            lambda e=exponent, res=result, pf=proof: verify_exponentiation(group, start, e, res, pf)
        )
        direct = _median_ms(lambda e=exponent, res=result: group.exp(start, e) == res)
        r.series.setdefault("poeCrossover", []).append(
            {"n": n, "with_proof_ms": round(with_proof, 4), "direct_ms": round(direct, 4)}
        )

    r.caveat(
        "One machine, one process, CPython's built-in big integers. A production "
        "deployment would use a GMP-backed modular exponentiation and should expect "
        "roughly an order of magnitude better on every RSA row."
    )
    r.caveat(
        "Accumulator verification is not faster than Merkle verification per record "
        "and this benchmark shows that. The saving is in verifier state and proof "
        "bandwidth, and in answering absence and completeness, which Merkle proofs "
        "cannot answer at any price."
    )
    r.caveat(
        "The modulus here is locally generated with known factors so the benchmark "
        "is reproducible. Timings are unaffected; the security argument is not the "
        "same one a deployment would make."
    )
    return r


def _product(primes: list[int]) -> int:
    out = 1
    for p in primes:
        out *= p
    return out


def _product_excluding(primes: list[int], index: int) -> int:
    out = 1
    for i, p in enumerate(primes):
        if i != index:
            out *= p
    return out


def _verify_path(disclosure, root: str) -> bool:
    from ..merkle import verify_disclosure

    ok, _, _ = verify_disclosure(disclosure, root)
    return ok


def _median_ms(fn, repeats: int = 5) -> float:
    import statistics

    samples = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000)
    return statistics.median(samples)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bits", type=int, default=3072)
    parser.add_argument("--quick", action="store_true", help="smaller sizes, for a sanity run")
    args = parser.parse_args()

    results = run(bits=args.bits, quick=args.quick)
    report(results)
    print(f"\nwrote {results.write()}")


if __name__ == "__main__":
    main()
