"""
Tests for the learning plane.

These are the claims the report makes about the method, checked rather than
asserted. They are slower than the ledger tests because they actually train.
"""

from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest
import torch

from model.ai import FederatedTrainer, MemoryBank
from model.ai.privacy import add_noise, clip_update, trimmed_mean, weighted_average
from model.datagen import DocumentGenerator, extract_features
from model.datagen.generate import _checksum_ok, _make_identifier

pytestmark = pytest.mark.slow


# -- the data generator ---------------------------------------------------
def test_a_valid_certificate_identifier_passes_its_own_checksum():
    """
    Guards a bug that made a whole task unlearnable: taking every digit in the
    identifier folded the scheme name's digits ("ISO45001") into the arithmetic,
    so nothing ever validated and the feature carried no signal at all.
    """
    rng = np.random.default_rng(0)
    for _ in range(200):
        assert _checksum_ok(_make_identifier(rng, valid=True))
        assert not _checksum_ok(_make_identifier(rng, valid=False))


def test_clean_documents_are_never_backdated():
    """
    A clean inspection is always signed on or after the day it was inspected.
    Random independent dates would make half of every clean document look
    back-dated, and the feature would be noise.
    """
    gen = DocumentGenerator(seed=3)
    for doc in gen.generate_of_kind(None, 100):
        if "signed_on" in doc.rows[0]:
            for row in doc.rows:
                assert row["signed_on"] >= row["inspected_on"]


@pytest.mark.parametrize(
    "kind,feature_index,expect_positive",
    [
        ("arithmetic", 0, True),   # arith_max_residual
        ("overtime", 4, True),     # ot_frac_over_legal
        ("checksum", 6, True),     # checksum_frac_failed
        ("backdating", 7, True),   # date_frac_backdated
    ],
)
def test_each_anomaly_kind_moves_its_own_feature(kind, feature_index, expect_positive):
    """Each planted anomaly must be visible in the feature it is supposed to affect."""
    gen = DocumentGenerator(seed=5)
    clean = np.stack([extract_features(d) for d in gen.generate_of_kind(None, 120)])
    dirty = np.stack([extract_features(d) for d in gen.generate_of_kind(kind, 120)])
    if expect_positive:
        assert dirty[:, feature_index].mean() > clean[:, feature_index].mean()


def test_features_carry_no_identifiers():
    """
    Only features leave the factory, so it matters that they are all relative
    quantities. A worker reference or a certificate number appearing in the
    vector would be a privacy failure at the point the report says there is none.
    """
    gen = DocumentGenerator(seed=1)
    doc = gen.generate_of_kind(None, 1)[0]
    f = extract_features(doc)
    assert len(f) == 16
    assert np.isfinite(f).all()
    # Nothing in the vector reconstructs a row's identity.
    for row in doc.rows:
        for value in row.values():
            if isinstance(value, str):
                assert not any(np.isclose(f, hash(value) % 1000))


# -- privacy and aggregation ---------------------------------------------
def test_clipping_bounds_the_update_norm():
    big = [torch.ones(10, 10) * 100]
    clipped, norm = clip_update(big, max_norm=5.0)
    assert norm > 5.0
    assert float(torch.sqrt(sum((t.double() ** 2).sum() for t in clipped))) == pytest.approx(5.0, rel=1e-6)


def test_a_small_update_is_left_alone():
    small = [torch.ones(2, 2) * 0.1]
    clipped, norm = clip_update(small, max_norm=5.0)
    assert norm < 5.0
    assert torch.allclose(clipped[0], small[0])


def test_noise_changes_the_update_without_moving_its_mean_much():
    update = [torch.zeros(2000)]
    noised = add_noise(update, sigma=0.01)
    assert not torch.allclose(noised[0], update[0])
    assert abs(float(noised[0].mean())) < 0.005


def test_trimmed_mean_discards_a_poisoned_update():
    """
    The defence against a dishonest participant: one wildly scaled update must
    not move the aggregate.
    """
    torch.manual_seed(0)
    # Honest updates cluster around 1.0 with a little spread, so that the sort
    # has no ties and the trimmed tails are genuinely the extremes.
    honest = [[torch.ones(50) + torch.randn(50) * 0.01] for _ in range(5)]
    poisoned = [[torch.ones(50) * 1000.0]]
    result, trimmed = trimmed_mean(honest + poisoned, trim=1)

    # The aggregate is unmoved by an update a thousand times larger.
    assert float(result[0].mean()) == pytest.approx(1.0, abs=0.02)
    # The attacker is trimmed on every single coordinate. A trimmed mean removes
    # both tails, so exactly one honest client is trimmed on each coordinate too;
    # what matters is that the attacker is trimmed on all of them.
    assert trimmed[-1] == 50
    assert sum(trimmed[:-1]) == 50  # the low tail, spread across honest clients


