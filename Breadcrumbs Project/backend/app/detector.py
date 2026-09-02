"""
The detector, actually run.

Everything else in this product is about the *governance* of the model: the
benchmarks sealed before training, the signed evaluations, the gate that refuses
a candidate which forgot. All of that was wired and none of it ever ran the
model on a document. There was a trained network sitting in `model/artefacts/`
that nothing loaded.

This module loads it and scores one record. That is the whole of "deploying the
AI": a 25-input, two-hidden-layer network of about 18 KB, a mean and a standard
deviation, and a threshold. It runs on the CPU inside the API process in about a
millisecond. There is no model server, no GPU and no second deployment, and that
is a property of the model's size rather than a shortcut.

WHAT THE SCORE IS NOT. It is not evidence and the interface must never let it
read as evidence. The ledger proves a record has not changed since it was
committed; the detector guesses whether the record looks wrong, and it is wrong
often enough that the number matters. At the operating point shipped here it
flags about one in ten clean documents, and on the anomaly family the corpus
calls `cross_inconsistency` it is at chance, by construction — that family is
invisible from a single document. Every response therefore carries the measured
rates alongside the score, so a screen cannot show the verdict without them.
"""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

ARTEFACTS = _ROOT / "model" / "artefacts"

# Which trained arm is served. `replay` is the one the Continuity Gate promoted;
# `sequential` is the ablation that forgets, kept for comparison and not served.
ARM = "replay"

WEIGHTS = ARTEFACTS / f"detector-{ARM}.pt"
SCALER = ARTEFACTS / f"scale-{ARM}.npz"
OPERATING_POINT = ARTEFACTS / f"operating-point-{ARM}.json"
MEASURED = ARTEFACTS / "training.json"

# What each learned class covers, from `model/ai/net.py:TASK_KINDS`. Class 0 is a
# clean document; the other three are the anomaly families of the three waves.
CLASS_LABEL = {
    0: "no anomaly",
    1: "arithmetic or overtime",
    2: "checksum or back-dating",
    3: "chemical or outlier",
}

_lock = threading.Lock()
_loaded: dict[str, Any] | None = None


def _load() -> dict[str, Any] | None:
    """
    Load the weights once per process, or report that there are none.

    A missing artefact is not an error. A fresh clone has no trained model until
    somebody runs the training, and the honest response to "screen this record"
    in that state is "there is no detector here", not a fabricated score.
    """
    global _loaded
    with _lock:
        if _loaded is not None:
            return _loaded or None
        if not (WEIGHTS.is_file() and SCALER.is_file() and OPERATING_POINT.is_file()):
            _loaded = {}
            return None

        import numpy as np
        import torch

        from data.features import N_FEATURES, extract_features
        from model.ai.net import Detector

        # `Detector()` defaults its input width to `model.datagen.N_FEATURES`,
        # which is 16 — the old extractor. The trained artefact is 25 wide,
        # from `data/features.py`. Constructing it without this argument raises
        # a shape error on load, and it is the single easiest way to get this
        # wrong when deploying.
        network = Detector(n_features=N_FEATURES)
        network.load_state_dict(torch.load(WEIGHTS, map_location="cpu"))
        network.eval()

        scale = np.load(SCALER)
        point = json.loads(OPERATING_POINT.read_text())
        budget = str(point["headline_budget"])
        # The JSON keys are written as "0.01" / "0.05" / "0.10"; a budget of 0.1
        # stringifies to "0.1", which is not one of them.
        tau = point["tau_by_budget"].get(budget) or point["tau_by_budget"][f"{float(budget):.2f}"]

        _loaded = {
            "network": network,
            "extract": extract_features,
            "mu": scale["mu"],
            "sd": scale["sd"],
            "tau": float(tau),
            "budget": float(point["headline_budget"]),
            "point": point,
            "measured": json.loads(MEASURED.read_text()) if MEASURED.is_file() else {},
            "torch": torch,
            "np": np,
        }
        return _loaded


def available() -> bool:
    return _load() is not None


