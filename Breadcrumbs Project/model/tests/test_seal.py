"""
Period seals: proving that nothing is missing.

Every notarisation system on the market proves a document is genuine. None of
them prove that the set you were shown is the whole set, which is the fraud that
actually happens: two sets of books, and the clean one gets disclosed. These
tests are about that gap.

The important one is `test_a_factory_cannot_disclose_a_subset_of_a_sealed_period`.
It is the test behind the sentence the report leads with.
"""

from __future__ import annotations

import pytest

from model.chaincode.doccustody import bucket_key
from model.consortium import DOCUMENT_CHANNEL, build
from model.merkle import MerkleTree, public_root

TS = "2026-08-05T09:14:00Z"
SITE = "Gazipur"
KIND = "payroll_register"
PERIOD = "2026-07"


@pytest.fixture
def factory():
    """A consortium with five payroll registers committed for one period."""
    c = build()
    ids = []
    for i in range(5):
        record_id = f"rc-{i:03d}"
        rows = [{"worker_ref": f"W-{i}-{j}", "net_pay_bdt": 14000 + j} for j in range(12)]
        _commit(c, record_id, MerkleTree(rows).root, len(rows))
        ids.append(record_id)
    return c, ids


def _commit(c, record_id: str, root: str, rows: int, period: str = PERIOD, ts: str = TS):
    return c.network.invoke(
        DOCUMENT_CHANNEL,
        "doccustody",
        "commit_record",
        {
            "record_id": record_id,
            "merkle_root": root,
            "record_type": KIND,
            "period": period,
            "site": SITE,
            "row_count": rows,
            "schema_version": "v2.1.0",
            "timestamp": ts,
        },
        submitter=c.who("fatema.begum"),
        endorsers=c.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
        timestamp=ts,
    )


def _seal(c, record_ids: list[str], submitter: str = "fatema.begum", ts: str = TS):
    return c.network.invoke(
        DOCUMENT_CHANNEL,
        "doccustody",
        "seal_period",
        {
            "site": SITE,
            "record_type": KIND,
            "period": PERIOD,
            "record_ids": record_ids,
            "timestamp": ts,
        },
        submitter=c.who(submitter),
        endorsers=c.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
        timestamp=ts,
    )


def _completeness(c, disclosed: list[str]):
    return c.network.query(
        DOCUMENT_CHANNEL,
        "doccustody",
        "check_completeness",
        {
            "owner_msp": "ApexTextileMSP",
            "site": SITE,
            "record_type": KIND,
            "period": PERIOD,
            "disclosed_record_ids": disclosed,
        },
        caller=c.who("james.holloway"),
    )


# -- sealing --------------------------------------------------------------
def test_a_period_seals_with_every_record_it_holds(factory):
    c, ids = factory
    _, result, response = _seal(c, ids)
    assert result.valid, result.reason
    assert response["record_count"] == 5
    assert response["records_root"] == public_root(ids)


def test_a_factory_cannot_seal_a_period_while_omitting_a_record(factory):
    """
    The attack, attempted at sealing time: close July having declared only the
    four registers you are happy about.

    The contract enumerates what the ledger actually holds for the bucket and
    refuses. This is the check that makes the seal worth anything — a seal a
    factory could compute over whatever subset it liked would prove only that it
    can do arithmetic.
    """
    c, ids = factory
    with pytest.raises(Exception, match="omits 1 record"):
        _seal(c, ids[:4])


def test_a_seal_cannot_name_a_record_that_was_never_committed(factory):
    c, ids = factory
    with pytest.raises(Exception, match="not committed"):
        _seal(c, [*ids, "rc-999"])


def test_a_period_cannot_be_sealed_twice(factory):
    c, ids = factory
    _seal(c, ids)
    with pytest.raises(Exception, match="already sealed"):
        _seal(c, ids)


def test_another_factory_cannot_seal_a_period_it_does_not_own(factory):
    """
    Noor Garments submits, Apex and BV endorse — the policy is satisfied, so the
    refusal has to come from the contract's ownership check rather than from the
    endorsement layer.
    """
    c, ids = factory
    with pytest.raises(Exception, match="no records to"):
        _seal(c, ids, submitter="noor.operator")


