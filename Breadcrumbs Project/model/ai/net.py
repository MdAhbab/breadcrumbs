"""
The detector, and the tasks it learns.

A small multi-layer perceptron over the 16 engineered features from
`datagen`. Small on purpose: the interesting claim in this project is not that a
neural network can classify anomalies — it obviously can — but that a consortium
can govern which version of it goes live. A larger model would make the demo
slower and prove nothing extra.

Four classes, learned in three stages, exactly as the report describes:

  class 0  clean document                  present at every stage
  class 1  wage-register inconsistency     stage 1
  class 2  forged compliance certificate   stage 2
  class 3  chemical-inventory misreporting stage 3

The difficulty is that by the time stage 3 arrives, stage 1's data is long gone.
A detector trained naively will be excellent at chemical misreporting and will
have quietly forgotten wages. That is the forgetting the Continuity Gate exists
to catch.
"""

from __future__ import annotations

import torch
import torch.nn as nn

from ..datagen import N_FEATURES

N_CLASSES = 4

# Which anomaly kinds from the generator make up each learned class.
TASK_KINDS: dict[int, list[str | None]] = {
    0: [None],
    1: ["arithmetic", "overtime"],
    2: ["checksum"],
    3: ["outlier", "backdating"],
}

# Task identifiers as they appear on the ledger and in the interface.
TASK_IDS = {
    1: "wage_register_inconsistency",
    2: "forged_certificate",
    3: "chemical_misreporting",
}

# Which classes are present at each stage. Class 0 is always present.
STAGE_CLASSES = [[0, 1], [0, 2], [0, 3]]


class Detector(nn.Module):
    """Two hidden layers, tanh activations, four-way output."""

    def __init__(self, n_features: int = N_FEATURES, hidden: int = 48):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_features, hidden),
            nn.Tanh(),
            nn.Linear(hidden, hidden),
            nn.Tanh(),
            nn.Linear(hidden, N_CLASSES),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


def get_weights(model: nn.Module) -> list[torch.Tensor]:
    return [p.detach().clone() for p in model.parameters()]


def set_weights(model: nn.Module, weights: list[torch.Tensor]) -> None:
    with torch.no_grad():
        for p, w in zip(model.parameters(), weights, strict=True):
            p.copy_(w)


@torch.no_grad()
def accuracy(model: nn.Module, x: torch.Tensor, y: torch.Tensor) -> float:
    model.eval()
    return float((model(x).argmax(dim=1) == y).float().mean())


def accuracy_bp(model: nn.Module, x: torch.Tensor, y: torch.Tensor) -> int:
    """
    Accuracy in basis points, as an integer.

    The gate contract compares integers because two peers must agree byte for
    byte and floating point across different hardware does not guarantee that.
    Rounding happens once, here, at the boundary between the learning plane and
    the ledger.
    """
    return int(round(accuracy(model, x, y) * 10_000))
