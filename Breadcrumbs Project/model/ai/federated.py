"""
Federated continual learning, wired to the ledger.

This is where Plane B meets Plane C. A training round here does not end with "the
server publishes a new model". It ends with a candidate, a memory-bank hash, and
a set of independently signed evaluations against benchmarks whose hashes were
committed before the round started — which the Continuity Gate then accepts or
refuses.

The pipeline per stage:

  1. each factory trains locally on its own data plus synthetic rehearsal records
     drawn from the shared memory bank
  2. each update is clipped and noised before it leaves the factory
  3. updates are aggregated with a coordinate-wise trimmed mean, weighted by the
     reputation scores held on-chain
  4. each factory contributes fresh noised summaries to the memory bank
  5. the bank's hash is anchored on the ledger and bound to the candidate
  6. endorsing organisations each evaluate the candidate off-chain against every
     committed benchmark and sign the accuracies they measured
  7. the gate contract decides

Data is split across factories with a Dirichlet partition so the six of them do
not hold interchangeable data — which is the realistic and much harder case.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import torch
import torch.nn as nn

from ..datagen import DocumentGenerator, build_dataset
from ..ledger.crypto import TAG_MODEL, hash_object, sign
from .net import (
    STAGE_CLASSES,
    TASK_IDS,
    TASK_KINDS,
    Detector,
    accuracy_bp,
    get_weights,
    set_weights,
)
from .privacy import add_noise, clip_update, fedprox_penalty, trimmed_mean, weighted_average
from .replay import MemoryBank

N_FACTORIES = 6
LOCAL_EPOCHS = 2
ROUNDS_PER_STAGE = 12
BATCH = 64
LR = 0.15
DIRICHLET_ALPHA = 0.6


@dataclass
class StageData:
    """One stage's training shards and its held-out benchmark."""

    stage: int
    task_id: str
    shards: list[tuple[torch.Tensor, torch.Tensor]]
    benchmark_x: torch.Tensor
    benchmark_y: torch.Tensor

    @property
    def benchmark_payload(self) -> dict[str, Any]:
        """
        The benchmark's canonical contents, hashed for the on-chain commitment.

        Rounded before hashing for the same determinism reason as the memory
        bank: two organisations must derive the same digest.
        """
        return {
            "task_id": self.task_id,
            "n": int(len(self.benchmark_y)),
            "x": np.round(self.benchmark_x.numpy(), 6).tolist(),
            "y": self.benchmark_y.numpy().astype(int).tolist(),
        }