# -- the claim ------------------------------------------------------------
def test_a_factory_cannot_disclose_a_subset_of_a_sealed_period(factory):
    """
    THE test. July is sealed with five registers. The factory hands a buyer four
    of them and says that is all there was.

    Each of the four verifies perfectly: genuine documents, valid Merkle roots,
    committed on the ledger. Every notarisation system in the comparison table
    reports success here. The seal reports the arithmetic instead.
    """
    c, ids = factory
    _seal(c, ids)

    honest = _completeness(c, ids)
    assert honest["complete"]

    withheld = _completeness(c, ids[:4])
    assert not withheld["complete"]
    assert withheld["sealed_count"] == 5
    assert withheld["disclosed_count"] == 4
    assert "1 record(s) were sealed into this period but not disclosed" in withheld["reason"]


def test_padding_a_disclosure_with_an_unrelated_record_does_not_help(factory):
    """
    The obvious follow-up: withhold one register and substitute another so the
    count comes out right. The count matches; the root does not.
    """
    c, ids = factory
    _seal(c, ids)
    padded = [*ids[:4], "rc-from-another-period"]
    result = _completeness(c, padded)
    assert not result["complete"]
    assert result["disclosed_count"] == result["sealed_count"]
    assert result["computed_root"] != result["sealed_root"]


def test_completeness_cannot_be_claimed_for_an_unsealed_period(factory):
    c, _ = factory
    result = _completeness(c, ["rc-000"])
    assert not result["sealed"]
    assert not result["complete"]


# -- late records ---------------------------------------------------------
def _reopen(c, reason: str, ts: str = "2026-08-09T09:00:00Z"):
    return c.network.invoke(
        DOCUMENT_CHANNEL, "doccustody", "reopen_seal",
        {"site": SITE, "record_type": KIND, "period": PERIOD, "reason": reason, "timestamp": ts},
        submitter=c.who("fatema.begum"),
        endorsers=c.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
        timestamp=ts,
    )


def _amend(c, added: list[str], reason: str, ts: str = "2026-08-09T10:00:00Z"):
    return c.network.invoke(
        DOCUMENT_CHANNEL, "doccustody", "amend_seal",
        {
            "site": SITE, "record_type": KIND, "period": PERIOD,
            "added_record_ids": added, "reason": reason, "timestamp": ts,
        },
        submitter=c.who("fatema.begum"),
        endorsers=c.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
        timestamp=ts,
    )


def _get_seal(c):
    return c.network.query(
        DOCUMENT_CHANNEL, "doccustody", "get_seal",
        {"site": SITE, "record_type": KIND, "period": PERIOD}, caller=c.who("fatema.begum"),
    )


def test_a_record_cannot_be_added_to_a_sealed_period(factory):
    c, ids = factory
    _seal(c, ids)
    with pytest.raises(Exception, match="reopen_seal it first"):
        _commit(c, "rc-005", "a" * 64, 10)


def test_a_genuinely_late_record_has_a_route_in(factory):
    """
    The regression test for a dead end this contract used to have.

    An earlier version refused a commit into a sealed bucket and told the caller
    to use amend_seal --- which required the record to exist in that bucket
    already. So a record that genuinely arrived late could not be committed and
    could not be amended in, and the error message named a door that was not
    there. A caller stuck like that has no way to comply, which is worse than a
    refusal because the system looks like it is working.

    The route is now three steps, and each is deliberate: reopen with a reason,
    commit, re-seal. The declaration of intent lands on the ledger BEFORE the
    thing being declared, so a factory cannot reopen a period, find nothing worth
    adding, and quietly pretend it never asked.
    """
    c, ids = factory
    _seal(c, ids)

    _, reopened, response = _reopen(c, "night-shift register arrived from Ashulia")
    assert reopened.valid, reopened.reason
    assert response["status"] == "reopened"

    _, committed, _ = _commit(c, "rc-late", "b" * 64, 11)
    assert committed.valid, committed.reason

    _, amended, result = _amend(c, ["rc-late"], "night-shift register arrived from Ashulia")
    assert amended.valid, amended.reason
    assert result["record_count"] == 6
    assert result["version"] == 2

    complete = _completeness(c, [*ids, "rc-late"])
    assert complete["complete"], complete["reason"]


def test_a_reopened_period_does_not_report_its_stale_count_as_settled(factory):
    """
    A verifier reading a count that is mid-revision has to be told that is what it
    is looking at. Reporting the old count as though it still held would let a
    factory sit in a reopened state and keep serving a completeness answer that is
    no longer true.
    """
    c, ids = factory
    _seal(c, ids)
    _reopen(c, "correcting an overtime column")

    result = _completeness(c, ids)
    assert not result["sealed"]
    assert not result["complete"]
    assert result["status"] == "reopened"
    assert "mid-revision" in result["reason"]


