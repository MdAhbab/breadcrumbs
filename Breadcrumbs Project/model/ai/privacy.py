"""
Update clipping, added noise, and robust aggregation.

Three defences, and one honest conflict between them.

Model updates leak information about the data that produced them — gradient
inversion can reconstruct training examples, and membership inference can tell
whether a particular record was used. So federated learning is not private by
itself, and this module exists because saying "the data never moves" is not a
sufficient answer.

The conflict, stated in the report and inherited here: secure aggregation hides
individual updates and reveals only their sum. Coordinate-wise trimmed mean
discards extreme values, which requires ranking each participant's contribution.
Contribution scoring requires attributing quality to named participants. The
second and third need to see what the first is designed to hide. You cannot
simply have all three.

The first deployment's choice, implemented here: run robust aggregation and
contribution scoring on updates the aggregator can read, and rely on clipping,
added noise and locally engineered features for privacy rather than on
cryptographic hiding. That is a weaker privacy position than secure aggregation
and it is stated plainly rather than buried. Secure aggregation becomes possible
later through committee decryption or ranking under multi-party computation.
"""

from __future__ import annotations

import torch

CLIP_NORM = 5.0
NOISE_SIGMA = 0.01


def clip_update(update: list[torch.Tensor], max_norm: float = CLIP_NORM) -> tuple[list[torch.Tensor], float]:
    """
    Scale an update down to a bounded norm.

    Clipping does two jobs at once: it bounds how much any single record can
    influence the global model, and it caps the damage one malicious participant
    can do in a round. Returns the update and its original norm, because the
    norm is what contribution scoring and outlier detection work from.
    """
    total = torch.sqrt(sum((t.double() ** 2).sum() for t in update))
    norm = float(total)
    if norm > max_norm:
        scale = max_norm / (norm + 1e-12)
        return [t * scale for t in update], norm
    return [t.clone() for t in update], norm


def add_noise(
    update: list[torch.Tensor], sigma: float = NOISE_SIGMA, generator: torch.Generator | None = None
) -> list[torch.Tensor]:
    """Gaussian noise on a clipped update. Not a differential privacy guarantee."""
    return [t + torch.normal(0.0, sigma, size=t.shape, generator=generator) for t in update]


def trimmed_mean(
    updates: list[list[torch.Tensor]], trim: int = 1
) -> tuple[list[torch.Tensor], list[int]]:
    """
    Coordinate-wise trimmed mean.

    For each parameter coordinate independently, drop the `trim` highest and
    `trim` lowest values and average the rest. A participant submitting a wildly
    scaled update is excluded coordinate by coordinate rather than wholesale,
    which is what makes this robust to a minority of dishonest contributors
    without needing to identify them first.

    Also returns, per participant, how often it was trimmed — the signal that
    feeds the reputation chaincode.
    """
    n = len(updates)
    if n == 0:
        raise ValueError("nothing to aggregate")
    if n <= 2 * trim:
        # Not enough participants to trim; fall back to a plain mean rather than
        # silently dropping everybody.
        return [torch.stack(p).mean(dim=0) for p in zip(*updates, strict=False)], [0] * n

    trimmed_counts = [0] * n
    out: list[torch.Tensor] = []
    for coordinate_group in zip(*updates, strict=False):
        stacked = torch.stack(coordinate_group)  # (n, *shape)
        flat = stacked.reshape(n, -1)
        order = flat.argsort(dim=0)
        keep_mask = torch.ones_like(flat, dtype=torch.bool)
        for t in range(trim):
            keep_mask.scatter_(0, order[t : t + 1], False)
            keep_mask.scatter_(0, order[n - 1 - t : n - t], False)
        for i in range(n):
            trimmed_counts[i] += int((~keep_mask[i]).sum())
        kept = (flat * keep_mask).sum(dim=0) / keep_mask.sum(dim=0).clamp(min=1)
        out.append(kept.reshape(stacked.shape[1:]))
    return out, trimmed_counts


def weighted_average(
    updates: list[list[torch.Tensor]], weights_bp: list[int]
) -> list[torch.Tensor]:
    """
    Federated averaging weighted by reputation score.

    Weights arrive in basis points from the reputation chaincode, so the
    influence each factory has on the shared model is a consortium decision
    recorded on the ledger rather than a server-side configuration value.
    """
    total = sum(weights_bp)
    if total == 0:
        raise ValueError("weights sum to zero")
    fractions = [w / total for w in weights_bp]
    if len(fractions) != len(updates):
        raise ValueError(
            f"{len(updates)} updates but {len(fractions)} weights; a mismatch here"
            " would silently drop a participant from the round"
        )
    return [
        sum(f * t for f, t in zip(fractions, group, strict=True))
        for group in zip(*updates, strict=True)
    ]


def fedprox_penalty(
    local: list[torch.Tensor], global_weights: list[torch.Tensor], mu: float = 0.01
) -> torch.Tensor:
    """
    FedProx proximal term.

    Six factories hold very different data — different sites, product mixes and
    error profiles. Plain federated averaging lets a client with unusual data
    drag the global model a long way in one round. This penalises drift from the
    global weights and is what makes non-IID participation stable.
    """
    return (mu / 2) * sum(
        ((w - g) ** 2).sum() for w, g in zip(local, global_weights, strict=False)
    )
