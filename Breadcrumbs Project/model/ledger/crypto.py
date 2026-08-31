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
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

# Domain-separation tags. Never reuse one for a different structure.
TAG_LEAF = b"breadcrumbs:leaf:v1"
TAG_NODE = b"breadcrumbs:node:v1"
TAG_TX = b"breadcrumbs:tx:v1"
TAG_BLOCK = b"breadcrumbs:block:v1"
TAG_MODEL = b"breadcrumbs:model:v1"
TAG_BENCH = b"breadcrumbs:benchmark:v1"
TAG_BANK = b"breadcrumbs:memorybank:v1"
TAG_PROPOSAL = b"breadcrumbs:proposal:v1"


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
def generate_signing_key() -> Ed25519PrivateKey:
    """Ed25519: small keys, small signatures, no parameter choices to get wrong."""
    return Ed25519PrivateKey.generate()


def sign(key: Ed25519PrivateKey, payload: Any) -> str:
    """Sign the canonical encoding of a payload. Returns hex."""
    return key.sign(canonical(payload)).hex()


def verify(public_key: Ed25519PublicKey, payload: Any, signature: str) -> bool:
    """Check a signature against the canonical encoding of a payload."""
    try:
        public_key.verify(bytes.fromhex(signature), canonical(payload))
        return True
    except (InvalidSignature, ValueError):
        return False


def public_bytes(public_key: Ed25519PublicKey) -> str:
    """Raw public key as hex, for storing in the world state."""
    return public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()


def load_public(raw_hex: str) -> Ed25519PublicKey:
    """Inverse of public_bytes."""
    return Ed25519PublicKey.from_public_bytes(bytes.fromhex(raw_hex))
