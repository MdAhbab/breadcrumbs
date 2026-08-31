"""
Membership Service Provider: who is allowed to speak, and as what.

This is the part that makes the ledger *permissioned*. In a public chain an
identity is a keypair anybody can generate. Here, every participant is a named
organisation that was issued a certificate by a certificate authority the
consortium recognises. A transaction signed by a key with no valid certificate
chain is not a minority opinion, it is not a transaction at all.

Each organisation runs its own CA and issues certificates to its own members.
The consortium's root of trust is the set of organisation CA certificates listed
in the channel configuration, so adding a member is a governance act, not a
technical one.

Roles are carried as an X.509 extension rather than inferred from the
organisation name, because a factory organisation may employ both an operator
who may commit records and a reader who may not.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Literal

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.x509.oid import NameOID

Role = Literal["admin", "operator", "reader", "orderer", "peer"]
OrgKind = Literal["factory", "buyer", "auditor", "consortium", "regulator"]

# An OID under a private arc to carry the Breadcrumbs role. Fabric does the same
# thing with its own OID for "hf.Type".
ROLE_OID = x509.ObjectIdentifier("1.3.6.1.4.1.57264.1.1")

_EPOCH = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)


@dataclass(frozen=True)
class Identity:
    """A signing identity: a certificate plus the key that matches it."""

    msp_id: str
    common_name: str
    role: Role
    certificate: x509.Certificate
    private_key: Ed25519PrivateKey

    @property
    def id(self) -> str:
        """Stable identifier used in read/write sets and endorsement records."""
        return f"{self.msp_id}::{self.common_name}"

    @property
    def public_key(self) -> Ed25519PublicKey:
        return self.certificate.public_key()

    def certificate_pem(self) -> str:
        return self.certificate.public_bytes(serialization.Encoding.PEM).decode()

    def fingerprint(self) -> str:
        return self.certificate.fingerprint(hashes.SHA256()).hex()


class CertificateAuthority:
    """
    One organisation's CA. Issues member certificates under a self-signed root.

    Validity dates are derived from a fixed epoch rather than wall-clock time so
    that a demo run produces the same certificates every time. Real deployments
    would use the actual date; determinism matters more here than realism.
    """

    def __init__(self, msp_id: str, org_name: str, kind: OrgKind, country: str = "BD"):
        self.msp_id = msp_id
        self.org_name = org_name
        self.kind = kind
        self.country = country
        self._key = Ed25519PrivateKey.generate()
        self._serial = 1000
        self.root = self._self_sign()
        self.revoked: set[str] = set()

    def _name(self, common_name: str) -> x509.Name:
        return x509.Name(
            [
                x509.NameAttribute(NameOID.COUNTRY_NAME, self.country),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, self.org_name),
                x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, self.msp_id),
                x509.NameAttribute(NameOID.COMMON_NAME, common_name),
            ]
        )

    def _next_serial(self) -> int:
        self._serial += 1
        return self._serial

    def _self_sign(self) -> x509.Certificate:
        subject = self._name(f"ca.{self.msp_id}")
        return (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(subject)
            .public_key(self._key.public_key())
            .serial_number(self._next_serial())
            .not_valid_before(_EPOCH)
            .not_valid_after(_EPOCH + dt.timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .sign(self._key, None)
        )

    def issue(self, common_name: str, role: Role) -> Identity:
        """Issue a member certificate carrying its role."""
        member_key = Ed25519PrivateKey.generate()
        cert = (
            x509.CertificateBuilder()
            .subject_name(self._name(common_name))
            .issuer_name(self.root.subject)
            .public_key(member_key.public_key())
            .serial_number(self._next_serial())
            .not_valid_before(_EPOCH)
            .not_valid_after(_EPOCH + dt.timedelta(days=730))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(
                x509.UnrecognizedExtension(ROLE_OID, role.encode("utf-8")), critical=False
            )
            .sign(self._key, None)
        )
        return Identity(self.msp_id, common_name, role, cert, member_key)

    def revoke(self, identity: Identity) -> None:
        """Add a certificate to this CA's revocation set."""
        self.revoked.add(identity.fingerprint())


class MSP:
    """
    The consortium's view of who exists.

    Validating an identity means three things, all of which must hold: the
    certificate was issued by a CA this channel recognises, the signature on the
    certificate actually verifies against that CA's key, and the certificate has
    not been revoked. Checking only the first is the classic mistake — it lets
    anyone mint a certificate that merely *claims* the right issuer.
    """

    def __init__(self) -> None:
        self.authorities: dict[str, CertificateAuthority] = {}

    def register(self, ca: CertificateAuthority) -> None:
        self.authorities[ca.msp_id] = ca

    def org_kind(self, msp_id: str) -> OrgKind | None:
        ca = self.authorities.get(msp_id)
        return ca.kind if ca else None

    def validate(self, identity: Identity) -> tuple[bool, str]:
        """Returns (ok, reason). Reason is empty when ok."""
        ca = self.authorities.get(identity.msp_id)
        if ca is None:
            return False, f"unknown MSP {identity.msp_id}"

        if identity.certificate.issuer != ca.root.subject:
            return False, "certificate was not issued by this organisation's CA"

        try:
            ca.root.public_key().verify(
                identity.certificate.signature,
                identity.certificate.tbs_certificate_bytes,
            )
        except Exception:
            return False, "certificate signature does not verify against the CA"

        if identity.fingerprint() in ca.revoked:
            return False, "certificate has been revoked"

        not_after = identity.certificate.not_valid_after_utc
        if not_after < _EPOCH:
            return False, "certificate has expired"

        return True, ""

    def role_of(self, identity: Identity) -> Role | None:
        """Read the role from the certificate, not from the caller's claim."""
        try:
            ext = identity.certificate.extensions.get_extension_for_oid(ROLE_OID)
        except x509.ExtensionNotFound:
            return None
        return ext.value.value.decode("utf-8")  # type: ignore[union-attr]
