"""
One entry point for everything this project can be asked to do.

This is the research entry point: training, evaluation, benchmarks, the demo.
It is not the application launcher. To start the API and the web app together,
use `run.py` in the repository root instead:

    python3 run.py

Two files named run.py is a nuisance, and renaming this one would invalidate the
reproduction commands printed in the paper's figure captions, so both simply say
which is which.

    python -m model.run corpus      check the corpus is present and readable
    python -m model.run train       federated continual training on the corpus
    python -m model.run eval        score the trained detector, per wave and kind
    python -m model.run adversary   score the LEDGER against the attack trace
    python -m model.run fcl         reproduce the report's figure-3 numbers
    python -m model.run demo        the twelve-act end-to-end ledger demo
    python -m model.run bench       measurements, written to results/*.json
    python -m model.run test        the whole test suite
    python -m model.run all         corpus, fcl, train, eval, adversary, demo

WHY TRAINING LOOKS THE WAY IT DOES

The corpus is not one dataset. It is six sites × three waves, and both of those
splits are load-bearing:

  the six sites are the federated clients. Their data is genuinely non-IID —
  `data/partition.py` gives each site a Dirichlet(0.6) mixture over the nine
  anomaly kinds, so Chattogram and Mirpur do not see interchangeable problems.

  the three waves are the continual stages. Wave 1 is arithmetic, overtime,
  duplication and roundness; wave 2 is checksum, backdating and Benford; wave 3
  is arithmetic, outlier and cross-inconsistency. By the time wave 3 arrives,
  wave 1's data is gone. A detector trained straight through ends up good at
  wave 3 and quietly hopeless at wave 1 — and that is the forgetting the
  Continuity Gate exists to catch.

So training runs the three waves in order, six clients per round, and evaluates
after the final wave against all three held-out benchmarks. Two arms are run:
sequential federated averaging, and the same thing plus differentially private
prototype replay. The gap between them is the claim.

WHY THE HEADLINE METRIC IS NOT ACCURACY

4.11% of the corpus is anomalous. A model that answers "clean" every time scores
95.9% accuracy and finds nothing. Every number reported here is therefore
balanced accuracy — the mean of the true-positive and true-negative rates, which
that useless model scores 50.0 on — with recall and precision alongside it.
`eval` prints the all-clean baseline next to the model so the comparison cannot
be dodged.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

PROJECT = Path(__file__).resolve().parent.parent
REPO = PROJECT.parent
CORPUS = PROJECT / "data" / "corpus"
CACHE = PROJECT / "model" / ".cache"
ARTEFACTS = PROJECT / "model" / "artefacts"

WAVES = (1, 2, 3)
N_CLIENTS = 6
ROUNDS_PER_WAVE = 8
LOCAL_EPOCHS = 2
BATCH = 128
LR = 0.08
SEED = 7

# The detector is scored at a chosen false-positive budget rather than at
# whatever point `argmax` happens to land on. See `anomaly_scores`.
FP_BUDGETS = (0.01, 0.05, 0.10)
HEADLINE_BUDGET = 0.10
VALIDATION_FRACTION = 0.15
# Uncapped inverse-frequency weighting gives the anomaly class roughly 24x the
# weight of a clean one on a shard that is 4% anomalous.
MAX_CLASS_WEIGHT_RATIO = 8.0

BOLD, DIM, GREEN, RED, YELLOW, OFF = "\033[1m", "\033[2m", "\033[32m", "\033[31m", "\033[33m", "\033[0m"


def _rule(title: str) -> None:
    print(f"\n{BOLD}{'─' * 78}\n  {title}\n{'─' * 78}{OFF}")


def _need_corpus() -> None:
    if not (CORPUS / "manifest.json").exists():
        sys.exit(
            f"{RED}No corpus at {CORPUS}.{OFF}\n"
            "Generate one first:  python -m data.cli --seed 7 --scale small --out data/corpus"
        )


# ---------------------------------------------------------------------------
# Loading the corpus into a feature matrix
# ---------------------------------------------------------------------------

def _shards() -> Iterator[tuple[str, int, Path]]:
    for site_dir in sorted((CORPUS / "documents").glob("site=*")):
        site = site_dir.name.split("=", 1)[1]
        for wave_dir in sorted(site_dir.glob("wave=*")):
            wave = int(wave_dir.name.split("=", 1)[1])
            for shard in sorted(wave_dir.glob("*.jsonl.gz")):
                yield site, wave, shard


def _read(path: Path) -> Iterator[dict[str, Any]]:
    with gzip.open(path, "rt") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


@dataclass
class Corpus:
    """The whole corpus as arrays, plus the held-out benchmarks."""

    x: np.ndarray
    y: np.ndarray
    wave: np.ndarray
    site: np.ndarray
    kind: np.ndarray
    benchmarks: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray]] = field(default_factory=dict)

    @property
    def sites(self) -> list[str]:
        return sorted(set(self.site.tolist()))


def _fingerprint() -> str:
    """
    Identifies the corpus *and* the extractor.

    Cached features must be thrown away when either the documents or the code
    that reads them changes, or a stale matrix silently becomes the thing every
    later number is computed from.
    """
    from data import features

    manifest = (CORPUS / "manifest.json").read_bytes()
    code = Path(features.__file__).read_bytes()
    return hashlib.sha256(manifest + code).hexdigest()[:16]


def load_corpus(*, refresh: bool = False, quiet: bool = False) -> Corpus:
    """Extract features for every document, caching the result."""
    _need_corpus()
    from data.features import build_matrix, extract_features

    CACHE.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE / f"corpus-{_fingerprint()}.npz"

    if cache_file.exists() and not refresh:
        blob = np.load(cache_file, allow_pickle=False)
        corpus = Corpus(
            x=blob["x"], y=blob["y"], wave=blob["wave"],
            site=blob["site"].astype(str), kind=blob["kind"].astype(str),
        )
        for w in WAVES:
            corpus.benchmarks[w] = (blob[f"bx{w}"], blob[f"by{w}"], blob[f"bk{w}"].astype(str))
        if not quiet:
            print(f"{DIM}features from cache: {cache_file.name}{OFF}")
        return corpus

    started = time.time()
    xs, ys, waves, sites, kinds = [], [], [], [], []
    for site, wave, shard in _shards():
        for document in _read(shard):
            xs.append(extract_features(document))
            ys.append(int(document.get("label") or 0))
            waves.append(wave)
            sites.append(site)
            kinds.append(str(document.get("anomaly_kind") or "clean"))

    corpus = Corpus(
        x=np.vstack(xs), y=np.asarray(ys, dtype=np.int64),
        wave=np.asarray(waves, dtype=np.int64),
        site=np.asarray(sites, dtype="U24"), kind=np.asarray(kinds, dtype="U24"),
    )

    payload: dict[str, np.ndarray] = {
        "x": corpus.x, "y": corpus.y, "wave": corpus.wave,
        "site": corpus.site, "kind": corpus.kind,
    }
    for w in WAVES:
        bench_file = CORPUS / "benchmarks" / f"wave{w}.jsonl.gz"
        bx, by, bkinds = build_matrix(_read(bench_file))
        bk = np.asarray(bkinds, dtype="U24")
        corpus.benchmarks[w] = (bx, by, bk)
        payload[f"bx{w}"], payload[f"by{w}"], payload[f"bk{w}"] = bx, by, bk

    np.savez_compressed(cache_file, **payload)
    if not quiet:
        print(f"{DIM}extracted {len(corpus.y):,} documents in {time.time() - started:.1f}s{OFF}")
    return corpus


# ---------------------------------------------------------------------------
# Metrics that survive a 4% base rate
# ---------------------------------------------------------------------------

@dataclass
class Score:
    balanced: float
    recall: float
    precision: float
    n: int
    positives: int

    def line(self) -> str:
        return (f"bal {self.balanced * 100:5.1f}%   recall {self.recall * 100:5.1f}%   "
                f"prec {self.precision * 100:5.1f}%   (n={self.n:,}, +{self.positives})")


def score(truth: np.ndarray, predicted: np.ndarray, target: int = 1) -> Score:
    """
    Balanced accuracy, recall and precision for one wave's class.

    `target` is the class that wave's anomalies belong to. Recall is therefore
    not "was this flagged" but "was it filed under the right kind of problem" —
    a model that has forgotten wave 1 and reports its documents as wave 3 scores
    zero here, which is the whole point of measuring it this way.
    """
    positive, negative = truth == target, truth == 0
    predicted = (predicted == target).astype(int)
    tpr = float(predicted[positive].mean()) if positive.any() else 0.0
    tnr = float((1 - predicted[negative]).mean()) if negative.any() else 0.0
    flagged = int(predicted.sum())
    precision = float((predicted[positive]).sum() / flagged) if flagged else 0.0
    return Score((tpr + tnr) / 2.0, tpr, precision, int(truth.size), int(positive.sum()))


def anomaly_scores(model, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    P(anomalous) for each document, and the wave it would be filed under.

    Deliberately two answers rather than one. A plain `argmax` over the four
    classes answers only "which class is most likely" and has no adjustable
    operating point at all — which is how this detector came to flag 43% of
    clean documents on one seed and 9% on another with nothing changed but the
    random seed. Splitting "is this anomalous" from "which wave is it" turns the
    first into a ranking that a threshold can be chosen on, and leaves the
    second as a label applied only once the first has been answered.
    """
    import torch

    model.eval()
    with torch.no_grad():
        logits = model(torch.tensor(x, dtype=torch.float32))
        probability = torch.softmax(logits, dim=1).numpy()
    return 1.0 - probability[:, 0], probability[:, 1:].argmax(axis=1) + 1


