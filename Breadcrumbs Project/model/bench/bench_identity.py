"""
What RSA identities cost, against the Ed25519 baseline they replaced.

This benchmark exists to be quoted against us. The report argues that RSA earns
its place because the identity layer and the accumulator then rest on one
assumption and one ceremony — but that argument is only honest alongside the
bill, and the bill is large: RSA-3072 signing is orders of magnitude slower than
Ed25519 and its signatures are eight times bigger, which lands on every
transaction, every endorsement and every certificate in the system.

Two mitigations are measured here as well, because "it is slower" is not a finding
a reader can act on and "it is slower, and here is what recovers most of it" is.

  Certificate caching. `MSP.public_key_for` parses a PEM certificate, walks the
  issuer chain and checks the CA signature on every endorsement it validates. The
  same handful of certificates appear in every transaction a consortium ever
  processes, so the work is almost entirely repeated.

  Short-circuit policy evaluation. Fabric verifies every endorsement attached to a
  transaction regardless of how many the policy needs. Stopping once the policy is
  satisfied is sound — an unsatisfied policy still verifies everything — and on a
  five-organisation network with a three-of-five policy it removes two RSA
  verifications per transaction.

Run:  python -m model.bench.bench_identity
"""

from __future__ import annotations

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from ..ledger.crypto import canonical, sign, verify
from ..ledger.identity import CertificateAuthority
from ..ledger.suites import ED25519, RSA3072
from .harness import Results, report

PAYLOAD = {
    "channel": "documents-apex-primark",
    "chaincode": "doccustody",
    "function": "commit_record",
    "args": {"record_id": "rc-000412", "merkle_root": "9f" * 32, "row_count": 1847},
}


def MSP_with(ca):
    """A fresh MSP with an empty cache, so a cold resolution is genuinely cold."""
    from ..ledger.identity import MSP

    msp = MSP()
    msp.register(ca)
    return msp


