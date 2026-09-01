"""
Cryptographic primitives for the Breadcrumbs ledger.

Two rules govern everything in this file.

Domain separation. Every hash is prefixed with a tag naming what is being
hashed. Without it, a leaf hash and an internal Merkle node hash could collide,
and an attacker could pass off a subtree as a leaf. This is the second-preimage
attack on naive Merkle trees, and the fix costs one string.

Determinism. Chaincode runs on every endorsing peer and the results must agree
byte for byte. Anything hashed here is first serialised canonically: sorted
keys, no insignificant whitespace, integers rather than floats. Floating point
is banned from anything that reaches a hash or a contract decision.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from typing import Any

from cryptography.exceptions import InvalidSignature

from .suites import load_public_der, public_der, suite, suite_for_key

# Domain-separation tags. Never reuse one for a different structure.
TAG_LEAF = b"breadcrumbs:leaf:v1"
TAG_NODE = b"breadcrumbs:node:v1"
TAG_TX = b"breadcrumbs:tx:v1"
TAG_BLOCK = b"breadcrumbs:block:v1"
TAG_MODEL = b"breadcrumbs:model:v1"
TAG_BENCH = b"breadcrumbs:benchmark:v1"
TAG_BANK = b"breadcrumbs:memorybank:v1"
TAG_PROPOSAL = b"breadcrumbs:proposal:v1"
TAG_PUBLIC_LEAF = b"breadcrumbs:publicleaf:v1"
TAG_SEAL = b"breadcrumbs:seal:v1"


def canonical(obj: Any) -> bytes:
    """
    Serialise to the one byte string every peer will agree on.

    sort_keys makes dictionary ordering irrelevant. The tight separators remove
    the whitespace that different json versions disagree about. allow_nan is off
    because NaN and Infinity are not valid JSON and not deterministic anyway.
    """
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def h(tag: bytes, *parts: bytes) -> str:
    """Tagged SHA-256 over a sequence of byte strings, returned as hex."""
    d = hashlib.sha256()
    d.update(tag)
    for p in parts:
        # Length-prefix each part so that concatenation is unambiguous:
        # h(b"ab", b"c") must not equal h(b"a", b"bc").
        d.update(len(p).to_bytes(8, "big"))
        d.update(p)
    return d.hexdigest()


def hash_object(tag: bytes, obj: Any) -> str:
    """Tagged hash of any JSON-serialisable object."""
    return h(tag, canonical(obj))


def leaf_hash(value: Any, salt: str) -> str:
    """
    Hash one record line for a Merkle tree.

    The salt matters more than it looks. A wage register has low-entropy rows:
    an attacker who suspects a worker earned 14,820 BDT can hash that guess and
    compare. A per-record salt, held by the factory and released only with the
    proof, makes that guessing attack useless.
    """
    return h(TAG_LEAF, canonical(value), salt.encode("utf-8"))


def node_hash(left: str, right: str) -> str:
    """Hash two Merkle children into their parent."""
    return h(TAG_NODE, bytes.fromhex(left), bytes.fromhex(right))


def new_salt() -> str:
    """A fresh 128-bit salt, hex encoded."""
    return secrets.token_hex(16)


# --------------------------------------------------------------------------
# Signing
# --------------------------------------------------------------------------
# The algorithm is a property of the key, not an argument. See `suites.py`:
# choosing the algorithm from a caller-supplied string is how downgrade attacks
# get in, and there is no reason to accept the risk when the key already knows.
def generate_signing_key(suite_id: str | None = None) -> Any:
    """A private key in the consortium's suite, RSA-3072 unless told otherwise."""
    return suite(suite_id).generate()


def sign(key: Any, payload: Any) -> str:
    """Sign the canonical encoding of a payload. Returns hex."""
    return suite_for_key(key).sign(key, canonical(payload)).hex()


def verify(public_key: Any, payload: Any, signature: str) -> bool:
    """
    Check a signature against the canonical encoding of a payload.

    A key of one suite presented with a signature of another fails here rather
    than raising, which is what callers expect: every caller in this codebase
    treats a False as "rejected" and would otherwise have to catch a TypeError
    to avoid turning a forged signature into a crashed peer.
    """
    try:
        suite_for_key(public_key).verify(public_key, canonical(payload), bytes.fromhex(signature))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def public_bytes(public_key: Any) -> str:
    """Public key as DER SubjectPublicKeyInfo, hex encoded, for the world state."""
    return public_der(public_key)


def load_public(raw_hex: str) -> Any:
    """Inverse of public_bytes."""
    return load_public_der(raw_hex)