def test_trimmed_mean_falls_back_rather_than_dropping_everyone():
    two = [[torch.ones(4) * 1.0], [torch.ones(4) * 3.0]]
    result, trimmed = trimmed_mean(two, trim=1)
    assert float(result[0].mean()) == pytest.approx(2.0)
    assert trimmed == [0, 0]


def test_weighted_average_respects_reputation():
    a, b = [torch.zeros(4)], [torch.ones(4)]
    assert float(weighted_average([a, b], [10_000, 0])[0].mean()) == pytest.approx(0.0)
    assert float(weighted_average([a, b], [0, 10_000])[0].mean()) == pytest.approx(1.0)
    assert float(weighted_average([a, b], [5_000, 5_000])[0].mean()) == pytest.approx(0.5)


# -- the memory bank ------------------------------------------------------
def test_the_bank_hash_changes_when_the_memory_changes():
    """The anchor is only meaningful if it actually tracks the contents."""
    rng = np.random.default_rng(0)
    bank = MemoryBank()
    before = bank.hash
    x = rng.normal(size=(200, 16))
    y = np.zeros(200, dtype=int)
    bank.merge(bank.summarise(x, y, rng))
    assert bank.hash != before


def test_the_bank_hash_is_stable_for_identical_contents():
    """Two organisations holding the same bank must derive the same anchor."""
    rng = np.random.default_rng(0)
    x = rng.normal(size=(200, 16))
    y = np.zeros(200, dtype=int)

    b1 = MemoryBank()
    b1.merge(b1.summarise(x, y, np.random.default_rng(4)))
    b2 = MemoryBank()
    b2.merge(b2.summarise(x, y, np.random.default_rng(4)))
    assert b1.hash == b2.hash


def test_the_bank_stores_summaries_not_records():
    rng = np.random.default_rng(0)
    x = rng.normal(size=(500, 16))
    y = np.zeros(500, dtype=int)
    bank = MemoryBank()
    bank.merge(bank.summarise(x, y, rng))
    proto = bank.prototypes[0]
    # Three centres, not five hundred rows.
    assert proto.centres.shape[0] <= 3
    assert proto.centres.shape[0] < len(x)


def test_the_privacy_note_does_not_claim_differential_privacy():
    note = MemoryBank.privacy_note()
    assert "not differential privacy" in note
    assert "no privacy budget" in note


# -- the claim the whole project rests on --------------------------------
def test_sequential_training_forgets_and_replay_prevents_it():
    """
    The report's central empirical claim, end to end.

    Train two models from the same parent through the same third stage. The one
    without rehearsal must lose substantially more of what it knew.
    """
    base = FederatedTrainer(use_replay=True, seed=7)
    base.run_stage(0)
    base.run_stage(1)
    before = base.evaluate_all()

    with_replay = deepcopy(base)
    without_replay = deepcopy(base)
    without_replay.use_replay = False
    with_replay.run_stage(2)
    without_replay.run_stage(2)

    earlier = ["wage_register_inconsistency", "forged_certificate"]
    kept = with_replay.evaluate_all()
    lost = without_replay.evaluate_all()

    forgetting_with = np.mean([before[t] - kept[t] for t in earlier])
    forgetting_without = np.mean([before[t] - lost[t] for t in earlier])

    # Both learned the new task.
    assert kept["chemical_misreporting"] > 8000
    assert lost["chemical_misreporting"] > 8000
    # Only one of them remembered the old ones.
    assert forgetting_without > forgetting_with
    assert forgetting_without > 500  # more than 5 points forgotten


def test_the_gate_would_catch_the_forgetful_model():
    """
    The join between the two planes: a model that forgets must fail the same
    threshold rule the chaincode applies.
    """
    base = FederatedTrainer(use_replay=True, seed=7)
    base.run_stage(0)
    base.run_stage(1)
    in_force = base.evaluate_all()

    forgetful = deepcopy(base)
    forgetful.use_replay = False
    forgetful.run_stage(2)
    after = forgetful.evaluate_all()

    tau_bp = 500
    regressions = [
        t for t in ["wage_register_inconsistency", "forged_certificate"]
        if in_force[t] - after[t] > tau_bp
    ]
    assert regressions, "the forgetful model should breach the tolerance somewhere"
