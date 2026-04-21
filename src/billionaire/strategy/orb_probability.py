"""ML-lite probability model for today's ORB outcome.

Given a backtest result (history of past ORB trades + no-trade days) and a
live snapshot of today's features, predict P(LONG break), P(SHORT break),
P(no break) for the remainder of the session.

Why not a heavy ML stack? Two reasons:
    1. Logistic regression has ~10 parameters. On 2 years of ~500 trading
       days it generalises fine, and is trivially explainable — every
       coefficient is a log-odds you can stare at.
    2. Shipping scikit-learn / pytorch for a 10-parameter model triples
       the Docker image size and adds a wall of FutureWarnings per request.

Implementation is a pure-stdlib multinomial logistic regression trained
with batch gradient descent. Deterministic, reproducible, and fast
enough (~50ms for 500 samples with 5 features).

Features (all computed from bars up to 09:20 IST on the target day):
    * ``opening_range_pct`` — (ORH-ORL)/ORL, log-transformed
    * ``gap_pct`` — today's open vs prev-day close
    * ``vix_level`` — India VIX at 09:20 IST
    * ``prev_day_return_pct`` — prev-day close-open, signed
    * ``day_of_week`` — one-hot, baseline Monday

Targets: ``LONG`` (trade was LONG and was a win or loss), ``SHORT`` (ditto),
``NONE`` (no break / no-trade day). The output labels are thus the 3
outcomes the UI needs to show.

Warning: this model will NOT be reliable with <100 training samples.
The API layer clamps probabilities back to (1/3, 1/3, 1/3) in that case.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

# Feature vector order (matters for deserialisation).
FEATURE_NAMES: list[str] = [
    "bias",
    "log_or_pct",
    "gap_pct",
    "vix_level",
    "prev_day_return_pct",
    "dow_tue",
    "dow_wed",
    "dow_thu",
    "dow_fri",
]

CLASS_NAMES: list[str] = ["NONE", "LONG", "SHORT"]


def _dow_onehot(weekday: int) -> list[float]:
    """weekday 0=Monday. Baseline is Monday so 4 features for Tue-Fri."""
    return [
        1.0 if weekday == 1 else 0.0,  # Tue
        1.0 if weekday == 2 else 0.0,  # Wed
        1.0 if weekday == 3 else 0.0,  # Thu
        1.0 if weekday == 4 else 0.0,  # Fri
    ]


@dataclass(frozen=True)
class FeatureRow:
    date: str
    features: list[float]
    label: str  # NONE | LONG | SHORT


def build_features(
    *,
    or_high: float,
    or_low: float,
    prev_close: float,
    today_open: float,
    vix_value: float,
    prev_day_return_pct: float,
    weekday: int,
) -> list[float]:
    """Construct one feature vector. Safe for zero / negative inputs."""
    or_pct = max((or_high - or_low) / max(or_low, 1e-9), 1e-9)
    log_or_pct = math.log(or_pct)
    gap_pct = (today_open - prev_close) / max(prev_close, 1e-9) * 100.0
    return [
        1.0,  # bias intercept
        log_or_pct,
        gap_pct,
        vix_value,
        prev_day_return_pct,
        *_dow_onehot(weekday),
    ]


def _softmax(logits: list[float]) -> list[float]:
    m = max(logits)
    exps = [math.exp(x - m) for x in logits]
    total = sum(exps)
    return [e / total for e in exps] if total > 0 else [1.0 / len(logits)] * len(logits)


@dataclass
class LogisticModel:
    """Multinomial logistic regression weights.

    ``W`` is ``[n_classes][n_features]``. ``classes`` maps row-index →
    class name (``"LONG"`` / ``"SHORT"`` / ``"NONE"``).
    """

    W: list[list[float]]
    classes: list[str]
    feature_names: list[str]
    n_samples: int
    trained_at: str  # ISO datetime

    def predict_proba(self, features: list[float]) -> dict[str, float]:
        logits = [
            sum(w_j * x_j for w_j, x_j in zip(row, features, strict=True))
            for row in self.W
        ]
        probs = _softmax(logits)
        return dict(zip(self.classes, probs, strict=True))

    def to_dict(self) -> dict[str, Any]:
        return {
            "W": self.W,
            "classes": self.classes,
            "feature_names": self.feature_names,
            "n_samples": self.n_samples,
            "trained_at": self.trained_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> LogisticModel:
        return cls(
            W=[list(row) for row in d["W"]],
            classes=list(d["classes"]),
            feature_names=list(d["feature_names"]),
            n_samples=int(d["n_samples"]),
            trained_at=str(d["trained_at"]),
        )


def _zero_weights(n_classes: int, n_features: int) -> list[list[float]]:
    return [[0.0] * n_features for _ in range(n_classes)]


def fit(
    features: list[list[float]],
    labels: list[str],
    *,
    learning_rate: float = 0.05,
    epochs: int = 500,
    l2: float = 0.001,
    classes: list[str] | None = None,
) -> LogisticModel:
    """Batch gradient descent for multinomial logistic regression.

    L2 regularisation applied to all weights including the bias. This keeps
    the model well-behaved when training samples are scarce. ``classes``
    order is used for the output row ordering; if omitted, derived from the
    sorted unique labels.
    """
    if not features:
        raise ValueError("no training samples")
    cls = classes or sorted(set(labels))
    n_classes = len(cls)
    n_features = len(features[0])
    cls_idx = {c: i for i, c in enumerate(cls)}

    W = _zero_weights(n_classes, n_features)
    n = len(features)

    for _ in range(epochs):
        grads = _zero_weights(n_classes, n_features)
        for row, label in zip(features, labels, strict=True):
            logits = [
                sum(w_j * x_j for w_j, x_j in zip(W[k], row, strict=True))
                for k in range(n_classes)
            ]
            probs = _softmax(logits)
            y_true = cls_idx[label]
            for k in range(n_classes):
                err = probs[k] - (1.0 if k == y_true else 0.0)
                for j in range(n_features):
                    grads[k][j] += err * row[j]
        for k in range(n_classes):
            for j in range(n_features):
                grads[k][j] = grads[k][j] / n + l2 * W[k][j]
                W[k][j] -= learning_rate * grads[k][j]

    return LogisticModel(
        W=W,
        classes=cls,
        feature_names=FEATURE_NAMES,
        n_samples=n,
        trained_at=datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
    )


def save_model(model: LogisticModel, path: str) -> None:
    with open(path, "w") as f:
        json.dump(model.to_dict(), f, indent=2)


def load_model(path: str) -> LogisticModel:
    with open(path) as f:
        return LogisticModel.from_dict(json.load(f))