def run() -> Results:
    r = Results(
        name="identity",
        description="RSA-3072 identity and endorsement costs against the Ed25519 baseline",
    )
    message = canonical(PAYLOAD)

    for suite in (ED25519, RSA3072):
        key = suite.generate()
        public = key.public_key()
        signature = suite.sign(key, message)

        # Generation is measured by calling the primitive directly. Going through
        # the suite would draw from the development pool in `devkeys.py` and report
        # a microsecond, which is the speed of reading a file rather than the cost
        # of finding two large primes.
        generator = (
            (lambda: rsa.generate_private_key(public_exponent=65537, key_size=3072))
            if suite is RSA3072
            else suite.generate
        )
        gen = r.time(
            f"{suite.id}: generate a key",
            generator,
            repeats=5 if suite is RSA3072 else 50,
            note="paid once per identity, at issuance; no pool",
        )
        signing = r.time(
            f"{suite.id}: sign a transaction",
            lambda k=key, s=suite: s.sign(k, message),
            repeats=20 if suite is RSA3072 else 200,
        )
        checking = r.time(
            f"{suite.id}: verify a signature",
            lambda p=public, sg=signature, s=suite: s.verify(p, message, sg),
            repeats=50 if suite is RSA3072 else 200,
        )

        ca = CertificateAuthority("BenchMSP", "Bench Org", "factory", suite_id=suite.id)
        identity = ca.issue("bench.operator", "operator")
        cert_pem = identity.certificate_pem()

        r.series.setdefault("suites", []).append(
            {
                "suite": suite.id,
                "keygen_ms": round(gen.median_ms, 4),
                "sign_ms": round(signing.median_ms, 4),
                "verify_ms": round(checking.median_ms, 4),
                "signature_bytes": len(signature),
                "certificate_bytes": len(cert_pem.encode()),
                "public_key_bytes": len(
                    public.public_bytes(
                        encoding=serialization.Encoding.DER,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo,
                    )
                ),
                "disallowed_after": suite.disallowed_after,
            }
        )

    rsa_row = next(s for s in r.series["suites"] if s["suite"] == RSA3072.id)
    ed_row = next(s for s in r.series["suites"] if s["suite"] == ED25519.id)
    r.value("rsaSignSlowdown", round(rsa_row["sign_ms"] / max(ed_row["sign_ms"], 1e-9), 1),
            "how much slower RSA-3072 signing is than Ed25519")
    # RSA verification is FASTER than Ed25519, which is not the result anybody
    # expects and is worth stating plainly: with a small public exponent, checking
    # an RSA signature is one cheap exponentiation, while Ed25519 verification
    # costs more than its own signing. A ledger verifies far more often than it
    # signs — every peer re-checks every endorsement on every transaction — so
    # this lands on the side of the ratio that carries the volume.
    r.value(
        "rsaVerifySpeedup",
        round(ed_row["verify_ms"] / max(rsa_row["verify_ms"], 1e-9), 1),
        "RSA-3072 verification against Ed25519; above 1.0 means RSA is faster",
    )
    r.value("rsaSignatureGrowth", round(rsa_row["signature_bytes"] / ed_row["signature_bytes"], 1),
            "signature size multiple; lands on every transaction")

    # -- what a transaction actually pays -------------------------------
    #
    # An AND(A, B) policy on doccustody means two endorsements, each carrying a
    # certificate that has to be resolved and a signature that has to be checked.
    ca = CertificateAuthority("BenchMSP", "Bench Org", "factory")
    identity = ca.issue("bench.operator", "operator")
    pem = identity.certificate_pem()

    from ..ledger.identity import MSP

    cold = MSP()
    cold.register(ca)
    uncached = r.time(
        "resolve a certificate: cold, per call",
        lambda: MSP_with(ca).public_key_for("BenchMSP", pem),
        repeats=20,
        note="parse the PEM, walk the chain, verify the CA signature",
    )
    warm_msp = MSP()
    warm_msp.register(ca)
    warm_msp.public_key_for("BenchMSP", pem)
    cached = r.time(
        "resolve a certificate: cached",
        lambda: warm_msp.public_key_for("BenchMSP", pem),
        repeats=200,
        note="revocation and validity still re-checked; only the parse is reused",
    )
    r.value(
        "certificateCacheSpeedup",
        round(uncached.median_ms / max(cached.median_ms, 1e-9), 1),
        "the single change that pays for RSA identities",
    )

    signature = sign(identity.private_key, PAYLOAD)
    r.time(
        "verify one endorsement end to end",
        lambda: verify(warm_msp.public_key_for("BenchMSP", pem)[0], PAYLOAD, signature),
        repeats=50,
    )

    # -- short-circuit policy evaluation ---------------------------------
    from ..consortium import GATE_ORGS, MODEL_CHANNEL, build
    from ..ledger import NOutOf

    c = build()
    tx = c.network.propose(
        MODEL_CHANNEL, "fedmodel", "list_models", {},
        submitter=c.who("rafiqul.islam"),
        endorsers=c.endorsers(GATE_ORGS),
        timestamp="2026-08-05T09:14:00Z",
    )
    policy = NOutOf(3, GATE_ORGS)
    validator = c.network.validator
    before = validator.signatures_verified
    validator.check(tx.payload(), tx.endorsements, policy)
    verified = validator.signatures_verified - before
    r.value("endorsementsAttached", len(tx.endorsements))
    r.value("signaturesVerifiedUnderPolicy", verified,
            "a 3-of-5 policy with 5 endorsements attached")
    r.value("signaturesAvoidedPerTransaction", len(tx.endorsements) - verified,
            "RSA verifications removed per transaction, on every peer, forever")

    r.caveat(
        "Key generation for RSA is drawn from a pre-generated development pool in the "
        "test suite but NOT here: this benchmark generates real keys, which is why its "
        "keygen row is the honest number and the test suite's speed is not."
    )
    r.caveat(
        "One machine, CPython, OpenSSL-backed primitives. Ratios between the two suites "
        "will hold on other hardware; absolute figures will not."
    )
    r.caveat(
        "RSA-3072 is disallowed after 2035 under NIST IR 8547. The cost measured here "
        "buys margin, not permanence, which is what the suite registry in "
        "`model/ledger/suites.py` exists to handle."
    )
    return r


def main() -> None:
    results = run()
    report(results)
    print(f"\nwrote {results.write()}")


if __name__ == "__main__":
    main()
