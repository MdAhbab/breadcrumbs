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
from typing import Any, Literal

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.x509.oid import NameOID

from .suites import DEFAULT_SUITE_ID, Suite, suite

Role = Literal["admin", "operator", "reader", "orderer", "peer"]
OrgKind = Literal["factory", "buyer", "auditor", "consortium", "regulator"]

# An OID under a private arc to carry the Breadcrumbs role. Fabric does the same
# thing with its own OID for "hf.Type".
ROLE_OID = x509.ObjectIdentifier("1.3.6.1.4.1.57264.1.1")

_EPOCH = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)


@dataclass(frozen=True)
class Identity:
    """A signing identity: a certificate plus the key that matches it."""

    msp_id: str
    common_name: str
    role: Role
    certificate: x509.Certificate
    private_key: Any
    suite_id: str = DEFAULT_SUITE_ID

    @property
    def id(self) -> str:
        """Stable identifier used in read/write sets and endorsement records."""
        return f"{self.msp_id}::{self.common_name}"

    @property
    def public_key(self) -> Any:
        return self.certificate.public_key()

    @property
    def suite(self) -> Suite:
        return suite(self.suite_id)

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

    def __init__(
        self,
        msp_id: str,
        org_name: str,
        kind: OrgKind,
        country: str = "BD",
        suite_id: str = DEFAULT_SUITE_ID,
    ):
        self.msp_id = msp_id
        self.org_name = org_name
        self.kind = kind
        self.country = country
        self.suite = suite(suite_id)
        self.suite_id = suite_id
        self._key = self.suite.generate()
        self._serial = 1000
        self.root = self._self_sign()
        self.revoked: set[str] = set()
        # Bumped on every revocation. Anything caching a validation decision has
        # to notice when a certificate is withdrawn, and a counter is the cheapest
        # way to make a stale cache entry impossible rather than merely unlikely.
        self.generation = 0

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
            .sign(self._key, self.suite.certificate_hash)
        )

    def issue(self, common_name: str, role: Role) -> Identity:
        """Issue a member certificate carrying its role."""
        member_key = self.suite.generate()
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
            .sign(self._key, self.suite.certificate_hash)
        )
        return Identity(self.msp_id, common_name, role, cert, member_key, self.suite_id)

    def revoke(self, identity: Identity) -> None:
        """Add a certificate to this CA's revocation set."""
        self.revoked.add(identity.fingerprint())
        self.generation += 1


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
        # (msp_id, generation, pem) -> (certificate, public key). See public_key_for.
        self._resolved: dict[tuple[str, int, str], tuple[x509.Certificate, Any]] = {}
        self.cache_hits = 0
        self.cache_misses = 0

    def register(self, ca: CertificateAuthority) -> None:
        self.authorities[ca.msp_id] = ca

    def org_kind(self, msp_id: str) -> OrgKind | None:
        ca = self.authorities.get(msp_id)
        return ca.kind if ca else None

    def validate(self, identity: Identity) -> tuple[bool, str]:
        """Returns (ok, reason). Reason is empty when ok."""
        return self.validate_certificate(identity.msp_id, identity.certificate)

    def validate_certificate(
        self, msp_id: str, certificate: x509.Certificate, now: dt.datetime | None = None
    ) -> tuple[bool, str]:
        """
        The single place a certificate is judged.

        Everything that accepts a signature must come through here, because the
        signature alone proves only that whoever holds *some* private key signed
        the bytes. It says nothing about who they are. Binding the key to a
        certificate this MSP issued is what turns a signature into an identity.
        """
        ok, reason = self._check_chain(msp_id, certificate)
        if not ok:
            return False, reason
        return self._check_standing(msp_id, certificate, now)

    def _check_chain(self, msp_id: str, certificate: x509.Certificate) -> tuple[bool, str]:
        """
        The part of validation that can never change: who issued this certificate.

        Split out from `_check_standing` because it is the expensive half — an RSA
        signature verification over the certificate body — and because its answer
        is fixed for the life of the certificate. That combination is exactly what
        makes it safe to cache, and the other half is exactly what is not.
        """
        ca = self.authorities.get(msp_id)
        if ca is None:
            return False, f"unknown MSP {msp_id}"

        if certificate.issuer != ca.root.subject:
            return False, "certificate was not issued by this organisation's CA"

        try:
            # Delegated rather than hand-rolled, because the verification differs
            # per algorithm — RSA needs a padding scheme and a hash that Ed25519
            # does not take at all — and a hand-rolled check that silently used
            # the wrong padding would accept certificates it should refuse.
            certificate.verify_directly_issued_by(ca.root)
        except Exception:
            return False, "certificate signature does not verify against the CA"
        return True, ""

    def _check_standing(
        self, msp_id: str, certificate: x509.Certificate, now: dt.datetime | None = None
    ) -> tuple[bool, str]:
        """
        The part of validation that changes with time and with governance.

        Never cached, and re-run on every single resolution including cache hits.
        A revoked certificate must stop working the moment it is revoked, and an
        expired one the moment it expires; an optimisation that skipped either
        would be the kind that turns a fast system into a broken one.
        """
        ca = self.authorities.get(msp_id)
        if ca is None:
            return False, f"unknown MSP {msp_id}"

        fingerprint = certificate.fingerprint(hashes.SHA256()).hex()
        if fingerprint in ca.revoked:
            return False, "certificate has been revoked"

        # Compare against the actual clock. Comparing against the issuance epoch
        # made this branch unreachable, so an expired certificate would have been
        # accepted for as long as the process ran.
        now = now or dt.datetime.now(dt.UTC)
        if certificate.not_valid_after_utc < now:
            return False, f"certificate expired on {certificate.not_valid_after_utc:%Y-%m-%d}"
        if certificate.not_valid_before_utc > now:
            return False, "certificate is not yet valid"

        return True, ""

    def public_key_for(self, msp_id: str, certificate_pem: str) -> tuple[Any | None, str]:
        """
        Resolve a PEM certificate to a usable public key, or say why not.

        This is what an endorsement carries. Accepting a bare public key instead
        would mean anyone could generate a keypair, name any organisation, and
        have the signature counted — which makes an endorsement policy
        decorative.
        """
        ca = self.authorities.get(msp_id)
        if ca is None:
            return None, f"unknown MSP {msp_id}"

        # The expensive half is cached; the time-varying half never is.
        #
        # Parsing a PEM certificate and verifying the CA's RSA signature over it
        # costs far more than everything else in transaction validation, and the
        # same handful of certificates arrive on every transaction a consortium
        # ever processes. Caching that is the single change that pays for RSA
        # identities.
        #
        # What is deliberately NOT cached is revocation and the validity window,
        # because both change with time and with governance. The cache key carries
        # the CA's revocation generation so a revoked certificate cannot be served
        # from a stale entry, and the dates are re-checked on every hit. A cache
        # that skipped those would turn a performance optimisation into a
        # security hole, which is the usual way this optimisation goes wrong.
        key = (msp_id, ca.generation, certificate_pem)
        cached = self._resolved.get(key)
        if cached is not None:
            self.cache_hits += 1
            certificate, public_key = cached
            ok, reason = self._check_standing(msp_id, certificate)
            return (public_key, "") if ok else (None, reason)

        self.cache_misses += 1
        try:
            certificate = x509.load_pem_x509_certificate(certificate_pem.encode())
        except Exception:
            return None, "malformed certificate"

        ok, reason = self.validate_certificate(msp_id, certificate)
        if not ok:
            return None, reason

        subject_ou = certificate.subject.get_attributes_for_oid(
            NameOID.ORGANIZATIONAL_UNIT_NAME
        )
        if not subject_ou or subject_ou[0].value != msp_id:
            return None, f"certificate subject does not belong to {msp_id}"

        public_key = certificate.public_key()
        self._resolved[key] = (certificate, public_key)
        return public_key, ""

    def role_of(self, identity: Identity) -> Role | None:
        """Read the role from the certificate, not from the caller's claim."""
        try:
            ext = identity.certificate.extensions.get_extension_for_oid(ROLE_OID)
        except x509.ExtensionNotFound:
            return None
        return ext.value.value.decode("utf-8")  # type: ignore[union-attr]
