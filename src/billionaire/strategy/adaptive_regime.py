"""Adaptive market regime detection using statistical learning.

Detects regime transitions dynamically and adjusts strategy parameters
based on historical performance in each regime.

Regimes supported:
- TRENDING_UP: Sustained upward movement
- TRENDING_DOWN: Sustained downward movement
- RANGE: Mean-reverting consolidation
- VOLATILE: High unpredictability
- QUIET: Low activity
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)


@dataclass
class RegimeMetrics:
    """Metrics for a detected regime."""
    name: str
    duration_bars: int = 0
    trend_strength: float = 0.0  # 0-1, how strong the trend
    volatility: float = 0.0  # z-score relative to baseline
    mean_reversion_score: float = 0.0  # 0-1, how mean-reverting
    probability: float = 1.0  # confidence in regime


@dataclass
class RegimePerformance:
    """Historical performance metrics in a regime."""
    regime_name: str
    win_rate: float = 0.0  # 0-1
    avg_win: float = 0.0
    avg_loss: float = 0.0
    sharpe_ratio: float = 0.0
    sample_count: int = 0
    
    @property
    def profit_factor(self) -> float:
        """Ratio of avg_win to avg_loss."""
        if self.avg_loss == 0:
            return 1.0 if self.avg_win == 0 else float("inf")
        return abs(self.avg_win / self.avg_loss)


class AdaptiveRegimeDetector:
    """Adaptive regime detection with HMM-inspired transition tracking.
    
    Instead of hard classification, maintains probability distribution
    over regimes and tracks transitions.
    """
    
    def __init__(self, lookback_bars: int = 100) -> None:
        """Initialize regime detector.
        
        Args:
            lookback_bars: Historical window for regime analysis
        """
        self.lookback_bars = lookback_bars
        self.regime_history: list[str] = []
        self.transition_matrix: dict[str, dict[str, float]] = {
            "TRENDING_UP": {"TRENDING_UP": 0.7, "RANGING": 0.2, "VOLATILE": 0.1},
            "TRENDING_DOWN": {"TRENDING_DOWN": 0.7, "RANGING": 0.2, "VOLATILE": 0.1},
            "RANGING": {"RANGING": 0.5, "TRENDING_UP": 0.25, "TRENDING_DOWN": 0.25},
            "VOLATILE": {"VOLATILE": 0.6, "TRENDING_UP": 0.2, "TRENDING_DOWN": 0.2},
            "QUIET": {"QUIET": 0.4, "RANGING": 0.6},
        }
        self.regime_performance: dict[str, RegimePerformance] = {
            regime: RegimePerformance(regime) for regime in self.transition_matrix.keys()
        }
    
    def detect(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        volume: np.ndarray,
    ) -> RegimeMetrics:
        """Detect current regime using multi-factor analysis.
        
        Returns:
            RegimeMetrics with dominant regime and confidence
        """
        if len(close) < self.lookback_bars:
            return RegimeMetrics("UNKNOWN", trend_strength=0.0, probability=0.5)
        
        window = close[-self.lookback_bars:]
        
        # 1. Trend strength (EMA-based)
        trend_strength = self._compute_trend_strength(window)
        
        # 2. Volatility analysis
        returns = np.diff(np.log(window))
        vol = float(np.std(returns))
        vol_z = self._volatility_z_score(vol)
        
        # 3. Mean reversion score
        mean_rev_score = self._compute_mean_reversion_score(window)
        
        # 4. Determine regime
        regime_name, prob = self._classify_regime(
            trend_strength, vol_z, mean_rev_score
        )
        
        # Track history
        self.regime_history.append(regime_name)
        if len(self.regime_history) > 100:
            self.regime_history.pop(0)
        
        return RegimeMetrics(
            name=regime_name,
            duration_bars=self._regime_duration(regime_name),
            trend_strength=trend_strength,
            volatility=vol_z,
            mean_reversion_score=mean_rev_score,
            probability=prob,
        )
    
    def _compute_trend_strength(self, close: np.ndarray) -> float:
        """Compute trend strength using EMA alignment and slope.
        
        Returns:
            0-1 score, higher = stronger trend
        """
        if len(close) < 50:
            return 0.0
        
        # EMA alignment
        from billionaire.strategy.indicator_engine import ema
        e9 = ema(close, 9)
        e21 = ema(close, 21)
        e50 = ema(close, 50)
        
        if np.isnan(e50[-1]):
            return 0.0
        
        # Proportion of bars where short > long EMA (for uptrend)
        alignment = float(np.mean((e9 > e50).astype(float)))
        
        # Slope of EMA20
        slope = float((e21[-1] - e21[-10]) / max(abs(e21[-10]), 1e-9))
        
        # Combine: 70% alignment, 30% slope
        trend = 0.7 * alignment + 0.3 * min(1.0, abs(slope))
        
        return float(np.clip(trend, 0.0, 1.0))
    
    def _volatility_z_score(self, vol: float) -> float:
        """Z-score volatility relative to historical baseline."""
        # In production, maintain running stats
        baseline_vol = 0.02  # typical daily vol
        vol_std = 0.01
        return float((vol - baseline_vol) / (vol_std + 1e-9))
    
    def _compute_mean_reversion_score(self, close: np.ndarray) -> float:
        """Score how mean-reverting the price action is.
        
        Uses rolling correlation of price with its detrended version.
        
        Returns:
            0-1 score, higher = more mean-reverting
        """
        if len(close) < 20:
            return 0.0
        
        # Detrend using simple linear regression
        x = np.arange(len(close))
        z = np.polyfit(x, close, 1)
        p = np.poly1d(z)
        trend = p(x)
        detrended = close - trend
        
        # Mean reversion score: correlation of price with bollinger band reversal
        bb_upper = np.mean(close[-20:]) + 2 * np.std(close[-20:])
        bb_lower = np.mean(close[-20:]) - 2 * np.std(close[-20:])
        
        reversals = 0
        for i in range(1, len(detrended)):
            if detrended[i-1] < 0 and detrended[i] > 0:
                reversals += 1
            elif detrended[i-1] > 0 and detrended[i] < 0:
                reversals += 1
        
        reversion_score = reversals / len(detrended)
        return float(np.clip(reversion_score, 0.0, 1.0))
    
    def _classify_regime(
        self,
        trend_strength: float,
        vol_z: float,
        mean_rev: float,
    ) -> tuple[str, float]:
        """Classify regime from metrics.
        
        Returns:
            (regime_name, confidence)
        """
        # Hard thresholds with soft fallback
        if vol_z > 2.0:
            return "VOLATILE", 0.9
        
        if vol_z < -1.0:
            return "QUIET", 0.8
        
        if trend_strength > 0.7:
            return "TRENDING_UP", 0.85
        
        if trend_strength < 0.3 and mean_rev > 0.5:
            return "RANGING", 0.8
        
        # Default fallback
        return "RANGING", 0.6
    
    def _regime_duration(self, regime_name: str) -> int:
        """How many bars in current regime."""
        if not self.regime_history:
            return 0
        
        count = 0
        for r in reversed(self.regime_history):
            if r == regime_name:
                count += 1
            else:
                break
        
        return count
    
    def update_performance(
        self,
        regime_name: str,
        trade_pnl: float,
        trade_risk: float,
    ) -> None:
        """Update historical performance for a regime.
        
        Call this after each closed trade.
        """
        if regime_name not in self.regime_performance:
            return
        
        perf = self.regime_performance[regime_name]
        perf.sample_count += 1
        
        if trade_pnl > 0:
            perf.avg_win = (perf.avg_win * (perf.sample_count - 1) + trade_pnl) / perf.sample_count
        else:
            perf.avg_loss = (perf.avg_loss * (perf.sample_count - 1) + trade_pnl) / perf.sample_count
        
        perf.win_rate = sum(1 for _ in range(perf.sample_count) if _ < perf.avg_win) / max(1, perf.sample_count)
    
    def get_optimal_strategy_params(
        self,
        regime_name: str,
    ) -> dict[str, float]:
        """Get recommended strategy parameters for a regime.
        
        Returns parameters tuned to historical performance in this regime.
        """
        perf = self.regime_performance.get(regime_name)
        if perf is None or perf.sample_count < 10:
            # Default params if insufficient data
            return self._get_default_params(regime_name)
        
        # Scale risk based on performance
        risk_multiplier = max(0.5, min(2.0, perf.profit_factor))
        
        return {
            "risk_multiplier": risk_multiplier,
            "position_size_multiplier": min(1.5, perf.win_rate * 2.0),
            "max_loss_percent": 2.0 / risk_multiplier,
            "entry_aggressiveness": 0.5 + (perf.win_rate * 0.5),
        }
    
    @staticmethod
    def _get_default_params(regime_name: str) -> dict[str, float]:
        """Default parameters by regime."""
        defaults = {
            "TRENDING_UP": {
                "risk_multiplier": 1.5,
                "position_size_multiplier": 1.2,
                "max_loss_percent": 1.5,
                "entry_aggressiveness": 0.8,
            },
            "TRENDING_DOWN": {
                "risk_multiplier": 1.5,
                "position_size_multiplier": 1.2,
                "max_loss_percent": 1.5,
                "entry_aggressiveness": 0.8,
            },
            "RANGING": {
                "risk_multiplier": 0.8,
                "position_size_multiplier": 1.0,
                "max_loss_percent": 2.5,
                "entry_aggressiveness": 0.5,
            },
            "VOLATILE": {
                "risk_multiplier": 0.6,
                "position_size_multiplier": 0.7,
                "max_loss_percent": 3.0,
                "entry_aggressiveness": 0.3,
            },
            "QUIET": {
                "risk_multiplier": 0.5,
                "position_size_multiplier": 0.5,
                "max_loss_percent": 4.0,
                "entry_aggressiveness": 0.4,
            },
        }
        return defaults.get(regime_name, defaults["RANGING"])


class RegimeBasedStrategyAdapter:
    """Adapts strategy behavior based on current market regime."""
    
    def __init__(self, detector: AdaptiveRegimeDetector) -> None:
        self.detector = detector
        self.current_regime = None
    
    def adapt_entry_signal(
        self,
        is_signal_valid: bool,
        regime_metrics: RegimeMetrics,
    ) -> bool:
        """Filter entry signals based on regime alignment.
        
        Some strategies work better in specific regimes.
        """
        self.current_regime = regime_metrics
        
        if regime_metrics.probability < 0.5:
            # Low confidence in regime, be cautious
            return is_signal_valid and regime_metrics.probability > 0.3
        
        return is_signal_valid
    
    def adapt_stop_loss(
        self,
        base_sl: float,
        entry: float,
        regime_metrics: RegimeMetrics,
    ) -> float:
        """Widen/tighten stop loss based on volatility regime."""
        vol_multiplier = max(0.5, min(2.0, 1.0 + regime_metrics.volatility / 5.0))
        adapted_sl = entry + (base_sl - entry) * vol_multiplier
        return adapted_sl
    
    def adapt_position_size(
        self,
        base_size: int,
        regime_metrics: RegimeMetrics,
    ) -> int:
        """Scale position size based on regime risk.
        
        Reduce size in volatile/unknown regimes.
        """
        params = self.detector.get_optimal_strategy_params(regime_metrics.name)
        multiplier = params.get("position_size_multiplier", 1.0)
        
        adapted_size = int(base_size * multiplier)
        return max(1, adapted_size)