def choose_tau(clean_scores: np.ndarray, budget: float) -> float:
    """
    The threshold that flags `budget` of clean documents and no more.

    Chosen on held-out *training* data, never on a benchmark. A threshold picked
    on the set the result is reported against is not a threshold, it is the
    answer.
    """
    if clean_scores.size == 0:
        return 0.5
    return float(np.quantile(clean_scores, 1.0 - budget))


def roc_auc(scores: np.ndarray, truth: np.ndarray) -> float:
    """
    Area under the ROC curve, computed from ranks.

    The one measure here that does not depend on where the threshold sits, and
    therefore the right thing to tune against: a change that raises AUC has made
    the model better at telling the two apart, whereas a change that raises
    accuracy may only have moved the operating point.
    """
    positive = truth.astype(bool)
    n_pos, n_neg = int(positive.sum()), int((~positive).sum())
    if n_pos == 0 or n_neg == 0:
        return 0.5
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(len(scores), dtype=np.float64)
    ranks[order] = np.arange(1, len(scores) + 1)
    # Tied scores share their average rank. Without this a model that emitted
    # one constant for every document would score 1.0 or 0.0 rather than 0.5.
    _, inverse, counts = np.unique(scores, return_inverse=True, return_counts=True)
    totals = np.zeros(len(counts), dtype=np.float64)
    np.add.at(totals, inverse, ranks)
    ranks = (totals / counts)[inverse]
    return float((ranks[positive].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def detection_curve(
    scores: np.ndarray, truth: np.ndarray, taus: dict[float, float]
) -> dict[float, dict[str, float]]:
    """Detection and realised false-positive rate at each agreed budget."""
    positive = truth.astype(bool)
    out: dict[float, dict[str, float]] = {}
    for budget, tau in taus.items():
        flagged = scores >= tau
        detection = float(flagged[positive].mean()) if positive.any() else 0.0
        false_positive = float(flagged[~positive].mean()) if (~positive).any() else 0.0
        out[budget] = {
            "detection": detection,
            "false_positive": false_positive,
            "balanced": (detection + (1.0 - false_positive)) / 2.0,
            "tau": tau,
        }
    return out


# ---------------------------------------------------------------------------
# Federated continual training over the waves
# ---------------------------------------------------------------------------

def _normaliser(x: np.ndarray):
    """
    One scale for every wave, fitted once on the whole corpus.

    Fitting per wave would let each stage move the goalposts, and the forgetting
    measured afterwards would be partly an artefact of the change of units. The
    standard deviation is floored because several features are exactly zero on
    every clean document, and dividing by that spread sends the tanh units into
    saturation for reasons that have nothing to do with the method.
    """
    mu = x.mean(axis=0)
    sd = np.maximum(x.std(axis=0), 1e-2)
    return lambda a: np.clip((a - mu) / sd, -10.0, 10.0)


def train(
    *, replay: bool, seed: int = SEED, rounds: int = ROUNDS_PER_WAVE,
    quiet: bool = False, save: bool = True,
) -> dict[str, Any]:
    """Run the three waves in order across six federated clients."""
    import torch
    import torch.nn as nn

    from data.features import N_FEATURES
    from model.ai.net import Detector, get_weights, set_weights
    from model.ai.privacy import (
        add_noise,
        clip_update,
        fedprox_penalty,
        trimmed_mean,
        weighted_average,
    )
    from model.ai.replay import MemoryBank

    corpus = load_corpus(quiet=quiet)
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    normalise = _normaliser(corpus.x)
    sites = corpus.sites

    # Class-incremental, exactly as the report's curriculum and `ai/net.py`
    # describe it: class 0 is a clean document and is present at every stage;
    # classes 1..3 are the anomaly kinds each wave introduces. Training on wave
    # 3 therefore has no reason on its own to keep class 1 separable, and that
    # is the forgetting the Continuity Gate exists to catch. Framing this as one
    # binary "is it anomalous" head instead would be a materially easier problem
    # and would not measure what the report claims.
    labels = np.where(corpus.y == 0, 0, corpus.wave).astype(np.int64)

    # A validation split, taken from the training shards and never from the
    # benchmarks. The threshold that decides what counts as anomalous has to be
    # chosen somewhere, and choosing it on the set the result is reported
    # against would be choosing the answer. Stratified by site and wave so no
    # factory or stage is over-represented in it.
    split_rng = np.random.default_rng(seed + 9973)
    is_validation = np.zeros(len(labels), dtype=bool)
    for wave in WAVES:
        for site in sites:
            index = np.where((corpus.wave == wave) & (corpus.site == site))[0]
            take = max(1, int(round(len(index) * VALIDATION_FRACTION)))
            is_validation[split_rng.choice(index, take, replace=False)] = True

    model = Detector(n_features=N_FEATURES, n_classes=4)
    bank = MemoryBank()
    history: list[dict[str, Any]] = []
    tau = 0.5

    for wave in WAVES:
        in_wave = corpus.wave == wave
        shards = []
        for site in sites:
            mask = in_wave & (corpus.site == site) & ~is_validation
            shards.append((
                torch.tensor(normalise(corpus.x[mask]), dtype=torch.float32),
                torch.tensor(labels[mask], dtype=torch.long),
            ))

        replay_x = replay_y = None
        if replay and bank.prototypes:
            rx, ry = bank.sample(rng)
            if rx is not None:
                replay_x = torch.tensor(np.clip(rx, -10.0, 10.0), dtype=torch.float32)
                replay_y = torch.tensor(ry, dtype=torch.long)

        for _ in range(rounds):
            global_weights = get_weights(model)
            updates = []
            for client_x, client_y in shards:
                if len(client_y) < BATCH or len(set(client_y.tolist())) < 2:
                    updates.append([torch.zeros_like(w) for w in global_weights])
                    continue
                cx, cy = client_x, client_y
                if replay_x is not None:
                    take = torch.randperm(len(replay_y))[: max(BATCH, len(cy) // 4)]
                    cx = torch.cat([cx, replay_x[take]])
                    cy = torch.cat([cy, replay_y[take]])

                local = Detector(n_features=N_FEATURES, n_classes=4)
                set_weights(local, global_weights)

                # The positive class is ~4% of a shard. Without this weight the
                # cheapest way down the loss surface is to answer "clean" every
                # time, which scores well and detects nothing.
                # Only the classes this shard actually holds are weighted; an
                # absent class must contribute nothing rather than an infinite
                # weight, and must not be pushed down either, or each stage
                # would actively unlearn the ones before it.
                #
                # The ratio is capped. Uncapped inverse frequency hands the
                # anomaly class about 24x the weight of a clean one, and with a
                # threshold now choosing the operating point that buys nothing:
                # it shifts every score upward without improving the ranking,
                # and costs calibration doing it.
                present = torch.bincount(cy, minlength=4).float()
                seen = present > 0
                inverse = torch.where(seen, present.clamp(min=1.0).reciprocal(),
                                      torch.zeros_like(present))
                if bool(seen.any()):
                    inverse = torch.clamp(inverse, max=float(inverse[seen].min()) *
                                          MAX_CLASS_WEIGHT_RATIO)
                    inverse = torch.where(seen, inverse, torch.zeros_like(inverse))
                weight = inverse / inverse.sum() * float(seen.sum())
                loss_fn = nn.CrossEntropyLoss(weight=weight)
                opt = torch.optim.Adam(local.parameters(), lr=LR)
                local.train()
                for _ in range(LOCAL_EPOCHS):
                    order = torch.randperm(len(cy))
                    for i in range(0, len(cy), BATCH):
                        b = order[i : i + BATCH]
                        opt.zero_grad()
                        loss = loss_fn(local(cx[b]), cy[b])
                        loss = loss + fedprox_penalty(list(local.parameters()), global_weights)
                        loss.backward()
                        opt.step()

                delta = [lw - gw for lw, gw in zip(get_weights(local), global_weights, strict=True)]
                delta, _ = clip_update(delta)
                updates.append(add_noise(delta))

            _, trimmed = trimmed_mean(updates, trim=1)
            worst = max(trimmed) or 1
            weights_bp = [max(1, int(10_000 // N_CLIENTS * (1.0 - 0.5 * t / worst))) for t in trimmed]
            averaged = weighted_average(updates, weights_bp)
            set_weights(model, [g + a for g, a in zip(get_weights(model), averaged, strict=True)])

        if replay:
            for client_x, client_y in shards:
                if len(client_y) >= 12:
                    bank.merge(bank.summarise(client_x.numpy(), client_y.numpy(), rng))

        # The operating point is re-chosen after every wave, on the waves seen
        # so far. Holding one threshold fixed across the curriculum would mean
        # the per-stage forgetting numbers compared models under two different
        # decision rules, and part of the measured drop would be the rule
        # changing rather than the model forgetting.
        known = is_validation & (corpus.wave <= wave)
        clean_validation = corpus.x[known & (labels == 0)]
        tau = choose_tau(anomaly_scores(model, normalise(clean_validation))[0],
                         HEADLINE_BUDGET)
        history.append({
            "wave": wave,
            "tau": tau,
            "after": {w: _bench_score(model, corpus, w, normalise, tau).balanced
                      for w in WAVES},
        })

    # Only the first seed's model is kept, so `eval` always scores the same
    # artefact rather than whichever seed the sweep happened to finish on.
    arm = "replay" if replay else "sequential"

    # One threshold per agreed budget, all chosen on validation. Persisted with
    # the weights so `eval` reports the same operating point `train` did rather
    # than re-deriving one and quietly disagreeing with the published number.
    final_validation = corpus.x[is_validation & (labels == 0)]
    validation_clean_scores = anomaly_scores(model, normalise(final_validation))[0]
    taus = {budget: choose_tau(validation_clean_scores, budget) for budget in FP_BUDGETS}

    if save:
        ARTEFACTS.mkdir(parents=True, exist_ok=True)
        torch.save(model.state_dict(), ARTEFACTS / f"detector-{arm}.pt")
        np.savez(ARTEFACTS / f"scale-{arm}.npz", mu=corpus.x.mean(axis=0),
                 sd=np.maximum(corpus.x.std(axis=0), 1e-2))
        (ARTEFACTS / f"operating-point-{arm}.json").write_text(json.dumps({
            "seed": seed,
            "headline_budget": HEADLINE_BUDGET,
            "chosen_on": "held-out validation split of the training shards",
            "validation_fraction": VALIDATION_FRACTION,
            "tau_by_budget": {f"{b:.2f}": round(t, 6) for b, t in taus.items()},
        }, indent=2))

    # The operating-point curve on the cross-wave benchmark, so it is reported
    # over the same seeds as everything else rather than from whichever single
    # artefact happened to be saved.
    from data.features import build_matrix

    cx, cy, _ = build_matrix(_read(CORPUS / "benchmarks" / "cross_wave.jsonl.gz"))
    cross_scores, _ = anomaly_scores(model, normalise(cx))

    return {"arm": arm, "history": history, "model": model, "corpus": corpus,
            "normalise": normalise, "tau": tau, "taus": taus,
            "auc": roc_auc(cross_scores, cy),
            "curve": detection_curve(cross_scores, cy, taus),
            "memory_bank_hash": bank.hash if replay else None}


def train_centralised(*, seed: int = SEED, epochs: int = 30) -> list[float]:
    """
    The ceiling: one model, every wave pooled, no federation and no forgetting.

    This is not a system Breadcrumbs is allowed to build — pooling the six
    factories' records in one place is the thing the consortium exists to avoid,
    and the report says so. It is here as a reference line, because a continual
    method is only interesting relative to what you could do if you were
    permitted to keep everything.
    """
    import torch
    import torch.nn as nn

    from data.features import N_FEATURES
    from model.ai.net import Detector

    corpus = load_corpus(quiet=True)
    torch.manual_seed(seed)
    normalise = _normaliser(corpus.x)
    labels = np.where(corpus.y == 0, 0, corpus.wave).astype(np.int64)

    x = torch.tensor(normalise(corpus.x), dtype=torch.float32)
    y = torch.tensor(labels, dtype=torch.long)
    model = Detector(n_features=N_FEATURES, n_classes=4)
    counts = torch.bincount(y, minlength=4).float().clamp(min=1.0)
    loss_fn = nn.CrossEntropyLoss(weight=counts.sum() / (4.0 * counts))
    opt = torch.optim.Adam(model.parameters(), lr=0.01)
    model.train()
    for _ in range(epochs):
        order = torch.randperm(len(y))
        for i in range(0, len(y), 256):
            b = order[i : i + 256]
            opt.zero_grad()
            loss_fn(model(x[b]), y[b]).backward()
            opt.step()
    # The ceiling is scored at the same kind of operating point as everything
    # else, chosen on a validation slice, or it would be compared against the
    # federated arms under a different decision rule and flatter itself.
    split_rng = np.random.default_rng(seed + 9973)
    held = np.zeros(len(labels), dtype=bool)
    for wave in WAVES:
        for site in sorted(set(corpus.site.tolist())):
            index = np.where((corpus.wave == wave) & (corpus.site == site))[0]
            take = max(1, int(round(len(index) * VALIDATION_FRACTION)))
            held[split_rng.choice(index, take, replace=False)] = True
    tau = choose_tau(
        anomaly_scores(model, normalise(corpus.x[held & (labels == 0)]))[0],
        HEADLINE_BUDGET,
    )
    return [_bench_score(model, corpus, w, normalise, tau).balanced for w in WAVES]


def _kind_detection(model, normalise, tau: float) -> dict[str, float]:
    """
    Detection rate per anomaly kind on the cross-wave benchmark, plus the
    false-positive rate on clean documents under the same model.

    Reported together and never apart. A per-kind recall without the
    false-positive rate beside it is not a result — a model that answers
    "anomalous" more often scores better on every kind and is worse at the job.
    """

    from data.features import build_matrix

    bx, _, bkinds = build_matrix(_read(CORPUS / "benchmarks" / "cross_wave.jsonl.gz"))
    p_anomalous, _ = anomaly_scores(model, normalise(bx))
    flagged = (p_anomalous >= tau).astype(float)
    kinds = np.asarray(bkinds)
    return {kind: float(flagged[kinds == kind].mean())
            for kind in sorted(set(kinds.tolist())) if (kinds == kind).any()}


def _bench_score(model, corpus: Corpus, wave: int, normalise, tau: float) -> Score:
    """One wave's benchmark, scored at the given operating point."""
    bx, by, _ = corpus.benchmarks[wave]
    p_anomalous, filed = anomaly_scores(model, normalise(bx))
    predicted = np.where(p_anomalous >= tau, filed, 0)
    return score(np.where(by == 0, 0, wave), predicted, target=wave)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_corpus(args: argparse.Namespace) -> int:
    _rule("The corpus")
    _need_corpus()
    manifest = json.loads((CORPUS / "manifest.json").read_text())
    stats = json.loads((CORPUS / "stats.json").read_text())
    config = manifest.get("config", {})
    print(f"  seed                 {config.get('seed')}   {DIM}generator {manifest.get('generator_version')}{OFF}")
    print(f"  periods              {config.get('start_period')} to {config.get('end_period')}")
    print(f"  dirichlet alpha      {config.get('dirichlet_alpha')}   {DIM}non-IID across sites{OFF}")
    print(f"  documents            {stats['total_documents']:,}")
    print(f"  anomalous            {stats['total_anomalous']:,} "
          f"({stats['overall_anomaly_rate'] * 100:.2f}%)")
    print(f"  sites                {len(stats['by_site'])}")
    print(f"  waves                {len(stats['by_wave'])}")
    print(f"  anomaly kinds        {len(stats['by_anomaly_kind'])}")

    print(f"\n{DIM}  benchmark integrity (hashes committed with the corpus){OFF}")
    recorded = json.loads((CORPUS / "benchmarks" / "hashes.json").read_text())
    all_ok = True
    for name, expected in sorted(recorded.items()):
        path = CORPUS / "benchmarks" / name
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        ok = actual == expected
        all_ok &= ok
        print(f"    {name:<22} {GREEN + 'match' + OFF if ok else RED + 'MISMATCH' + OFF}")

    corpus = load_corpus(refresh=args.refresh)
    finite = np.isfinite(corpus.x).all()
    print(f"\n  feature matrix       {corpus.x.shape[0]:,} x {corpus.x.shape[1]}")
    print(f"  all finite           {GREEN + 'yes' + OFF if finite else RED + 'no' + OFF}")
    for wave in WAVES:
        bx, by, _ = corpus.benchmarks[wave]
        print(f"  benchmark wave {wave}     {len(by):,} documents, {int(by.sum())} anomalous")
    return 0 if (all_ok and finite) else 1


def _continual_metrics(history: list[dict[str, Any]]) -> dict[str, float]:
    """
    The three standard continual-learning measures, as in `fcl_sim.py`.

      ACC  mean balanced accuracy over every wave, measured after the last one
      BWT  backward transfer: mean change on an earlier wave caused by later
           training. Negative is forgetting
      FGT  forgetting: mean drop from each wave's best score to its final one
    """
    final = history[-1]["after"]
    learned = {step["wave"]: step["after"][step["wave"]] for step in history}
    peak = {w: max(step["after"][w] for step in history) for w in WAVES}
    earlier = [w for w in WAVES if w != history[-1]["wave"]]
    return {
        "ACC": float(np.mean([final[w] for w in WAVES])),
        "BWT": float(np.mean([final[w] - learned[w] for w in earlier])),
        "FGT": float(np.mean([peak[w] - final[w] for w in WAVES])),
    }


def cmd_train(args: argparse.Namespace) -> int:
    _rule("Federated continual training on the corpus")
    print(f"{DIM}  six sites as clients, three waves in order, {args.rounds} rounds per wave,")
    print(f"  {args.seeds} seeds. Balanced accuracy; the all-clean baseline scores 50.0%.{OFF}\n")

    seeds = [args.seed + i for i in range(args.seeds)]
    collected: dict[str, dict[str, list]] = {}
    for replay in (False, True):
        arm = "replay" if replay else "sequential"
        label = "prototype replay" if replay else "sequential FedAvg"
        started = time.time()
        finals, metrics, curves, kinds, aucs, points = [], [], [], [], [], []
        for i, seed in enumerate(seeds):
            out = train(replay=replay, seed=seed, rounds=args.rounds,
                        quiet=True, save=(i == 0))
            finals.append([out["history"][-1]["after"][w] for w in WAVES])
            metrics.append(_continual_metrics(out["history"]))
            curves.append(out["history"])
            kinds.append(_kind_detection(out["model"], out["normalise"], out["tau"]))
            aucs.append(out["auc"])
            points.append(out["curve"])
        collected[arm] = {"final": np.array(finals), "metrics": metrics,
                          "curve": curves[0], "kinds": kinds,
                          "auc": aucs, "points": points}
        print(f"  {label:<20}{len(seeds)} seeds in {time.time() - started:.1f}s")
        for step in curves[0]:
            after = "  ".join(f"w{w} {step['after'][w] * 100:5.1f}%" for w in WAVES)
            print(f"{DIM}      seed {seeds[0]}, after wave {step['wave']}:  {after}{OFF}")
        print()

    ceiling = np.array([train_centralised(seed=seed) for seed in seeds])

    _rule("After all three waves")
    print(f"  {'wave':<8}{'sequential FedAvg':>22}{'prototype replay':>22}"
          f"{'difference':>14}{'pooled ceiling':>18}")
    for i, wave in enumerate(WAVES):
        a, b = collected["sequential"]["final"][:, i], collected["replay"]["final"][:, i]
        diff = b.mean() - a.mean()
        colour = GREEN if diff >= 0 else RED
        print(f"  {wave:<8}{a.mean() * 100:>15.1f}% ±{a.std() * 100:<5.1f}"
              f"{b.mean() * 100:>15.1f}% ±{b.std() * 100:<5.1f}{colour}{diff * 100:>+13.1f}{OFF}"
              f"{ceiling[:, i].mean() * 100:>17.1f}%")

    print(f"\n  {'':8}{'sequential FedAvg':>22}{'prototype replay':>22}{'difference':>14}")
    for key, note in (("ACC", "mean accuracy, higher is better"),
                      ("BWT", "backward transfer, negative is forgetting"),
                      ("FGT", "forgetting, lower is better")):
        a = np.array([m[key] for m in collected["sequential"]["metrics"]])
        b = np.array([m[key] for m in collected["replay"]["metrics"]])
        better = (b.mean() - a.mean()) if key != "FGT" else (a.mean() - b.mean())
        colour = GREEN if better >= 0 else RED
        print(f"  {key:<8}{a.mean() * 100:>15.1f}% ±{a.std() * 100:<5.1f}"
              f"{b.mean() * 100:>15.1f}% ±{b.std() * 100:<5.1f}"
              f"{colour}{(b.mean() - a.mean()) * 100:>+13.1f}{OFF}   {DIM}{note}{OFF}")

    _rule("Detection by anomaly kind — prototype replay, mean over seeds")
    per_kind = collected["replay"]["kinds"]
    names = sorted(per_kind[0], key=lambda k: -float(np.mean([d[k] for d in per_kind])))
    kind_summary: dict[str, list[float]] = {}
    for kind in names:
        values = np.array([d[kind] for d in per_kind])
        kind_summary[kind] = [round(float(values.mean()), 4), round(float(values.std()), 4)]
        if kind == "clean":
            label, note = "clean (false positives)", f"   {DIM}the rate every row above must be read against{OFF}"
        elif kind == "cross_inconsistency":
            label, note = kind, f"   {YELLOW}control: invisible in a single document{OFF}"
        else:
            label, note = kind, ""
        bar = "█" * int(round(values.mean() * 22))
        print(f"  {label:<26}{values.mean() * 100:5.1f}% ±{values.std() * 100:<5.1f}"
              f"{DIM}{bar}{OFF}{note}")

    _rule("The operating point — prototype replay, mean over seeds")
    auc = np.array(collected["replay"]["auc"])
    print(f"  ROC-AUC {auc.mean():.4f} ±{auc.std():.4f}   "
          f"{DIM}threshold-free: how well it ranks, before any budget is chosen{OFF}\n")
    print(f"  {'budget':<10}{'detection':>12}{'actual FP':>12}{'balanced':>11}")
    curve_summary: dict[str, dict[str, list[float]]] = {}
    for budget in FP_BUDGETS:
        rows = [pt[budget] for pt in collected["replay"]["points"]]
        det = np.array([r["detection"] for r in rows])
        fpr = np.array([r["false_positive"] for r in rows])
        bal = np.array([r["balanced"] for r in rows])
        curve_summary[f"{budget:.2f}"] = {
            "detection": [round(float(det.mean()), 4), round(float(det.std()), 4)],
            "false_positive": [round(float(fpr.mean()), 4), round(float(fpr.std()), 4)],
            "balanced": [round(float(bal.mean()), 4), round(float(bal.std()), 4)],
        }
        star = "*" if abs(budget - HEADLINE_BUDGET) < 1e-9 else " "
        print(f" {star}{budget * 100:>5.0f}%   {det.mean() * 100:>10.1f}%"
              f"{fpr.mean() * 100:>11.1f}%{bal.mean() * 100:>10.1f}%")
    print(f"\n{DIM}  * headline. The false-positive rate is now a number the consortium")
    print(f"  chooses, not one the argmax happened to land on.{OFF}")

    payload = {
        "seeds": seeds,
        "headline_fp_budget": HEADLINE_BUDGET,
        "roc_auc_replay": [round(float(auc.mean()), 4), round(float(auc.std()), 4)],
        "operating_points_replay": curve_summary,
        "detection_by_kind_replay": kind_summary, "rounds_per_wave": args.rounds, "waves": list(WAVES),
        "metric": "balanced_accuracy",
        "arms": {
            arm: {
                "final_per_wave_mean": (data["final"].mean(axis=0)).round(4).tolist(),
                "final_per_wave_std": (data["final"].std(axis=0)).round(4).tolist(),
                # Mean and spread together. Storing only the mean would leave the
                # figure's error bars sourced from terminal output rather than
                # from the file the figure claims to be generated from.
                **{k: [round(float(np.mean([m[k] for m in data["metrics"]])), 4),
                       round(float(np.std([m[k] for m in data["metrics"]])), 4)]
                   for k in ("ACC", "BWT", "FGT")},
            }
            for arm, data in collected.items()
        },
        "centralised_ceiling": {
            "final_per_wave_mean": ceiling.mean(axis=0).round(4).tolist(),
            "final_per_wave_std": ceiling.std(axis=0).round(4).tolist(),
            "ACC": [round(float(ceiling.mean(axis=1).mean()), 4),
                    round(float(ceiling.mean(axis=1).std()), 4)],
            "note": "pooled training, not permitted in the deployed system",
        },
    }
    ARTEFACTS.mkdir(parents=True, exist_ok=True)
    (ARTEFACTS / "training.json").write_text(json.dumps(payload, indent=2))
    print(f"\n{DIM}  written to {ARTEFACTS / 'training.json'}{OFF}")
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    import torch

    from data.features import N_FEATURES, build_matrix
    from model.ai.net import Detector

    arm = args.arm
    weights = ARTEFACTS / f"detector-{arm}.pt"
    point_file = ARTEFACTS / f"operating-point-{arm}.json"
    if not weights.exists() or not point_file.exists():
        sys.exit(f"{RED}No trained detector at {weights}. Run: python -m model.run train{OFF}")

    corpus = load_corpus()
    scale = np.load(ARTEFACTS / f"scale-{arm}.npz")
    mu, sd = scale["mu"], scale["sd"]

    def normalise(a: np.ndarray) -> np.ndarray:
        return np.clip((a - mu) / sd, -10.0, 10.0)

    model = Detector(n_features=N_FEATURES, n_classes=4)
    model.load_state_dict(torch.load(weights))
    model.eval()

    point = json.loads(point_file.read_text())
    taus = {float(k): float(v) for k, v in point["tau_by_budget"].items()}
    headline = float(point["headline_budget"])
    tau = taus[min(taus, key=lambda b: abs(b - headline))]

    # -- the operating point, before anything measured at it -----------------
    bx, by, bkinds = build_matrix(_read(CORPUS / "benchmarks" / "cross_wave.jsonl.gz"))
    p_anomalous, filed = anomaly_scores(model, normalise(bx))
    kinds = np.asarray(bkinds)

    _rule(f"Choosing the operating point — {arm}")
    print(f"{DIM}  Thresholds were chosen on a held-out {point['validation_fraction']:.0%} "
          f"split of the training\n  shards, never on these benchmarks. AUC does not depend "
          f"on the threshold at all.{OFF}\n")
    print(f"  ROC-AUC  {roc_auc(p_anomalous, by):.4f}   "
          f"{DIM}1.0 is perfect ranking, 0.5 is a coin{OFF}\n")

    curve = detection_curve(p_anomalous, by, taus)
    print(f"  {'budget':<10}{'threshold':>11}{'detection':>12}{'actual FP':>12}{'balanced':>11}")
    best = max(curve, key=lambda b: curve[b]["balanced"])
    for budget in sorted(curve):
        row = curve[budget]
        mark = f"  {GREEN}<- best balanced{OFF}" if budget == best else ""
        star = "*" if abs(budget - headline) < 1e-9 else " "
        print(f" {star}{budget * 100:>5.0f}%    {row['tau']:>11.4f}"
              f"{row['detection'] * 100:>11.1f}%{row['false_positive'] * 100:>11.1f}%"
              f"{row['balanced'] * 100:>10.1f}%{mark}")
    print(f"\n{DIM}  * is the headline budget. Every number below is measured at it.{OFF}")
    if abs(best - headline) > 1e-9:
        print(f"{YELLOW}  Note: the {best:.0%} budget scores higher balanced accuracy than the")
        print(f"  headline {headline:.0%} and flags fewer clean documents, so it dominates it.")
        print(f"  A consortium choosing on these numbers would pick {best:.0%}.{OFF}")

    # -- per wave -------------------------------------------------------------
    _rule(f"Held-out benchmarks at a {headline:.0%} false-positive budget")
    print(f"{DIM}  recall means 'filed under the right wave', not merely 'flagged'{OFF}")
    print(f"  {'wave':<8}{'model':<52}{'all-clean baseline'}")
    for wave in WAVES:
        wx, wy, _ = corpus.benchmarks[wave]
        truth = np.where(wy == 0, 0, wave)
        wave_scores, wave_filed = anomaly_scores(model, normalise(wx))
        predicted = np.where(wave_scores >= tau, wave_filed, 0)
        base = score(truth, np.zeros_like(truth), target=wave)
        print(f"  {wave:<8}{score(truth, predicted, target=wave).line():<52}"
              f"{base.balanced * 100:5.1f}%")

    # -- per kind -------------------------------------------------------------
    _rule("Detection by anomaly kind (cross-wave benchmark)")
    flagged = (p_anomalous >= tau).astype(float)
    clean_rate = float(flagged[kinds == "clean"].mean())
    for kind in sorted(set(kinds.tolist()) - {"clean"}):
        mask = kinds == kind
        rate = float(flagged[mask].mean()) if mask.any() else 0.0
        note = ""
        if kind == "cross_inconsistency":
            verdict = "below" if rate <= clean_rate else "above"
            note = (f"   {YELLOW}control: invisible in one document — and {verdict} "
                    f"the false-positive rate{OFF}")
        bar = "\u2588" * int(round(rate * 24))
        print(f"  {kind:<22}{rate * 100:5.1f}%  n={int(mask.sum()):<5}{DIM}{bar}{OFF}{note}")
    print(f"\n  {'false-positive rate':<22}{clean_rate * 100:5.1f}%  "
          f"n={int((kinds == 'clean').sum())}")
    print(f"{DIM}  the rate every row above must be read against{OFF}")
    return 0


# Which ledger mechanism answers each attack in the corpus's trace, and the
# tests that actually attempt it. `prevented` says whether the mechanism stops
# the attack or merely records it — the distinction matters, and collapsing the
# two would overclaim.
ATTACK_MECHANISMS: dict[str, dict[str, Any]] = {
    "retroactive_edit": {
        "detected_at": "transaction",
        "when": "refused by the contract that would have to accept it; nothing is committed",
        "mechanism": "block hash chain + period seal Merkle root",
        "claim": "a sealed period cannot be amended without being reopened on the record",
        "prevented": True,
        "tests": [
            "model/tests/test_seal.py::test_a_period_cannot_be_amended_without_being_reopened",
            "model/tests/test_seal.py::test_a_record_cannot_be_added_to_a_sealed_period",
            "model/tests/test_seal.py::test_an_amendment_naming_a_record_that_does_not_exist_is_refused",
        ],
    },
    "withholding": {
        "detected_at": "disclosure",
        "when": "invisible until someone asks for the period, then arithmetic on the sealed count",
        "mechanism": "period seal completeness proof",
        "claim": "the sealed count exceeds the disclosed count; arithmetic, not trust",
        "prevented": True,
        "tests": [
            "model/tests/test_seal.py::test_a_factory_cannot_seal_a_period_while_omitting_a_record",
            "model/tests/test_seal.py::test_a_factory_cannot_disclose_a_subset_of_a_sealed_period",
            "model/tests/test_seal.py::test_padding_a_disclosure_with_an_unrelated_record_does_not_help",
        ],
    },
    "backdated_seal": {
        "detected_at": "epoch",
        "when": "when the epoch is anchored and its beacon checked against the agreed work",
        "mechanism": "epoch digest + VDF delay beacon",
        "claim": "an epoch carries proof that time passed, so history cannot be manufactured quickly",
        "prevented": True,
        "tests": [
            "model/tests/test_anchor.py::test_an_epoch_carries_a_proof_that_time_passed",
            "model/tests/test_anchor.py::test_a_beacon_claiming_less_work_than_agreed_is_refused",
            "model/tests/test_anchor.py::test_the_trapdoor_holder_cannot_rewrite_history",
        ],
    },
    "late_amendment_abuse": {
        "detected_at": "transaction",
        "when": "refused by the contract that would have to accept it; nothing is committed",
        "mechanism": "reopen_seal, recorded before the change",
        "claim": "a reopened period reports itself mid-revision rather than serving a stale count",
        "prevented": True,
        "tests": [
            "model/tests/test_seal.py::test_reopening_must_state_a_reason",
            "model/tests/test_seal.py::test_a_reopened_period_does_not_report_its_stale_count_as_settled",
            "model/tests/test_seal.py::test_reopening_is_recorded_permanently_rather_than_hidden",
            "model/tests/test_seal.py::test_a_genuinely_late_record_has_a_route_in",
        ],
    },
    "witness_collusion": {
        "detected_at": "audit",
        "when": "not at commit time: only when an auditor files a falsification finding",
        "mechanism": "commit-reveal seed round",
        "claim": "assignment is fixed before the assignees are known, and collusion is recorded",
        "prevented": False,
        "tests": [
            "model/tests/test_witness.py::test_the_owner_cannot_substitute_a_friendlier_witness",
            "model/tests/test_witness.py::test_an_assigned_witness_that_colludes_is_not_stopped_only_recorded",
            "model/tests/test_witness.py::test_the_owner_is_never_its_own_witness",
        ],
    },
}


def cmd_adversary(args: argparse.Namespace) -> int:
    """
    Score the ledger — not the detector — against the corpus's attack trace.

    The trace names attacks; it does not carry out. So for each attack type this
    runs the tests that genuinely attempt it against a live ledger and reports
    what they returned. A row here is a test result, not an assertion: if a
    mechanism stops working, this command says so rather than reprinting a claim.
    """
    _rule("The ledger against the attack trace")
    _need_corpus()
    trace = json.loads((CORPUS / "adversary_trace.json").read_text())
    events = trace["events"]

    counts: dict[str, int] = {}
    for event in events:
        counts[event["attack_type"]] = counts.get(event["attack_type"], 0) + 1
    unknown = set(counts) - set(ATTACK_MECHANISMS)
    if unknown:
        print(f"{RED}  no mechanism mapped for: {', '.join(sorted(unknown))}{OFF}")
        return 1

    print(f"{DIM}  {len(events)} events, {len(counts)} attack types. Running the tests that"
          f" attempt each one.{OFF}\n")

    prevented_events = recorded_events = 0
    points: dict[str, int] = {}
    failures: list[str] = []
    for attack, seen in sorted(counts.items()):
        spec = ATTACK_MECHANISMS[attack]
        outcome = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--no-header", *spec["tests"]],
            cwd=PROJECT, capture_output=True, text=True,
        )
        passed = outcome.returncode == 0
        if not passed:
            failures.append(attack)
        if spec["prevented"]:
            prevented_events += seen if passed else 0
        else:
            recorded_events += seen if passed else 0

        if not passed:
            mark = f"{RED}TESTS FAILED{OFF}"
        elif spec["prevented"]:
            mark = f"{GREEN}prevented  {OFF}"
        else:
            mark = f"{YELLOW}recorded   {OFF}"
        print(f"  {mark} {attack:<22}{DIM}{seen} event(s) in the trace, "
              f"{len(spec['tests'])} tests{OFF}")
        print(f"               {DIM}{spec['mechanism']}{OFF}")
        print(f"               {DIM}{spec['claim']}{OFF}")
        print(f"               caught at {BOLD}{spec['detected_at']}{OFF} time — "
              f"{DIM}{spec['when']}{OFF}")
        points[spec["detected_at"]] = points.get(spec["detected_at"], 0) + seen

    total = len(events)
    print(f"\n  {prevented_events} of {total} events are prevented outright.")
    print(f"  {recorded_events} of {total} are detected and attributed but not prevented.")

    # Where in the life of a record each attack is caught. This is a structural
    # property, not a stopwatch: "transaction" means the contract refuses it and
    # nothing reaches the ledger, while "audit" means the ledger holds the
    # evidence but somebody has to come looking. The gap between those two is
    # the honest measure of how much this design depends on anyone checking.
    _rule("Where each attack is caught")
    order = ["transaction", "disclosure", "epoch", "audit"]
    for point in order:
        if point not in points:
            continue
        share = points[point] / total
        print(f"  {point:<14}{points[point]:>2} of {total} events   "
              f"{DIM}{'█' * int(round(share * 30))}{OFF}")
    immediate = points.get("transaction", 0)
    print(f"\n  {immediate} of {total} never reach the ledger at all.")
    print(f"{DIM}  The rest are recorded and detectable, but only once a period is")
    print("  disclosed, an epoch is anchored, or an auditor looks. That is a real")
    print(f"  dependency on somebody checking, and the report states it.{OFF}")
    if failures:
        print(f"\n{RED}  mechanisms whose tests failed: {', '.join(failures)}{OFF}")
    print(f"\n{DIM}  'recorded' is the honest word for witness collusion: a quorum large")
    print("  enough to control the seed round can still collude. The commit-reveal")
    print("  round makes the assignment unforgeable and the collusion attributable,")
    print("  which raises the cost — it does not make the attack impossible. That is a")
    print("  stated limitation, and test_an_assigned_witness_that_colludes_is_not")
    print(f"  _stopped_only_recorded exists to keep it stated.{OFF}")
    return 1 if failures else 0


def _run(command: list[str], cwd: Path = PROJECT) -> int:
    return subprocess.call(command, cwd=cwd)


def cmd_fcl(args: argparse.Namespace) -> int:
    _rule("Figure 3 — the report's learning numbers")
    print(f"{DIM}  self-contained NumPy simulation on Gaussian clusters, five seeds{OFF}\n")
    return _run([sys.executable, "fcl_sim.py"], cwd=PROJECT / "model" / "experiments")


def cmd_demo(args: argparse.Namespace) -> int:
    return _run([sys.executable, "-m", "model.demo"])


def cmd_bench(args: argparse.Namespace) -> int:
    _rule("Benchmarks")
    documents = "60" if args.quick else "200"
    bits = "2048" if args.quick else "3072"
    steps = [
        [sys.executable, "-m", "model.bench.bench_identity"],
        [sys.executable, "-m", "model.bench.bench_ledger", "--documents", documents],
        [sys.executable, "-m", "model.bench.bench_accumulator", "--bits", bits]
        + (["--quick"] if args.quick else []),
        [sys.executable, "-m", "model.bench.to_latex"],
    ]
    for step in steps:
        if (code := _run(step)) != 0:
            return code
    return 0


def cmd_test(args: argparse.Namespace) -> int:
    _rule("Tests")
    return _run([sys.executable, "-m", "pytest", "data/tests", "model/tests", "backend/tests", "-q"])


def cmd_all(args: argparse.Namespace) -> int:
    for name, fn in (("corpus", cmd_corpus), ("fcl", cmd_fcl), ("train", cmd_train),
                     ("eval", cmd_eval), ("adversary", cmd_adversary), ("demo", cmd_demo)):
        if (code := fn(args)) != 0:
            print(f"{RED}{name} failed{OFF}")
            return code
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m model.run",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # Shared options live on a parent parser so they work on either side of the
    # subcommand: `run --rounds 6 train` and `run train --rounds 6` both parse.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--seed", type=int, default=SEED)
    common.add_argument("--rounds", type=int, default=ROUNDS_PER_WAVE,
                        help="federated rounds per wave")
    common.add_argument("--seeds", type=int, default=5,
                        help="how many seeds to average training over")
    common.add_argument("--arm", choices=("replay", "sequential"), default="replay",
                        help="which trained detector eval should score")
    common.add_argument("--refresh", action="store_true", help="re-extract features")
    common.add_argument("--quick", action="store_true", help="smaller benchmarks")
    for action in common._actions:
        parser._add_action(action)

    sub = parser.add_subparsers(dest="command", required=True)
    for name, fn, help_text in (
        ("corpus", cmd_corpus, "check the corpus is present and readable"),
        ("train", cmd_train, "federated continual training on the corpus"),
        ("eval", cmd_eval, "score the trained detector, per wave and kind"),
        ("adversary", cmd_adversary, "score the ledger against the attack trace"),
        ("fcl", cmd_fcl, "reproduce the report's figure-3 numbers"),
        ("demo", cmd_demo, "the twelve-act end-to-end ledger demo"),
        ("bench", cmd_bench, "measurements, written to results/*.json"),
        ("test", cmd_test, "the whole test suite"),
        ("all", cmd_all, "everything, in order"),
    ):
        sub.add_parser(name, help=help_text, parents=[common]).set_defaults(handler=fn)

    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
