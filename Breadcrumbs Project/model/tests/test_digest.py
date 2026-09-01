"""
Fork detection: what happens when somebody rewrites history consistently.

The security audit's §3.5 is the gap these tests close. An attacker holding the
storage can recompute every hash link and re-sign every block, producing a
history with no internal contradiction at all. Nothing inside a chain detects
that. What detects it is that other organisations remember what they were shown.
"""

from __future__ import annotations

from model.consortium import DOCUMENT_CHANNEL, build
from model.ledger.digest import DigestRegistry, attest, epoch_digest

TS = "2026-08-05T09:14:00Z"
PARAMS = "f" * 64


def _digest(epoch: int, accumulator: str, block_hash: str, block_number: int = 4):
    return epoch_digest(DOCUMENT_CHANNEL, epoch, accumulator, block_number, block_hash, PARAMS)


def test_members_agreeing_produce_no_fork():
    c = build()
    registry = DigestRegistry(msp=c.msp)
    shared = _digest(3, "abc123", "d" * 64)
    for name in ("fatema.begum", "james.holloway", "meera.nair"):
        ok, why = registry.observe(attest(c.who(name), shared, TS))
        assert ok, why
    assert registry.fork_at(DOCUMENT_CHANNEL, 3) is None
    assert registry.forks() == []


def test_two_members_served_different_histories_are_detected_and_the_epoch_is_named():
    """
    THE test. The factory shows the buyer one history and the auditor another —
    both internally consistent, both correctly hash-linked, neither detectable
    from the inside.

    Comparing what they each signed detects it, and says exactly where.
    """
    c = build()
    registry = DigestRegistry(msp=c.msp)

    honest = _digest(7, "aaa111", "1" * 64)
    rewritten = _digest(7, "bbb222", "2" * 64)

    registry.observe(attest(c.who("james.holloway"), honest, TS))
    registry.observe(attest(c.who("meera.nair"), rewritten, TS))

    divergence = registry.fork_at(DOCUMENT_CHANNEL, 7)
    assert divergence is not None
    assert divergence.epoch == 7
    assert len(divergence.views) == 2
    assert set(divergence.parties) == {"PrimarkSourcingMSP", "BVCertificationMSP"}
    assert "FORK DETECTED" in divergence.describe()
    assert "epoch 7" in divergence.describe()


def test_a_fork_does_not_by_itself_say_which_history_is_genuine():
    """
    The honest limit, and the report must state it in these words. Two members
    disagreeing proves somebody equivocated. It does not say who was lied to.
    A third independent member breaks the tie by counting, not by cleverness.
    """
    c = build()
    registry = DigestRegistry(msp=c.msp)
    honest = _digest(7, "aaa111", "1" * 64)
    rewritten = _digest(7, "bbb222", "2" * 64)

    registry.observe(attest(c.who("james.holloway"), honest, TS))
    registry.observe(attest(c.who("meera.nair"), rewritten, TS))
    winner, supporting, total = registry.majority(DOCUMENT_CHANNEL, 7)
    assert (supporting, total) == (1, 2), "a two-way split has no majority to report"

    registry.observe(attest(c.who("rafiqul.islam"), honest, TS))
    winner, supporting, total = registry.majority(DOCUMENT_CHANNEL, 7)
    assert winner == honest["digest"]
    assert (supporting, total) == (2, 3)


def test_a_digest_attributed_to_an_organisation_that_did_not_sign_it_is_refused():
    """
    The attack: manufacture agreement. Forge digests from three organisations so
    a rewritten history looks like the majority view.
    """
    c = build()
    registry = DigestRegistry(msp=c.msp)
    genuine = attest(c.who("james.holloway"), _digest(2, "aaa", "0" * 64), TS)

    impersonated = type(genuine)(
        msp_id="BVCertificationMSP",
        identity_id="BVCertificationMSP::meera.nair",
        certificate_pem=genuine.certificate_pem,
        digest=genuine.digest,
        signature=genuine.signature,
        observed_at=TS,
    )
    ok, reason = registry.observe(impersonated)
    assert not ok
    assert "not issued by this organisation's CA" in reason
    assert registry.fork_at(DOCUMENT_CHANNEL, 2) is None


def test_a_digest_that_contradicts_its_own_contents_is_refused():
    """
    A signed digest whose body does not hash to its stated digest would let a
    member assert one thing and be recorded as asserting another.
    """
    c = build()
    registry = DigestRegistry(msp=c.msp)
    body = _digest(5, "aaa", "3" * 64)
    tampered = {**body, "accumulator_hex": "bbb"}
    ok, reason = registry.observe(attest(c.who("james.holloway"), tampered, TS))
    assert not ok
    assert "does not match its own contents" in reason


def test_forks_are_reported_in_epoch_order():
    c = build()
    registry = DigestRegistry(msp=c.msp)
    for epoch in (9, 4):
        registry.observe(attest(c.who("james.holloway"), _digest(epoch, "a", "1" * 64), TS))
        registry.observe(attest(c.who("meera.nair"), _digest(epoch, "b", "2" * 64), TS))
    assert [d.epoch for d in registry.forks()] == [4, 9]
