"""
Cryptographic suites, and the reason this file exists at all.

A wage register committed in 2026 may have to stay verifiable into the 2040s. That
is an unusual requirement and it makes one question unavoidable, so this codebase
answers it in code rather than in a paragraph: NIST IR 8547 has RSA-2048 and
ECC-256 deprecated by 2030 and disallowed after 2035. Any system putting RSA at
its centre in 2026 has to say what happens to its evidence when that date passes.

The answer is that a commitment records the suite that produced it. Verification
looks the suite up rather than assuming one. Adding a post-quantum suite is then a
new entry in this registry and a re-anchoring transaction, not a migration that
invalidates a decade of proofs. Systems that hard-code their primitives cannot do
this at any price, and that — not key length — is what actually decides whether
long-lived evidence survives a cryptographic transition.

WHAT IS AND IS NOT COVERED. Signatures and identities are suite-tagged and
replaceable. The accumulator is not: it needs a group of unknown order, and no
post-quantum construction with constant-size witnesses is known — Boneh, Bunz and
Fisch raise that as an open problem and it is still open. So the honest position
is that the *hash chain and the Merkle commitments* are the quantum-durable part
of this design, being hash-based, and the accumulator is an accelerator whose
security assumption has a horizon. That is the same reasoning that makes the
trusted-dealer modulus survivable, arrived at from the other direction, and the
report should state it in exactly these terms rather than claim the whole system
is post-quantum ready.

WHY RSA IS THE DEFAULT HERE. It is slower than Ed25519 at signing and verifying,
by a margin this repository measures rather than guesses. What it buys is that the
identity layer and the accumulator live in the same mathematics, so one ceremony,
one parameter set and one security assumption cover the whole system. The cost
appears in `results/identity.json`; a reader is entitled to both halves.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

RSA_KEY_BITS = 3072
RSA_PUBLIC_EXPONENT = 65537


@dataclass(frozen=True)
class Suite:
    """One named set of algorithm choices, and the date it stops being acceptable."""

    id: str
    description: str
    generate: Callable[[], Any]
    sign: Callable[[Any, bytes], bytes]
    verify: Callable[[Any, bytes, bytes], None]  # raises on failure
    certificate_hash: Any  # what x509 CertificateBuilder.sign() expects
    signature_bytes: int
    disallowed_after: str
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "signature_bytes": self.signature_bytes,
            "disallowed_after": self.disallowed_after,
            "note": self.note,
        }


# --------------------------------------------------------------------------
# RSA-3072 with PSS
# --------------------------------------------------------------------------
def _rsa_generate() -> rsa.RSAPrivateKey:
    """
    A fresh RSA-3072 private key, from the development pool where one is available.

    Generation costs roughly a quarter of a second, and a consortium of seven
    organisations needs fifteen keys before a single test can run. Drawing from a
    pool of pre-generated keys is what keeps the suite runnable; each key is handed
    out at most once, so no two identities ever share one. See `devkeys.py` for why
    that file exists and why it is not key material anybody should deploy.
    """
    from .devkeys import take_key

    pooled = take_key()
    if pooled is not None:
        return pooled
    return rsa.generate_private_key(
        public_exponent=RSA_PUBLIC_EXPONENT, key_size=RSA_KEY_BITS
    )


def _rsa_padding() -> padding.PSS:
    """
    PSS, not PKCS#1 v1.5.

    PSS has a security proof; v1.5 has a long history of implementation flaws and
    survives mainly because old systems cannot change. There is no compatibility
    constraint here, so there is no reason to choose the weaker one.
    """
    return padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=hashes.SHA256.digest_size)


def _rsa_sign(key: rsa.RSAPrivateKey, message: bytes) -> bytes:
    return key.sign(message, _rsa_padding(), hashes.SHA256())


def _rsa_verify(public_key: rsa.RSAPublicKey, message: bytes, signature: bytes) -> None:
    public_key.verify(signature, message, _rsa_padding(), hashes.SHA256())


RSA3072 = Suite(
    id="rsa3072-pss-sha256-v1",
    description="RSA-3072 signatures with PSS padding and SHA-256",
    generate=_rsa_generate,
    sign=_rsa_sign,
    verify=_rsa_verify,
    certificate_hash=hashes.SHA256(),
    signature_bytes=RSA_KEY_BITS // 8,
    disallowed_after="2035-12-31",
    note=(
        "NIST IR 8547 deprecates RSA-2048 and ECC-256 by 2030 and disallows them "
        "after 2035. RSA-3072 buys margin, not immunity: commitments that must "
        "outlive it have to be re-anchored under a successor suite."
    ),
)


# --------------------------------------------------------------------------
# Ed25519, kept for comparison and for anything that does not need the group
# --------------------------------------------------------------------------
def _ed_sign(key: Ed25519PrivateKey, message: bytes) -> bytes:
    return key.sign(message)


def _ed_verify(public_key: Ed25519PublicKey, message: bytes, signature: bytes) -> None:
    public_key.verify(signature, message)


ED25519 = Suite(
    id="ed25519-sha256-v1",
    description="Ed25519 signatures",
    generate=Ed25519PrivateKey.generate,
    sign=_ed_sign,
    verify=_ed_verify,
    certificate_hash=None,  # Ed25519 certificates carry no separate hash algorithm
    signature_bytes=64,
    disallowed_after="2035-12-31",
    note=(
        "Faster and far smaller than RSA at equivalent strength. Retained as the "
        "measured baseline, and as the suite to fall back to if the accumulator "
        "were ever dropped."
    ),
)


SUITES: dict[str, Suite] = {s.id: s for s in (RSA3072, ED25519)}

# The consortium's choice. RSA everywhere means the identity layer and the
# accumulator rest on one assumption and one ceremony, which is worth the
# signing cost — a cost this repository measures rather than waves away.
DEFAULT_SUITE_ID = RSA3072.id


def suite(suite_id: str | None = None) -> Suite:
    if suite_id is None:
        return SUITES[DEFAULT_SUITE_ID]
    if suite_id not in SUITES:
        raise KeyError(f"unknown cryptographic suite {suite_id}")
    return SUITES[suite_id]


def suite_for_key(key: Any) -> Suite:
    """
    Identify the suite a key belongs to.

    Dispatching on the key rather than on a caller-supplied string is deliberate.
    A signature verified under the wrong suite is a downgrade attack waiting to
    happen, and the safest way to prevent one is to make the algorithm a property
    of the key material rather than a parameter somebody can pass.
    """
    if isinstance(key, (rsa.RSAPrivateKey, rsa.RSAPublicKey)):
        return RSA3072
    if isinstance(key, (Ed25519PrivateKey, Ed25519PublicKey)):
        return ED25519
    raise TypeError(f"no cryptographic suite handles {type(key).__name__}")


def public_der(public_key: Any) -> str:
    """
    A public key as DER SubjectPublicKeyInfo, hex encoded.

    One encoding for every suite, and self-describing: the algorithm identifier is
    inside the structure, so a stored key cannot be reinterpreted under a different
    algorithm than the one it was written as.
    """
    return public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).hex()


def load_public_der(raw_hex: str) -> Any:
    """Inverse of `public_der`."""
    return serialization.load_der_public_key(bytes.fromhex(raw_hex))