def test_reopening_must_state_a_reason(factory):
    c, ids = factory
    _seal(c, ids)
    with pytest.raises(Exception, match="must state a reason"):
        _reopen(c, "")


def test_a_period_cannot_be_amended_without_being_reopened(factory):
    c, ids = factory
    _seal(c, ids)
    with pytest.raises(Exception, match="reopen_seal it before amending"):
        _amend(c, ids[:1], "trying to skip the visible step")


def test_reopening_is_recorded_permanently_rather_than_hidden(factory):
    """
    A late record is allowed. What is not allowed is a late record that leaves no
    trace: the count and root at the moment of reopening stay in the seal's
    history, so a buyer can see that July was closed at five, reopened, and closed
    again at six --- and when, and why.
    """
    c, ids = factory
    _seal(c, ids)
    _reopen(c, "night-shift register arrived from Ashulia")
    _commit(c, "rc-late", "b" * 64, 11)
    _amend(c, ["rc-late"], "night-shift register arrived from Ashulia")

    seal = _get_seal(c)
    assert seal["status"] == "sealed"
    assert seal["version"] == 2
    assert seal["record_count"] == 6
    assert len(seal["reopenings"]) == 1
    assert seal["reopenings"][0]["count_when_reopened"] == 5
    assert seal["reopenings"][0]["reason"] == "night-shift register arrived from Ashulia"
    assert len(seal["amendments"]) == 1
    assert seal["amendments"][0]["previous_count"] == 5
    assert seal["amendments"][0]["added"] == ["rc-late"]


def test_an_amendment_naming_a_record_that_does_not_exist_is_refused(factory):
    """
    The amendment path declares a late record. It does not conjure one.
    """
    c, ids = factory
    _seal(c, ids)
    _reopen(c, "expecting a register that has not arrived")
    with pytest.raises(Exception, match="unknown record rc-imaginary"):
        _amend(c, ["rc-imaginary"], "declaring something that does not exist")


def test_an_amendment_must_state_a_reason(factory):
    c, ids = factory
    _seal(c, ids)
    _reopen(c, "reopened so the reason check is what refuses, not the status check")
    with pytest.raises(Exception, match="must state a reason"):
        c.network.invoke(
            DOCUMENT_CHANNEL, "doccustody", "amend_seal",
            {
                "site": SITE, "record_type": KIND, "period": PERIOD,
                "added_record_ids": ids[:1], "reason": "", "timestamp": TS,
            },
            submitter=c.who("fatema.begum"),
            endorsers=c.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
            timestamp=TS,
        )


# -- concurrency ----------------------------------------------------------
def test_a_record_committed_during_sealing_invalidates_the_seal(factory):
    """
    The phantom read, and the reason `Context.range` records a digest.

    The attack: start sealing July, and while the seal transaction is in flight,
    commit the register you want left out. The seal simulated against a set of
    five, so it would have committed a five-record seal over a six-record period
    — a permanently wrong count, produced by an ordering the attacker chose.

    Recording what the scan saw turns that into an invalidated transaction.
    """
    c, ids = factory

    seal_tx = c.network.propose(
        DOCUMENT_CHANNEL, "doccustody", "seal_period",
        {
            "site": SITE, "record_type": KIND, "period": PERIOD,
            "record_ids": ids, "timestamp": TS,
        },
        submitter=c.who("fatema.begum"),
        endorsers=c.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
        timestamp=TS,
    )

    _commit(c, "rc-late", "b" * 64, 9)  # sneaks in between simulation and commit

    ok, _ = c.network.submit(seal_tx)
    assert ok
    c.network.commit(TS, channel_name=DOCUMENT_CHANNEL)
    result = c.network.channels[DOCUMENT_CHANNEL].validation[seal_tx.tx_id]
    assert not result.valid
    assert result.code == "PHANTOM_READ_CONFLICT"


def test_the_bucket_key_names_its_owner():
    """
    Two factories at the same site must not collide on one bucket. Without the
    owner in the key, whichever sealed second would overwrite a statement it does
    not own.
    """
    apex = bucket_key("ApexTextileMSP", "Gazipur", "payroll_register", "2026-07")
    noor = bucket_key("NoorGarmentsMSP", "Gazipur", "payroll_register", "2026-07")
    assert apex != noor
    assert apex == "ApexTextileMSP|Gazipur|payroll_register|2026-07"
