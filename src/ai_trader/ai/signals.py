"""AI signal generator — combines ML model output with options context
to produce actionable trade signals.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime

import pandas as pd

from ai_trader.ai.features import build_features
from ai_trader.ai.model import EnsembleModel
from ai_trader.ai.regime import detect_regime
from ai_trader.config import get_settings
from ai_trader.models.domain import (
    Instrument,
    MarketRegime,
    Signal,
    SignalDirection,
)

log = logging.getLogger(__name__)


class SignalGenerator:
    """Generates trade signals using the AI ensemble model."""

    def __init__(self) -> None:
        self._model = EnsembleModel()
        self._settings = get_settings()

    @property
    def model(self) -> EnsembleModel:
        return self._model

    def generate(
        self,
        instrument: Instrument,
        candles_df: pd.DataFrame,
        vix: float = 15.0,
        pcr: float = 1.0,
        spot_price: float | None = None,
    ) -> Signal | None:
        """Generate a signal from candle data + market context.

        Returns None if confidence is below threshold or data is insufficient.
        """
        if len(candles_df) < 50:
            log.debug("Insufficient candles (%d < 50) for signal generation", len(candles_df))
            return None

        # Build features
        features_df = build_features(candles_df, vix=vix, pcr=pcr)

        # Detect regime
        regime = detect_regime(candles_df, vix=vix)

        # ML prediction
        direction_int, confidence = self._model.predict(features_df)

        if confidence < self._settings.min_signal_confidence:
            log.debug(
                "Signal confidence %.3f below threshold %.3f",
                confidence, self._settings.min_signal_confidence,
            )
            return None

        if direction_int == 0:
            direction = SignalDirection.NEUTRAL
        elif direction_int == 1:
            direction = SignalDirection.BULLISH
        else:
            direction = SignalDirection.BEARISH

        # Calculate entry, SL, targets from ATR
        current_price = spot_price or float(candles_df["close"].iloc[-1])
        atr_raw = float(features_df["atr_14"].iloc[-1]) if "atr_14" in features_df.columns else None
        atr = atr_raw if (atr_raw is not None and not math.isnan(atr_raw)) else current_price * 0.01

        if direction == SignalDirection.BULLISH:
            entry = current_price
            stop_loss = entry - 1.5 * atr
            target1 = entry + 2 * atr
            target2 = entry + 3 * atr
        elif direction == SignalDirection.BEARISH:
            entry = current_price
            stop_loss = entry + 1.5 * atr
            target1 = entry - 2 * atr
            target2 = entry - 3 * atr
        else:
            entry = current_price
            stop_loss = entry - atr
            target1 = entry + atr
            target2 = None

        risk_per_unit = abs(entry - stop_loss)
        max_risk = self._settings.max_capital * (self._settings.risk_per_trade_pct / 100)
        suggested_qty = max(1, int(max_risk / risk_per_unit)) if risk_per_unit > 0 else 0
        if suggested_qty > 0:
            # Round to lot size
            suggested_qty = (suggested_qty // instrument.lot_size) * instrument.lot_size
            suggested_qty = max(instrument.lot_size, suggested_qty)

        reasons = self._build_reasons(features_df, direction, regime)
        expected_rr = abs(target1 - entry) / risk_per_unit if risk_per_unit > 0 else 0

        return Signal(
            instrument=instrument,
            direction=direction,
            entry=round(entry, 2),
            stop_loss=round(stop_loss, 2),
            target1=round(target1, 2),
            target2=round(target2, 2) if target2 else None,
            confidence=round(confidence, 4),
            regime=regime,
            reasons=reasons,
            strategy_name="AI_ENSEMBLE",
            suggested_qty=suggested_qty,
            risk_rupees=round(risk_per_unit * suggested_qty, 2),
            expected_rr=round(expected_rr, 2),
            ts=datetime.utcnow(),
        )

    def _build_reasons(
        self,
        features_df: pd.DataFrame,
        direction: SignalDirection,
        regime: MarketRegime,
    ) -> list[str]:
        """Build human-readable reasons for the signal."""
        reasons: list[str] = []
        r = features_df.iloc[-1]

        reasons.append(f"Regime: {regime.value}")

        rsi = float(r.get("rsi_14", 50))
        if rsi > 60:
            reasons.append(f"RSI bullish ({rsi:.1f})")
        elif rsi < 40:
            reasons.append(f"RSI bearish ({rsi:.1f})")

        ema_cross = float(r.get("ema_crossover_9_21", 0))
        if ema_cross > 0.001:
            reasons.append("EMA 9/21 bullish crossover")
        elif ema_cross < -0.001:
            reasons.append("EMA 9/21 bearish crossover")

        macd_hist = float(r.get("macd_histogram", 0))
        if macd_hist > 0:
            reasons.append("MACD histogram positive")
        elif macd_hist < 0:
            reasons.append("MACD histogram negative")

        st = float(r.get("supertrend_dir", 0))
        if st > 0:
            reasons.append("SuperTrend bullish")
        elif st < 0:
            reasons.append("SuperTrend bearish")

        vol_ratio = float(r.get("volume_ratio", 1))
        if vol_ratio > 1.5:
            reasons.append(f"Volume spike ({vol_ratio:.1f}x)")

        if self._model.is_trained:
            reasons.append("ML model: trained ensemble")
        else:
            reasons.append("ML model: rule-based fallback")

        return reasons
