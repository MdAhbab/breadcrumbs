"""
A pool of pre-generated RSA keys, for development only.

WHY THIS EXISTS. RSA-3072 key generation costs about a quarter of a second. A
consortium of seven organisations needs fifteen keys before one test can run, and
the suite builds a fresh consortium for most of its hundred-odd tests. Generating
honestly would take the suite from five seconds to eight minutes, and a test suite
nobody runs is a test suite that stops catching things.

WHAT THIS IS NOT. It is not a security shortcut and it does not weaken any test.
Each key is handed out at most once, so no two identities ever share one, and
every signature check in the suite is a real RSA-PSS verification against a real
certificate chain. What is pre-computed is only the search for two large primes,
which no adversary in any threat model here gets to influence.

**The private keys in `devkeys.pem` are public. Anything signed with them is
signed with a key everyone has.** They exist so the demo starts quickly and the
tests stay fast. A deployment generates keys in a hardware security module and
this file is never loaded — `take_key()` returns None when the pool is absent or
exhausted, and generation falls back to doing the real work.

Regenerate with:  python -m model.ledger.devkeys --count 40
"""

from __future__ import annotations

import argparse
import threading
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

POOL_PATH = Path(__file__).with_name("devkeys.pem")
BANNER = (
    b"# Breadcrumbs development keys. PUBLIC. Never deploy anything signed with these.\n"
)

_lock = threading.Lock()
_pool: list[rsa.RSAPrivateKey] | None = None
_issued = 0


def _load() -> list[rsa.RSAPrivateKey]:
    if not POOL_PATH.exists():
        return []
    keys: list[rsa.RSAPrivateKey] = []
    blob = POOL_PATH.read_bytes()
    marker = b"-----BEGIN PRIVATE KEY-----"
    parts = blob.split(marker)
    for part in parts[1:]:
        pem = marker + part.split(b"-----END PRIVATE KEY-----")[0] + b"-----END PRIVATE KEY-----\n"
        keys.append(serialization.load_pem_private_key(pem, password=None))
    return keys


def take_key() -> rsa.RSAPrivateKey | None:
    """
    Hand out the next unused key, or None when the pool is absent or exhausted.

    Returning None rather than recycling is the important part. A pool that wrapped
    around would silently give two organisations the same key, and every identity
    test in the suite would keep passing while the property it checks had quietly
    become false.
    """
    global _pool, _issued
    with _lock:
        if _pool is None:
            _pool = _load()
        if _issued >= len(_pool):
            return None
        key = _pool[_issued]
        _issued += 1
        return key


def reset() -> None:
    """Rewind the pool. For tests that build many consortia in one process."""
    global _issued
    with _lock:
        _issued = 0


def available() -> int:
    global _pool
    with _lock:
        if _pool is None:
            _pool = _load()
        return max(0, len(_pool) - _issued)


def generate(count: int, bits: int = 3072) -> None:
    """Write a fresh pool. Slow on purpose; run it once, not in a test."""
    out = bytearray(BANNER)
    for i in range(count):
        key = rsa.generate_private_key(public_exponent=65537, key_size=bits)
        out += key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        print(f"  {i + 1}/{count}", end="\r")
    POOL_PATH.write_bytes(bytes(out))
    print(f"\nwrote {count} RSA-{bits} development keys to {POOL_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=40)
    parser.add_argument("--bits", type=int, default=3072)
    generate(**vars(parser.parse_args()))
