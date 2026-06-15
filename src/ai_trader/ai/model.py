"""Ensemble ML model for trade signal prediction.

Combines XGBoost for classification with gradient-boosted confidence scoring.
The model predicts: {BULLISH, BEARISH, NEUTRAL} and a confidence score [0, 1].

Training is done on historical data; at runtime the model is loaded from disk.
If no trained model exists, it falls back to a rule-based scoring system.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from ai_trader.ai.features import FEATURE_COLUMNS

log = logging.getLogger(__name__)

MODEL_DIR = Path("models_trained")


class EnsembleModel:
    """XGBoost ensemble for directional prediction + confidence scoring."""

    def __init__(self) -> None:
        self._classifier = None
        self._confidence_model = None
        self._is_trained = False
        self._try_load()

    def _try_load(self) -> None:
        clf_path = MODEL_DIR / "xgb_classifier.json"
        conf_path = MODEL_DIR / "xgb_confidence.json"
        if clf_path.exists() and conf_path.exists():
            try:
                from xgboost import XGBClassifier, XGBRegressor

                self._classifier = XGBClassifier()
                self._classifier.load_model(str(clf_path))
                self._confidence_model = XGBRegressor()
                self._confidence_model.load_model(str(conf_path))
                self._is_trained = True
                log.info("Loaded trained ensemble model from %s", MODEL_DIR)
            except Exception as e:
                log.warning("Failed to load trained model: %s — using rule-based fallback", e)

    @property
    def is_trained(self) -> bool:
        return self._is_trained

    def predict(self, features_df: pd.DataFrame) -> tuple[int, float]:
        """Predict direction and confidence from feature row(s).

        Returns
        -------
        direction : int
            1 = bullish, -1 = bearish, 0 = neutral
        confidence : float
            Confidence score between 0 and 1.
        """
        if features_df.empty:
            return 0, 0.0

        row = features_df[FEATURE_COLUMNS].iloc[[-1]].copy()
        row = row.fillna(0)

        if self._is_trained and self._classifier is not None and self._confidence_model is not None:
            return self._predict_ml(row)
        return self._predict_rules(row)

    def _predict_ml(self, row: pd.DataFrame) -> tuple[int, float]:
        pred = int(self._classifier.predict(row)[0])
        direction_map = {0: -1, 1: 0, 2: 1}  # 0=bearish, 1=neutral, 2=bullish
        direction = direction_map.get(pred, 0)
        confidence = float(np.clip(self._confidence_model.predict(row)[0], 0, 1))
        return direction, confidence

    def _predict_rules(self, row: pd.DataFrame) -> tuple[int, float]:
        """Rule-based fallback when no ML model is trained."""
        r = row.iloc[0]
        score = 0.0
        total_weight = 0.0

        # EMA crossovers (weight: 3)
        ema_cross = float(r.get("ema_crossover_9_21", 0))
        if ema_cross > 0.001:
            score += 3
        elif ema_cross < -0.001:
            score -= 3
        total_weight += 3

        # RSI (weight: 2)
        rsi = float(r.get("rsi_14", 50))
        if rsi > 60:
            score += 2
        elif rsi < 40:
            score -= 2
        elif 45 <= rsi <= 55:
            pass  # neutral
        total_weight += 2

        # MACD histogram (weight: 2)
        macd_hist = float(r.get("macd_histogram", 0))
        if macd_hist > 0:
            score += 2
        elif macd_hist < 0:
            score -= 2
        total_weight += 2

        # SuperTrend direction (weight: 2)
        st = float(r.get("supertrend_dir", 0))
        score += 2 * st
        total_weight += 2

        # Volume confirmation (weight: 1)
        vol_ratio = float(r.get("volume_ratio", 1))
        if vol_ratio > 1.5:
            score += 1 * (1 if score > 0 else -1)
        total_weight += 1

        # Bollinger Band position (weight: 1)
        bb_pos = float(r.get("bb_position", 0.5))
        if bb_pos > 0.8:
            score += 1
        elif bb_pos < 0.2:
            score -= 1
        total_weight += 1

        # VIX context (weight: 1)
        vix_high = float(r.get("vix_high", 0))
        if vix_high:
            score *= 0.8  # reduce conviction in high-vol
        total_weight += 1

        # PCR context (weight: 1)
        pcr_bullish = float(r.get("pcr_bullish", 0))
        pcr_bearish = float(r.get("pcr_bearish", 0))
        if pcr_bullish:
            score += 1
        elif pcr_bearish:
            score -= 1
        total_weight += 1

        # Normalize
        if total_weight == 0:
            return 0, 0.0

        normalized = score / total_weight
        confidence = min(abs(normalized), 1.0)

        if normalized > 0.15:
            direction = 1
        elif normalized < -0.15:
            direction = -1
        else:
            direction = 0

        return direction, round(confidence, 4)

    def train(self, features_df: pd.DataFrame, labels: pd.Series, returns: pd.Series) -> dict[str, float]:
        """Train the ensemble model on historical data.

        Parameters
        ----------
        features_df : pd.DataFrame
            Feature matrix with FEATURE_COLUMNS.
        labels : pd.Series
            Direction labels: -1 (bearish), 0 (neutral), 1 (bullish).
        returns : pd.Series
            Forward returns used as confidence target (absolute value, clipped 0-1).

        Returns
        -------
        Metrics dict with accuracy, precision, recall.
        """
        from sklearn.metrics import accuracy_score, precision_score, recall_score
        from sklearn.model_selection import train_test_split
        from xgboost import XGBClassifier, XGBRegressor

        X = features_df[FEATURE_COLUMNS].fillna(0)
        y_cls = (labels + 1).astype(int)  # map -1,0,1 → 0,1,2
        y_conf = returns.abs().clip(0, 1)

        X_train, X_test, y_train, y_test = train_test_split(X, y_cls, test_size=0.2, shuffle=False)
        _, _, yc_train, yc_test = train_test_split(X, y_conf, test_size=0.2, shuffle=False)

        # Direction classifier
        self._classifier = XGBClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.05,
            objective="multi:softmax",
            num_class=3,
            eval_metric="mlogloss",
            use_label_encoder=False,
        )
        self._classifier.fit(X_train, y_train)

        # Confidence regressor
        self._confidence_model = XGBRegressor(
            n_estimators=150,
            max_depth=5,
            learning_rate=0.05,
            objective="reg:squarederror",
        )
        self._confidence_model.fit(X_train, yc_train)

        # Save
        MODEL_DIR.mkdir(exist_ok=True)
        self._classifier.save_model(str(MODEL_DIR / "xgb_classifier.json"))
        self._confidence_model.save_model(str(MODEL_DIR / "xgb_confidence.json"))
        self._is_trained = True

        # Metrics
        y_pred = self._classifier.predict(X_test)
        metrics = {
            "accuracy": float(accuracy_score(y_test, y_pred)),
            "precision_macro": float(precision_score(y_test, y_pred, average="macro", zero_division=0)),
            "recall_macro": float(recall_score(y_test, y_pred, average="macro", zero_division=0)),
        }
        log.info("Model trained — %s", metrics)
        return metrics
