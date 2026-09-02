"""
Acceptance Test 10: Trivial baseline reaches well short of perfect (ROC-AUC / accuracy < 96%).
"""

from __future__ import annotations

import numpy as np

from data.generator import DocumentGenerator


def _extract_naive_features(rows: list[dict], record_type: str) -> np.ndarray:
    """Extract 4 simple naive summary statistics."""
    feat = np.zeros(4, dtype=np.float64)
    if record_type == "payroll_register":
        nets = [float(r.get("net_pay_bdt", 0.0)) for r in rows]
        ots = [float(r.get("ot_hours", 0.0)) for r in rows]
        feat[0] = max(nets) if nets else 0.0
        feat[1] = np.mean(nets) if nets else 0.0
        feat[2] = max(ots) if ots else 0.0
        feat[3] = np.mean(ots) if ots else 0.0
    elif record_type == "safety_inspection":
        feat[0] = float(len(rows))
        feat[1] = float(sum(1 for r in rows if r.get("result") == "remediate"))
    elif record_type == "chemical_inventory":
        closing = [float(r.get("closing_kg", 0.0)) for r in rows]
        feat[0] = max(closing) if closing else 0.0
        feat[1] = np.mean(closing) if closing else 0.0
    return feat


def test_trivial_baseline_does_not_score_perfect():
    """
    Train a simple logistic model / threshold on naive features.
    Assert that due to subtle continuous severity (1-3% noise) and realistic site variations,
    a trivial classifier achieves well short of 99% accuracy / F1 on the realistic mix.
    """
    gen = DocumentGenerator(seed=42, anomaly_rate=0.04)
    docs = gen.generate(n_docs=1000)

    X = np.stack([_extract_naive_features(d.rows, d.record_type) for d in docs])
    y = np.array([d.label for d in docs], dtype=np.float64)

    # Standardize X
    mu = X.mean(axis=0)
    std = np.where(X.std(axis=0) == 0, 1.0, X.std(axis=0))
    X_norm = (X - mu) / std

    # Fit a simple ridge logistic regression with gradient descent
    weights = np.zeros(X_norm.shape[1])
    lr = 0.05
    for _ in range(150):
        logits = X_norm @ weights
        preds = 1.0 / (1.0 + np.exp(-np.clip(logits, -15.0, 15.0)))
        grad = X_norm.T @ (preds - y) / len(y) + 0.01 * weights
        weights -= lr * grad

    final_preds = (1.0 / (1.0 + np.exp(-np.clip(X_norm @ weights, -15.0, 15.0)))) > 0.5
    # Calculate F1 score for anomaly class
    tp = np.sum((final_preds == 1) & (y == 1))
    fp = np.sum((final_preds == 1) & (y == 0))
    fn = np.sum((final_preds == 0) & (y == 1))
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = 2 * precision * recall / max(1e-6, precision + recall)

    # Trivial classifier on naive features must not achieve near-perfect F1 (> 0.95)
    assert f1 < 0.95, (
        f"Trivial model scored suspiciously high F1={f1:.4f} (corpus is too easy)"
    )
