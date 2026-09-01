"""
Tests for selective disclosure.

The claim being tested is the one a buyer cares about: "you learned one number,
and you could not have learned any other."
"""

from __future__ import annotations

import pytest

from model.ledger.crypto import leaf_hash, new_salt, node_hash
from model.merkle import MerkleTree, verify_disclosure


def rows(n: int = 1847) -> list[dict]:
    return [{"worker_id": f"APX-{4400 + i}", "net_pay_bdt": 14000 + i * 7} for i in range(n)]


def test_a_single_row_proves_against_the_committed_root():
    tree = MerkleTree(rows())
    d = tree.prove(21, "rc-001", "net_pay_bdt")
    ok, computed, trace = verify_disclosure(d, tree.root)
    assert ok
    assert computed == tree.root
    assert len(trace) == len(d.path) + 1


def test_proof_size_is_logarithmic_not_linear():
    """1,847 rows needs 11 sibling hashes, not 1,846. This is the whole point."""
    tree = MerkleTree(rows())
    assert tree.size == 1847
    assert len(tree.prove(21, "rc-001", "net_pay_bdt").path) == 11


def test_changing_the_disclosed_value_fails_verification():
    tree = MerkleTree(rows())
    d = tree.prove(21, "rc-001", "net_pay_bdt")
    d.value = {"worker_id": "APX-4421", "net_pay_bdt": 99999}
    assert not verify_disclosure(d, tree.root)[0]


def test_changing_the_salt_fails_verification():
    tree = MerkleTree(rows())
    d = tree.prove(21, "rc-001", "net_pay_bdt")
    d.salt = new_salt()
    assert not verify_disclosure(d, tree.root)[0]


def test_corrupting_any_step_of_the_path_fails_verification():
    tree = MerkleTree(rows(64))
    for i in range(len(tree.prove(3, "rc", "f").path)):
        d = tree.prove(3, "rc", "f")
        d.path[i].sibling = "f" * 64
        assert not verify_disclosure(d, tree.root)[0], f"step {i} was not checked"


def test_flipping_a_siblings_side_fails_verification():
    """Order matters: node_hash(a,b) must differ from node_hash(b,a)."""
    tree = MerkleTree(rows(64))
    d = tree.prove(3, "rc", "f")
    d.path[0].position = "left" if d.path[0].position == "right" else "right"
    assert not verify_disclosure(d, tree.root)[0]


def test_a_proof_for_one_row_reveals_nothing_about_another():
    """
    The disclosure carries one value, one salt and sibling *hashes*. Every other
    row's value is absent, and the hashes are not invertible.

    The check is structural rather than a substring search over the serialised
    proof. An earlier version of this test looked for each other row's decimal
    value anywhere in the stringified disclosure, which fails roughly two percent
    of runs for a reason that has nothing to do with leakage: a five-digit decimal
    is a valid hex string, so it turns up inside a sibling hash by chance. A test
    that fails at random teaches people to re-run it, which is how a real failure
    gets ignored.
    """
    data = rows(64)
    tree = MerkleTree(data)
    d = tree.prove(3, "rc-001", "net_pay_bdt")

    assert d.value == data[3]
    assert d.salt == tree.salts[3]

    # Everything else in the proof is a sibling hash and nothing but a sibling hash.
    siblings = {step.sibling for step in d.path}
    assert all(len(h) == 64 and set(h) <= set("0123456789abcdef") for h in siblings)

    other_salts = set(tree.salts[:3] + tree.salts[4:])
    assert not (siblings & other_salts)

    # No sibling is the bare leaf hash of another row computed without its salt,
    # which is the shape a leakage bug would actually take.
    from model.ledger.crypto import leaf_hash

    unsalted = {leaf_hash(r, "") for i, r in enumerate(data) if i != 3}
    assert not (siblings & unsalted)


def test_salting_defeats_guessing_a_low_entropy_row():
    """
    Without a salt, an attacker who suspects a value can hash the guess and
    compare it to a leaf. With a per-row salt they cannot.
    """
    value = {"worker_id": "APX-4421", "net_pay_bdt": 14147}
    guess_unsalted = leaf_hash(value, "")
    actual = leaf_hash(value, new_salt())
    assert guess_unsalted != actual


def test_domain_separation_stops_a_node_posing_as_a_leaf():
    """
    Hashing leaves and internal nodes with the same function lets a forger
    present an internal node as a record. Different tags make the two spaces
    disjoint.
    """
    a, b = leaf_hash({"x": 1}, "s1"), leaf_hash({"x": 2}, "s2")
    internal = node_hash(a, b)
    assert internal != leaf_hash(internal, "")
    assert internal != a and internal != b


def test_odd_row_counts_are_handled_by_promotion_not_duplication():
    """
    Duplicating the last hash to pad a level is CVE-2012-2459: two different row
    lists then produce the same root. Promotion avoids it.
    """
    three = MerkleTree([{"v": 1}, {"v": 2}, {"v": 3}], salts=["s1", "s2", "s3"])
    four = MerkleTree(
        [{"v": 1}, {"v": 2}, {"v": 3}, {"v": 3}], salts=["s1", "s2", "s3", "s3"]
    )
    assert three.root != four.root


def test_every_row_in_a_document_can_be_proved():
    data = rows(37)  # odd, and not a power of two
    tree = MerkleTree(data)
    for i in range(len(data)):
        assert verify_disclosure(tree.prove(i, "rc", "f"), tree.root)[0], f"row {i} failed"


def test_a_proof_from_one_document_does_not_verify_against_another():
    a, b = MerkleTree(rows(64)), MerkleTree(rows(64))
    assert a.root != b.root  # different random salts
    assert not verify_disclosure(a.prove(3, "rc", "f"), b.root)[0]


def test_an_empty_document_is_refused():
    with pytest.raises(ValueError, match="zero rows"):
        MerkleTree([])


def test_salt_count_must_match_row_count():
    with pytest.raises(ValueError, match="one salt per row"):
        MerkleTree([{"v": 1}, {"v": 2}], salts=["only-one"])


def test_the_tree_is_reproducible_given_the_same_salts():
    salts = [new_salt() for _ in range(64)]
    assert MerkleTree(rows(64), salts).root == MerkleTree(rows(64), salts).root