def _class_data(gen: DocumentGenerator, class_id: int, n: int) -> np.ndarray:
    """Feature matrix for one learned class, drawn across its anomaly kinds."""
    kinds = TASK_KINDS[class_id]
    per_kind = max(1, n // len(kinds))
    docs = []
    for kind in kinds:
        docs.extend(gen.generate_of_kind(kind, per_kind))
    X, _, _ = build_dataset(docs)
    return X


def _dirichlet_split(
    x: np.ndarray, y: np.ndarray, n_clients: int, rng: np.random.Generator
) -> list[tuple[torch.Tensor, torch.Tensor]]:
    """
    Give each factory a different class mixture.

    An even split would be a much easier problem than the real one, where a
    factory in Chattogram and one in Gazipur see genuinely different error
    profiles. Dirichlet partitioning is the standard way to model that.
    """
    shards: list[list[int]] = [[] for _ in range(n_clients)]
    for c in np.unique(y):
        idx = np.where(y == c)[0]
        rng.shuffle(idx)
        proportions = rng.dirichlet(DIRICHLET_ALPHA * np.ones(n_clients))
        cuts = (np.cumsum(proportions) * len(idx)).astype(int)[:-1]
        for i, part in enumerate(np.split(idx, cuts)):
            shards[i].extend(part.tolist())
    out = []
    for s in shards:
        arr = np.array(s, dtype=int)
        rng.shuffle(arr)
        out.append(
            (
                torch.tensor(x[arr], dtype=torch.float32),
                torch.tensor(y[arr], dtype=torch.long),
            )
        )
    return out


def build_stages(seed: int = 7, n_per_class: int = 900, n_benchmark: int = 400) -> list[StageData]:
    """Generate all three stages of the curriculum with their benchmarks."""
    gen = DocumentGenerator(seed=seed)
    rng = np.random.default_rng(seed)
    stages: list[StageData] = []

    # Feature normalisation is fitted once, across *all* classes, so every stage
    # shares one scale. Fitting it on clean documents alone is a trap worth
    # naming: a clean payroll has exactly zero arithmetic residual, so that
    # feature's standard deviation is zero, and every anomalous value then
    # normalises to something astronomical. The tanh units saturate, gradients
    # vanish, and the model looks broken for reasons that have nothing to do
    # with the method. The standard deviation is also floored, for the same
    # reason at a smaller scale.
    reference = np.vstack([_class_data(gen, c, 300) for c in range(len(TASK_KINDS))])
    mu = reference.mean(axis=0)
    sd = np.maximum(reference.std(axis=0), 1e-2)

    def normalise(a: np.ndarray) -> np.ndarray:
        # Clipped because a single extreme document should not dominate a batch.
        return np.clip((a - mu) / sd, -10.0, 10.0)

    for stage, classes in enumerate(STAGE_CLASSES):
        xs, ys, bxs, bys = [], [], [], []
        for c in classes:
            train = normalise(_class_data(gen, c, n_per_class))
            bench = normalise(_class_data(gen, c, n_benchmark))
            xs.append(train)
            ys.append(np.full(len(train), c))
            bxs.append(bench)
            bys.append(np.full(len(bench), c))
        x, y = np.vstack(xs), np.concatenate(ys)
        bx, by = np.vstack(bxs), np.concatenate(bys)
        stages.append(
            StageData(
                stage=stage,
                task_id=TASK_IDS[classes[1]],
                shards=_dirichlet_split(x, y, N_FACTORIES, rng),
                benchmark_x=torch.tensor(bx, dtype=torch.float32),
                benchmark_y=torch.tensor(by, dtype=torch.long),
            )
        )
    return stages


def train_local(
    model: nn.Module,
    x: torch.Tensor,
    y: torch.Tensor,
    global_weights: list[torch.Tensor],
    epochs: int = LOCAL_EPOCHS,
) -> None:
    """One factory's local training. Data never leaves this function."""
    opt = torch.optim.SGD(model.parameters(), lr=LR)
    loss_fn = nn.CrossEntropyLoss()
    model.train()
    for _ in range(epochs):
        order = torch.randperm(len(y))
        for i in range(0, len(y), BATCH):
            b = order[i : i + BATCH]
            opt.zero_grad()
            loss = loss_fn(model(x[b]), y[b])
            loss = loss + fedprox_penalty(list(model.parameters()), global_weights)
            loss.backward()
            opt.step()


@dataclass
class RoundReport:
    """What a round produced, for the interface and the ledger."""

    stage: int
    task_id: str
    participants: list[str]
    trimmed_counts: list[int]
    update_norms: list[float]
    memory_bank_hash: str
    model_hash: str
    accuracies_bp: dict[str, int] = field(default_factory=dict)


class FederatedTrainer:
    """Runs the curriculum and produces candidates for the gate."""

    def __init__(self, use_replay: bool = True, seed: int = 7):
        self.use_replay = use_replay
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        torch.manual_seed(seed)
        self.model = Detector()
        self.bank = MemoryBank()
        self.stages = build_stages(seed)
        self.reports: list[RoundReport] = []

    def model_hash(self) -> str:
        """Hash of the weights. The ledger stores this, never the weights."""
        return hash_object(
            TAG_MODEL,
            [np.round(p.detach().numpy(), 6).tolist() for p in self.model.parameters()],
        )

    def run_stage(self, stage: int, weights_bp: list[int] | None = None) -> RoundReport:
        """Train one stage across all factories and fold in the new memory."""
        data = self.stages[stage]
        weights_bp = weights_bp or [10_000 // N_FACTORIES] * N_FACTORIES

        replay_x, replay_y = (None, None)
        if self.use_replay and self.bank.prototypes:
            rx, ry = self.bank.sample(self.rng)
            if rx is not None:
                replay_x = torch.tensor(rx, dtype=torch.float32)
                replay_y = torch.tensor(ry, dtype=torch.long)

        norms: list[float] = []
        trimmed_total = [0] * N_FACTORIES

        for _ in range(ROUNDS_PER_STAGE):
            global_weights = get_weights(self.model)
            updates: list[list[torch.Tensor]] = []
            norms = []
            for client in range(N_FACTORIES):
                cx, cy = data.shards[client]
                if len(cy) < BATCH:
                    updates.append([torch.zeros_like(w) for w in global_weights])
                    norms.append(0.0)
                    continue
                if replay_x is not None:
                    sel = torch.randperm(len(replay_y))[: len(cy)]
                    cx = torch.cat([cx, replay_x[sel]])
                    cy = torch.cat([cy, replay_y[sel]])

                local = Detector()
                set_weights(local, global_weights)
                train_local(local, cx, cy, global_weights)

                delta = [lw - gw for lw, gw in zip(get_weights(local), global_weights, strict=False)]
                delta, norm = clip_update(delta)
                delta = add_noise(delta)
                updates.append(delta)
                norms.append(norm)

            # Robustness and reputation are applied in two steps, because they
            # want different things. The trimmed mean tells us *who* behaved
            # like an outlier this round, coordinate by coordinate; the
            # reputation scores from the ledger tell us how much each factory
            # should count in the first place. So: trim to find outliers,
            # down-weight them, then average by reputation.
            _, trimmed = trimmed_mean(updates, trim=1)
            for i, t in enumerate(trimmed):
                trimmed_total[i] += t

            worst = max(trimmed) or 1
            effective = [
                max(1, int(w * (1.0 - 0.5 * t / worst)))
                for w, t in zip(weights_bp, trimmed, strict=False)
            ]
            averaged = weighted_average(updates, effective)
            set_weights(
                self.model, [g + a for g, a in zip(get_weights(self.model), averaged, strict=False)]
            )

        # End of stage: contribute noised summaries to the shared memory.
        if self.use_replay:
            for client in range(N_FACTORIES):
                cx, cy = data.shards[client]
                if len(cy) < 12:
                    continue
                self.bank.merge(
                    self.bank.summarise(cx.numpy(), cy.numpy(), self.rng)
                )

        report = RoundReport(
            stage=stage,
            task_id=data.task_id,
            participants=[f"factory-{i}" for i in range(N_FACTORIES)],
            trimmed_counts=trimmed_total,
            update_norms=norms,
            memory_bank_hash=self.bank.hash,
            model_hash=self.model_hash(),
        )
        self.reports.append(report)
        return report

    def evaluate_all(self) -> dict[str, int]:
        """Accuracy in basis points on every stage's benchmark seen so far."""
        return {
            s.task_id: accuracy_bp(self.model, s.benchmark_x, s.benchmark_y)
            for s in self.stages
        }

    # -- the bridge to the ledger ----------------------------------------
    def signed_evaluations(
        self,
        consortium,
        endorser_msps: list[str],
        round_id: str,
        candidate_id: str,
        candidate_hash: str,
        previous: dict[str, int],
        jitter_bp: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Each endorsing organisation evaluates the candidate and signs the result.

        In a deployment each organisation runs this on its own hardware against
        its own copy of the committed benchmark. Here they share one process, so
        `jitter_bp` optionally perturbs each organisation's numbers to exercise
        the contract's agreement tolerance — the same way real hardware
        differences would.
        """
        measured = self.evaluate_all()
        submissions = []
        for msp_id in endorser_msps:
            offset = 0 if jitter_bp == 0 else int(self.rng.integers(-jitter_bp, jitter_bp + 1))
            accuracies = {
                task: {
                    "candidate_bp": max(0, min(10_000, measured[task] + offset)),
                    "previous_bp": previous.get(task, 0),
                }
                for task in measured
            }
            identity = consortium.org_identity(msp_id)
            payload = {
                "round_id": round_id,
                "candidate_id": candidate_id,
                "candidate_hash": candidate_hash,
                "accuracies": accuracies,
            }
            submissions.append(
                {
                    "endorser_msp": msp_id,
                    "certificate_pem": identity.certificate_pem(),
                    "signature": sign(identity.private_key, payload),
                    "accuracies": accuracies,
                }
            )
        return submissions
