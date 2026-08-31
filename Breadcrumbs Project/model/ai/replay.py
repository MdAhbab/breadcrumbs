"""
Ledger-anchored prototype replay.

Replay is the most effective defence against forgetting, but the standard form
stores real past examples, which is impossible here: a buffer of old wage rows is
a privacy breach with extra steps.

Instead each factory summarises its local data into a few cluster centres per
category, with a spread and a count. Noise is added to each centre before it is
shared, and the summaries are aggregated across factories into a memory bank. In
later stages each factory rehearses on synthetic records drawn from that bank
alongside its real current data. No original record is stored or transmitted, yet
older categories keep being practised.

**Be careful what this is called.** Adding noise to a released statistic is not
differential privacy, which needs a bounded sensitivity and a stated privacy
budget. This design has neither, and it releases the per-category variances and
record counts with no noise at all. A rival's variance on wage features is
exactly what this system promises not to leak. The honest description is *noised
aggregate summaries*. Making it real means clipping contributions, noising every
released quantity, and stating the budget. That is specified work, not finished
work, and `MemoryBank.privacy_note()` returns exactly that sentence so no
interface can quietly overstate it.

The blockchain contribution is the anchoring: the hash of each memory bank is
written to the ledger and bound to the model version trained against it. Anyone
can later verify which memory a given model was rehearsed on.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from ..ledger.crypto import TAG_BANK, hash_object

K_PROTO = 3          # clusters kept per class; captures more than one mode
DP_SIGMA = 0.10      # noise added to each centre before it is shared
REPLAY_PER_CLASS = 300


@dataclass
class Prototype:
    """One class's summary, as shared."""

    class_id: int
    centres: np.ndarray  # (k, d) noised
    variance: np.ndarray  # (d,) NOT noised — see the module docstring
    counts: np.ndarray  # (k,) NOT noised

    def to_dict(self) -> dict[str, Any]:
        """
        Canonical form for hashing.

        Rounded to 6 decimal places before hashing so that two organisations
        computing the same summary on different hardware produce the same digest.
        Without the rounding, the last bit of a float would change the bank hash
        and the ledger anchor would be useless.
        """
        return {
            "class_id": self.class_id,
            "centres": np.round(self.centres, 6).tolist(),
            "variance": np.round(self.variance, 6).tolist(),
            "counts": self.counts.astype(int).tolist(),
        }


def _kmeans(x: np.ndarray, k: int, rng: np.random.Generator, iters: int = 25):
    if len(x) <= k:
        return x.copy(), np.ones(len(x), dtype=int)
    centres = x[rng.choice(len(x), k, replace=False)].copy()
    for _ in range(iters):
        d = ((x[:, None, :] - centres[None, :, :]) ** 2).sum(axis=2)
        a = d.argmin(axis=1)
        for j in range(k):
            if (a == j).any():
                centres[j] = x[a == j].mean(axis=0)
    d = ((x[:, None, :] - centres[None, :, :]) ** 2).sum(axis=2)
    a = d.argmin(axis=1)
    return centres, np.array([max(1, int((a == j).sum())) for j in range(k)])


class MemoryBank:
    """Aggregated prototypes across factories and stages."""

    def __init__(self, sigma: float = DP_SIGMA, k: int = K_PROTO):
        self.sigma = sigma
        self.k = k
        self.prototypes: dict[int, Prototype] = {}

    def summarise(
        self, x: np.ndarray, y: np.ndarray, rng: np.random.Generator
    ) -> dict[int, Prototype]:
        """
        Build one factory's local summaries. Raw records never leave this call.
        """
        out: dict[int, Prototype] = {}
        for c in np.unique(y):
            xs = x[y == c]
            if len(xs) < self.k * 3:
                continue
            centres, counts = _kmeans(xs, self.k, rng)
            noised = centres + rng.normal(0, self.sigma, size=centres.shape)
            out[int(c)] = Prototype(int(c), noised, xs.var(axis=0) + 1e-3, counts)
        return out

    def merge(self, contributions: dict[int, Prototype]) -> None:
        """Fold one factory's summaries into the shared bank."""
        for class_id, proto in contributions.items():
            if class_id not in self.prototypes:
                self.prototypes[class_id] = proto
                continue
            existing = self.prototypes[class_id]
            self.prototypes[class_id] = Prototype(
                class_id,
                np.vstack([existing.centres, proto.centres])[: self.k * 2],
                (existing.variance + proto.variance) / 2.0,
                np.concatenate([existing.counts, proto.counts])[: self.k * 2],
            )

    def sample(
        self, rng: np.random.Generator, per_class: int = REPLAY_PER_CLASS
    ) -> tuple[np.ndarray | None, np.ndarray | None]:
        """Draw synthetic rehearsal records from the summaries."""
        xs, ys = [], []
        for class_id, proto in sorted(self.prototypes.items()):
            weights = proto.counts / proto.counts.sum()
            take = rng.multinomial(per_class, weights)
            for j, n in enumerate(take):
                if n > 0:
                    xs.append(rng.normal(proto.centres[j], np.sqrt(proto.variance), size=(n, proto.centres.shape[1])))
                    ys.append(np.full(n, class_id))
        if not xs:
            return None, None
        return np.vstack(xs), np.concatenate(ys)

    @property
    def hash(self) -> str:
        """
        The digest anchored on the ledger and bound to a model version.

        This is the part that is genuinely new: generative and prototype replay
        both already exist, but making the memory a versioned, hash-anchored,
        auditable object does not.
        """
        return hash_object(
            TAG_BANK,
            {
                "sigma": round(self.sigma, 6),
                "k": self.k,
                "prototypes": [p.to_dict() for _, p in sorted(self.prototypes.items())],
            },
        )

    @staticmethod
    def privacy_note() -> str:
        """The sentence every interface showing this bank must display verbatim."""
        return (
            "Noised aggregate summaries, not differential privacy: there is no "
            "sensitivity bound and no privacy budget, and the released variances "
            "and record counts carry no noise at all."
        )
