"""Backtest performance metrics."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass
class PerformanceMetrics:
    trades: int
    wins: int
    losses: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    expectancy: float
    max_drawdown: float
    sharpe_like: float
    total_pnl: float


def performance_metrics(pnls: list[float]) -> PerformanceMetrics:
    if not pnls:
        return PerformanceMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    arr = np.asarray(pnls, dtype=float)
    wins = arr[arr > 0]
    losses = arr[arr < 0]
    total = float(arr.sum())
    n = len(arr)
    wr = len(wins) / n if n else 0
    avg_w = float(wins.mean()) if len(wins) else 0.0
    avg_l = float(losses.mean()) if len(losses) else 0.0
    pf = float(wins.sum() / -losses.sum()) if len(losses) and losses.sum() != 0 else float("inf")
    expectancy = wr * avg_w + (1 - wr) * avg_l
    # max drawdown from equity curve
    equity = np.cumsum(arr)
    peak = np.maximum.accumulate(equity)
    dd = equity - peak
    max_dd = float(dd.min()) if len(dd) else 0.0
    # sharpe-like: mean/std of per-trade pnls * sqrt(N) (not annualised — illustrative)
    mean, std = float(arr.mean()), float(arr.std())
    sharpe = (mean / std) * math.sqrt(len(arr)) if std > 0 else 0.0
    return PerformanceMetrics(
        trades=n,
        wins=len(wins),
        losses=len(losses),
        win_rate=round(wr, 4),
        avg_win=round(avg_w, 2),
        avg_loss=round(avg_l, 2),
        profit_factor=round(pf, 3) if pf != float("inf") else float("inf"),
        expectancy=round(expectancy, 2),
        max_drawdown=round(max_dd, 2),
        sharpe_like=round(sharpe, 3),
        total_pnl=round(total, 2),
    )
