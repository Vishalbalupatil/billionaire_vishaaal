"""Unit tests for the ORB probability (logistic regression) model."""

from __future__ import annotations

import random

from billionaire.strategy.orb_probability import (
    CLASS_NAMES,
    FEATURE_NAMES,
    build_features,
    fit,
)


def test_build_features_is_stable_order() -> None:
    row = build_features(
        or_high=100.0, or_low=99.0, prev_close=99.5, today_open=99.7,
        vix_value=15.0, prev_day_return_pct=0.3, weekday=2,
    )
    assert len(row) == len(FEATURE_NAMES)
    # Intercept is always 1.0
    assert row[0] == 1.0
    # DoW one-hot: Wednesday (weekday=2) → dow_wed=1.0, others 0.
    assert row[5] == 0.0  # Tue
    assert row[6] == 1.0  # Wed
    assert row[7] == 0.0  # Thu


def test_fit_learns_separable_pattern() -> None:
    """Two well-separated classes: LONG when gap > 0, SHORT when gap < 0.
    After training, predictions on unseen samples from the same distribution
    should recover the label with high confidence. All other features are
    held constant so only ``gap_pct`` carries signal."""
    random.seed(42)
    features: list[list[float]] = []
    labels: list[str] = []

    for _ in range(300):
        gap = random.uniform(-0.5, 0.5)
        if abs(gap) < 0.05:
            continue  # skip ambiguous boundary cases
        label = "LONG" if gap > 0 else "SHORT"
        # Constant OR width → no confounding feature; only gap_pct should
        # end up with a non-zero coefficient.
        row = build_features(
            or_high=100.5, or_low=100.0,
            prev_close=100.0, today_open=100.0 + gap,
            vix_value=15.0, prev_day_return_pct=0.0, weekday=1,
        )
        features.append(row)
        labels.append(label)

    model = fit(
        features, labels, epochs=2000, learning_rate=0.5, l2=0.0,
        classes=["LONG", "SHORT"],
    )
    # Evaluate on 40 fresh points.
    correct = 0
    total = 0
    for _ in range(60):
        gap = random.uniform(-0.5, 0.5)
        if abs(gap) < 0.05:
            continue
        expected = "LONG" if gap > 0 else "SHORT"
        row = build_features(
            or_high=100.5, or_low=100.0, prev_close=100.0,
            today_open=100.0 + gap, vix_value=15.0, prev_day_return_pct=0.0, weekday=1,
        )
        probs = model.predict_proba(row)
        predicted = max(probs.items(), key=lambda kv: kv[1])[0]
        total += 1
        if predicted == expected:
            correct += 1
    # ≥80% accuracy on a linearly separable single-feature problem.
    assert correct / total >= 0.80, f"{correct}/{total}"


def test_predict_proba_sums_to_one() -> None:
    features = [[1.0, 0.1, 0.2, 15.0, 0.0, 0.0, 0.0, 0.0, 0.0]]
    labels = [CLASS_NAMES[0]]
    # Train tiny model just to instantiate weights.
    m = fit(features * 5, labels * 5, epochs=10, classes=CLASS_NAMES)
    probs = m.predict_proba(features[0])
    assert abs(sum(probs.values()) - 1.0) < 1e-9
    assert set(probs.keys()) == set(CLASS_NAMES)


def test_fit_raises_on_empty_dataset() -> None:
    import pytest

    with pytest.raises(ValueError):
        fit([], [])