def status() -> dict[str, Any]:
    """
    What is deployed, and how well it is known to work.

    Served alongside every score and on its own, because an operating point is
    a choice somebody made and a reader is entitled to see which one and what it
    cost. The rates are measurements over five seeds, not targets.
    """
    state = _load()
    if state is None:
        return {
            "trained": False,
            "reason": (
                "No detector in model/artefacts. Train one with: "
                "cd 'Breadcrumbs Project' && python -m model.run train"
            ),
        }

    measured = state["measured"]
    rates = (measured.get("operating_points_replay") or {}).get(
        f"{state['budget']:.2f}", {}
    )
    by_kind = measured.get("detection_by_kind_replay", {})

    return {
        "trained": True,
        "arm": ARM,
        "features": int(len(state["mu"])),
        "parameters": sum(p.numel() for p in state["network"].parameters()),
        "weights_bytes": WEIGHTS.stat().st_size,
        "threshold": state["tau"],
        "false_positive_budget": state["budget"],
        "chosen_on": state["point"].get("chosen_on"),
        "measured": {
            "detection": _mean(rates.get("detection")),
            "false_positive": _mean(rates.get("false_positive")),
            "balanced_accuracy": _mean(rates.get("balanced")),
            "roc_auc": _mean(measured.get("roc_auc_replay")),
            "seeds": len(measured.get("seeds", [])),
        },
        "detection_by_kind": {k: _mean(v) for k, v in sorted(by_kind.items())},
        "blind_to": {
            "kind": "cross_inconsistency",
            "detection": _mean(by_kind.get("cross_inconsistency")),
            "why": (
                "A cross-inconsistency is two documents that are each perfectly "
                "valid and disagree with one another. Nothing in a single "
                "document reveals it, so this detector is at chance on that "
                "family by construction rather than by accident. Catching it "
                "needs the ledger, not the model."
            ),
        },
        "note": (
            "A score is not evidence. The ledger proves a record has not changed "
            "since it was committed; this only guesses whether the record looks "
            "wrong, and at this operating point it is wrong about roughly one "
            "clean document in ten."
        ),
    }


def _mean(pair: Any) -> float | None:
    """`training.json` stores every figure as [mean, standard deviation]."""
    if isinstance(pair, list) and pair:
        return round(float(pair[0]), 4)
    return None


def screen(record_type: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Score one document.

    Takes the rows rather than a record id so this stays a pure function of the
    document: the caller has already decided the requester may see it.
    """
    state = _load()
    if state is None:
        return {"scored": False, **status()}

    np = state["np"]
    torch = state["torch"]

    features = state["extract"]({"record_type": record_type, "rows": rows})
    # A zero standard deviation would divide by zero on a constant feature.
    normalised = (features - state["mu"]) / np.where(state["sd"] == 0, 1.0, state["sd"])

    with torch.no_grad():
        logits = state["network"](
            torch.tensor(normalised, dtype=torch.float32).unsqueeze(0)
        )
        probability = torch.softmax(logits, dim=1).numpy()[0]

    anomalous = float(1.0 - probability[0])
    kind_index = int(probability[1:].argmax() + 1)

    # The measured rates travel with every score, not on request. A probability
    # beside a cryptographic proof invites a reader to treat the two as the same
    # kind of fact, and the error rates are the whole of the difference. Making
    # them a second call would mean a screen could render the number without
    # them, which is exactly the screen this is trying not to be.
    return {
        **status(),
        "scored": True,
        "score": round(anomalous, 4),
        "threshold": state["tau"],
        "flagged": anomalous >= state["tau"],
        "likely_kind": CLASS_LABEL[kind_index] if anomalous >= state["tau"] else None,
        "per_class": {
            CLASS_LABEL[i]: round(float(p), 4) for i, p in enumerate(probability)
        },
        "features_used": int(len(features)),
        "verdict": (
            "Worth a look" if anomalous >= state["tau"] else "Nothing stands out"
        ),
        "caveat": (
            "This is the model's opinion, not a finding. It is not on the ledger, "
            "it is not signed, and nobody is accountable for it. Its purpose is to "
            "order a queue of documents for a human, and at this threshold about "
            "one flagged document in three is clean."
            if anomalous >= state["tau"]
            else "This document did not cross the threshold. That is not a clean "
            "bill of health: the detector misses roughly one anomaly in four, and "
            "it cannot see a cross-document inconsistency at all."
        ),
    }
