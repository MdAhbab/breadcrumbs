"""
Cryptographic suites, the certificate cache, and short-circuit policy evaluation.

Two of these tests exist because the optimisations they cover are the kind that
work perfectly while silently removing a security property. A certificate cache
that forgets to re-check revocation makes the system fast and makes revocation
meaningless, and every other test in the suite would keep passing.
"""

from __future__ import annotations

import datetime as dt

import pytest

from model.consortium import GATE_ORGS, MODEL_CHANNEL, build
from model.ledger import DEFAULT_SUITE_ID, NOutOf
from model.ledger.crypto import generate_signing_key, sign, verify
from model.ledger.identity import MSP, CertificateAuthority
from model.ledger.suites import ED25519, RSA3072, suite_for_key

TS = "2026-08-05T09:14:00Z"


@pytest.fixture
def consortium():
    return build()


# -- suites ---------------------------------------------------------------
def test_the_consortium_signs_with_rsa_by_default():
    """
    RSA everywhere means the identity layer and the accumulator rest on one
    assumption and one ceremony. The cost is measured in `results/identity.json`
    rather than argued away.
    """
    assert DEFAULT_SUITE_ID == RSA3072.id
    key = generate_signing_key()
    assert suite_for_key(key) is RSA3072
    assert suite_for_key(key.public_key()) is RSA3072


def test_a_signature_does_not_verify_under_a_key_of_another_suite():
    """
    The downgrade attack: present an artefact from a weaker or different suite and
    hope the verifier picks the algorithm from something the attacker supplied.
    Here the algorithm is a property of the key, so there is nothing to supply.
    """
    rsa_key = RSA3072.generate()
    ed_key = ED25519.generate()
    payload = {"claim": "committed"}

    rsa_signature = sign(rsa_key, payload)
    assert verify(rsa_key.public_key(), payload, rsa_signature)
    assert not verify(ed_key.public_key(), payload, rsa_signature)

    ed_signature = sign(ed_key, payload)
    assert verify(ed_key.public_key(), payload, ed_signature)
    assert not verify(rsa_key.public_key(), payload, ed_signature)


def test_every_suite_declares_when_it_stops_being_acceptable():
    """
    A wage register committed in 2026 may need to verify into the 2040s. A suite
    that does not carry its own expiry cannot be planned around.
    """
    for suite in (RSA3072, ED25519):
        assert suite.disallowed_after
        assert dt.date.fromisoformat(suite.disallowed_after) > dt.date(2030, 1, 1)


# -- the certificate cache ------------------------------------------------
def test_a_revoked_certificate_stops_working_immediately_even_when_cached():
    """
    THE cache test. Resolve a certificate so it is cached, revoke it, resolve
    again. A cache keyed only on the PEM would serve the old decision and
    revocation would become decorative — fast, and worthless.
    """
    ca = CertificateAuthority("ApexTextileMSP", "Apex Textile Ltd", "factory")
    msp = MSP()
    msp.register(ca)
    identity = ca.issue("fatema.begum", "operator")
    pem = identity.certificate_pem()

    key, reason = msp.public_key_for("ApexTextileMSP", pem)
    assert key is not None, reason
    assert msp.public_key_for("ApexTextileMSP", pem)[0] is not None
    assert msp.cache_hits >= 1, "the second resolution should have been served from cache"

    ca.revoke(identity)
    key, reason = msp.public_key_for("ApexTextileMSP", pem)
    assert key is None
    assert "revoked" in reason


def test_an_expired_certificate_is_refused_even_when_cached():
    """
    Expiry is time-varying, so it must be re-checked on every hit rather than
    frozen at the moment the entry was written.
    """
    ca = CertificateAuthority("ApexTextileMSP", "Apex Textile Ltd", "factory")
    msp = MSP()
    msp.register(ca)
    identity = ca.issue("fatema.begum", "operator")

    assert msp.public_key_for("ApexTextileMSP", identity.certificate_pem())[0] is not None

    future = identity.certificate.not_valid_after_utc + dt.timedelta(days=1)
    ok, reason = msp._check_standing("ApexTextileMSP", identity.certificate, now=future)
    assert not ok
    assert "expired" in reason


def test_the_cache_actually_caches():
    ca = CertificateAuthority("ApexTextileMSP", "Apex Textile Ltd", "factory")
    msp = MSP()
    msp.register(ca)
    pem = ca.issue("fatema.begum", "operator").certificate_pem()

    for _ in range(10):
        msp.public_key_for("ApexTextileMSP", pem)
    assert msp.cache_misses == 1
    assert msp.cache_hits == 9


# -- short-circuit evaluation ---------------------------------------------
def test_a_satisfied_policy_verifies_no_more_signatures_than_it_needs(consortium):
    """
    Fabric verifies every endorsement attached regardless of what the policy
    requires. On a three-of-five policy that is two RSA verifications per
    transaction, on every peer, that change nothing.
    """
    c = consortium
    tx = c.network.propose(
        MODEL_CHANNEL, "fedmodel", "list_models", {},
        submitter=c.who("rafiqul.islam"),
        endorsers=c.endorsers(GATE_ORGS),
        timestamp=TS,
    )
    assert len(tx.endorsements) == 5

    validator = c.network.validator
    before = validator.signatures_verified
    ok, why = validator.check(tx.payload(), tx.endorsements, NOutOf(3, GATE_ORGS))
    assert ok, why
    assert validator.signatures_verified - before == 3


def test_a_failing_policy_still_pays_for_every_signature(consortium):
    """
    The saving lands on the honest path only, and that is the correct trade.
    Refusing a transaction means establishing that no sufficient subset verifies,
    which cannot be short-circuited.
    """
    c = consortium
    tx = c.network.propose(
        MODEL_CHANNEL, "fedmodel", "list_models", {},
        submitter=c.who("rafiqul.islam"),
        endorsers=c.endorsers(GATE_ORGS[:2]),
        timestamp=TS,
    )
    validator = c.network.validator
    before = validator.signatures_verified
    ok, _ = validator.check(tx.payload(), tx.endorsements, NOutOf(3, GATE_ORGS))
    assert not ok
    assert validator.signatures_verified - before == 2


def test_repeat_signatures_from_one_organisation_are_not_verified_twice(consortium):
    """
    A policy counts distinct organisations. A second signature from one already
    counted cannot change the outcome, so checking it is pure cost — and the same
    reasoning is what stops five employees of one factory satisfying a
    three-of-five policy.
    """
    c = consortium
    tx = c.network.propose(
        MODEL_CHANNEL, "fedmodel", "list_models", {},
        submitter=c.who("rafiqul.islam"),
        endorsers=c.endorsers(GATE_ORGS),
        timestamp=TS,
    )
    duplicated = [tx.endorsements[0]] * 4 + tx.endorsements
    validator = c.network.validator
    before_verified = validator.signatures_verified
    before_skipped = validator.signatures_skipped
    validator.check(tx.payload(), duplicated, NOutOf(3, GATE_ORGS))
    assert validator.signatures_verified - before_verified == 3
    assert validator.signatures_skipped - before_skipped >= 3
