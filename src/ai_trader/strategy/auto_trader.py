"""Autonomous trading engine — scans markets, identifies setups,
enters trades, monitors positions, and exits for profit/loss.

This is the main loop that makes the system fully autonomous.
It works for both equity (cash) trades and Nifty 50 options.
"""

from __future__ import annotations

import logging
from datetime import datetime

import pandas as pd

from ai_trader.broker.base import BrokerClient
from ai_trader.config import TradingMode, get_settings
from ai_trader.execution.scheduler import is_market_open, minutes_to_close
from ai_trader.models.domain import (
    Exchange,
    Instrument,
    OrderRequest,
    OrderStatus,
    OrderType,
    ProductType,
    Side,
)
from ai_trader.models.scanner import (
    AutoTradeAction,
    AutoTradeLog,
    ChartPattern,
    PatternBias,
    ScanResult,
    TrendAnalysis,
    TrendDirection,
)
from ai_trader.risk.manager import RiskManager
from ai_trader.scanner.equity import rank_results, scan_stock
from ai_trader.scanner.patterns import detect_patterns
from ai_trader.scanner.trend import analyze_trend

log = logging.getLogger(__name__)


class AutoTrader:
    """Autonomous trading engine that scans, identifies, and trades."""

    def __init__(self, broker: BrokerClient, risk_manager: RiskManager) -> None:
        self._broker = broker
        self._risk = risk_manager
        self._settings = get_settings()
        self._scan_results: list[ScanResult] = []
        self._patterns: list[ChartPattern] = []
        self._trends: dict[str, TrendAnalysis] = {}
        self._trade_log: list[AutoTradeLog] = []
        self._active_trades: dict[str, _ActiveTrade] = {}

    @property
    def scan_results(self) -> list[ScanResult]:
        return list(self._scan_results)

    @property
    def patterns(self) -> list[ChartPattern]:
        return list(self._patterns)

    @property
    def trends(self) -> dict[str, TrendAnalysis]:
        return dict(self._trends)

    @property
    def trade_log(self) -> list[AutoTradeLog]:
        return list(self._trade_log)

    @property
    def active_trades(self) -> dict[str, dict]:
        return {
            sym: {
                "symbol": sym,
                "side": t.side,
                "entry": t.entry,
                "stop_loss": t.stop_loss,
                "target": t.target,
                "quantity": t.quantity,
                "pnl": t.unrealized_pnl(t.last_price),
                "last_price": t.last_price,
            }
            for sym, t in self._active_trades.items()
        }

    def scan_market(self, market_data: dict[str, pd.DataFrame]) -> list[ScanResult]:
        """Scan all provided stocks and return ranked results.

        market_data: {symbol: OHLCV DataFrame}
        """
        if not is_market_open():
            log.debug("Market closed — skipping scan")
            return []

        all_results: list[ScanResult] = []
        for symbol, df in market_data.items():
            results = scan_stock(df, symbol)
            all_results.extend(results)

            # Also detect patterns and trends
            patterns = detect_patterns(df, symbol)
            self._patterns = [
                p for p in self._patterns if p.symbol != symbol
            ] + patterns

            trend = analyze_trend(df, symbol)
            self._trends[symbol] = trend

        ranked = rank_results(all_results, top_n=10)
        self._scan_results = ranked

        self._log(
            "MARKET",
            AutoTradeAction.SCAN,
            f"Scanned {len(market_data)} stocks, found {len(ranked)} setups",
        )

        return ranked

    def evaluate_and_trade(self, market_data: dict[str, pd.DataFrame]) -> list[AutoTradeLog]:
        """Main autonomous loop: scan → filter → enter → manage → exit."""
        if not is_market_open():
            return []

        can_trade, reason = self._risk.can_trade()
        if not can_trade:
            self._log("SYSTEM", AutoTradeAction.SKIP, f"Cannot trade: {reason}")
            return self._trade_log[-5:]

        # 1. Update existing positions
        self._update_active_trades(market_data)

        # 2. Check exits for active trades
        self._check_exits(market_data)

        # 3. Auto square-off near market close
        if minutes_to_close() <= 15:
            self._square_off_all(market_data)
            return self._trade_log[-10:]

        # 4. Scan for new opportunities
        results = self.scan_market(market_data)

        # 5. Filter and enter new trades
        if self._settings.trading_mode != TradingMode.ANALYSIS:
            for result in results:
                if result.symbol in self._active_trades:
                    continue  # Already in this stock
                if len(self._active_trades) >= self._settings.max_open_positions:
                    break

                if self._should_enter(result):
                    self._enter_trade(result, market_data.get(result.symbol))

        return self._trade_log[-10:]

    def _should_enter(self, result: ScanResult) -> bool:
        """Decide whether to enter a trade based on scan result + trend + patterns."""
        # Minimum score threshold
        if result.score < 60:
            return False

        # Check trend alignment
        trend = self._trends.get(result.symbol)
        if trend:
            if result.entry > result.stop_loss:  # Bullish trade
                if trend.overall in (TrendDirection.DOWN, TrendDirection.STRONG_DOWN):
                    self._log(result.symbol, AutoTradeAction.SKIP, "Trend not aligned (bearish)")
                    return False
            else:  # Bearish trade
                if trend.overall in (TrendDirection.UP, TrendDirection.STRONG_UP):
                    self._log(result.symbol, AutoTradeAction.SKIP, "Trend not aligned (bullish)")
                    return False

        # Check for confirming patterns
        matching_patterns = [p for p in self._patterns if p.symbol == result.symbol]
        pattern_confirms = False
        for pat in matching_patterns:
            if result.entry > result.stop_loss and pat.bias == PatternBias.BULLISH or result.entry < result.stop_loss and pat.bias == PatternBias.BEARISH:
                pattern_confirms = True

        # Boost confidence with pattern confirmation
        if pattern_confirms:
            self._log(result.symbol, AutoTradeAction.SIGNAL, f"Pattern confirms: score={result.score}")
        elif result.score < 70:
            self._log(result.symbol, AutoTradeAction.SKIP, f"Score {result.score} too low without pattern")
            return False

        # Risk validation
        risk_per_unit = abs(result.entry - result.stop_loss)
        if risk_per_unit <= 0:
            return False

        max_risk = self._settings.max_capital * (self._settings.risk_per_trade_pct / 100)
        position_risk = risk_per_unit * self._settings.default_lot_size
        if position_risk > max_risk:
            self._log(result.symbol, AutoTradeAction.SKIP, f"Risk ₹{position_risk:.0f} > max ₹{max_risk:.0f}")
            return False

        self._log(result.symbol, AutoTradeAction.SIGNAL, f"Entry signal: {result.scan_type} score={result.score}")
        return True

    def _enter_trade(self, result: ScanResult, df: pd.DataFrame | None) -> None:
        """Place an order and track the trade."""
        is_bullish = result.entry > result.stop_loss
        side = Side.BUY if is_bullish else Side.SELL

        # Calculate quantity based on risk
        risk_per_unit = abs(result.entry - result.stop_loss)
        max_risk = self._settings.max_capital * (self._settings.risk_per_trade_pct / 100)
        quantity = max(1, int(max_risk / risk_per_unit)) if risk_per_unit > 0 else 0

        if quantity <= 0:
            return

        instrument = Instrument(
            instrument_token=0,
            tradingsymbol=result.symbol,
            exchange=Exchange.NSE,
        )

        request = OrderRequest(
            instrument=instrument,
            side=side,
            quantity=quantity,
            order_type=OrderType.MARKET,
            product=ProductType.MIS,
            tag=f"auto_{result.scan_type.value.lower()}",
        )

        # Set price for paper broker
        self._broker.set_price(result.symbol, result.ltp)

        order = self._broker.place_order(request)

        if order.status in (OrderStatus.COMPLETE, OrderStatus.PENDING):
            self._active_trades[result.symbol] = _ActiveTrade(
                symbol=result.symbol,
                side=side.value,
                entry=order.avg_price or result.ltp,
                stop_loss=result.stop_loss,
                target=result.target,
                quantity=quantity,
                last_price=result.ltp,
            )
            self._log(
                result.symbol,
                AutoTradeAction.ENTER,
                f"{side.value} {quantity}x @ {result.ltp:.2f} SL={result.stop_loss:.2f} TGT={result.target:.2f}",
            )
        else:
            self._log(result.symbol, AutoTradeAction.SKIP, f"Order rejected: {order.message}")

    def _update_active_trades(self, market_data: dict[str, pd.DataFrame]) -> None:
        """Update LTP for active trades."""
        for symbol, trade in self._active_trades.items():
            df = market_data.get(symbol)
            if df is not None and len(df) > 0:
                trade.last_price = float(df["close"].iloc[-1])

    def _check_exits(self, market_data: dict[str, pd.DataFrame]) -> None:
        """Check stop-loss and target for all active trades."""
        to_exit: list[str] = []

        for symbol, trade in self._active_trades.items():
            ltp = trade.last_price
            if trade.side == "BUY":
                if ltp <= trade.stop_loss:
                    self._log(symbol, AutoTradeAction.EXIT, f"Stop-loss hit @ {ltp:.2f}")
                    to_exit.append(symbol)
                elif ltp >= trade.target:
                    self._log(symbol, AutoTradeAction.EXIT, f"Target hit @ {ltp:.2f}")
                    to_exit.append(symbol)
            else:  # SELL
                if ltp >= trade.stop_loss:
                    self._log(symbol, AutoTradeAction.EXIT, f"Stop-loss hit @ {ltp:.2f}")
                    to_exit.append(symbol)
                elif ltp <= trade.target:
                    self._log(symbol, AutoTradeAction.EXIT, f"Target hit @ {ltp:.2f}")
                    to_exit.append(symbol)

        for symbol in to_exit:
            self._exit_trade(symbol)

    def _exit_trade(self, symbol: str) -> None:
        """Close an active trade."""
        trade = self._active_trades.get(symbol)
        if not trade:
            return

        exit_side = Side.SELL if trade.side == "BUY" else Side.BUY

        instrument = Instrument(
            instrument_token=0,
            tradingsymbol=symbol,
            exchange=Exchange.NSE,
        )

        request = OrderRequest(
            instrument=instrument,
            side=exit_side,
            quantity=trade.quantity,
            order_type=OrderType.MARKET,
            product=ProductType.MIS,
            tag="auto_exit",
        )

        self._broker.set_price(symbol, trade.last_price)
        order = self._broker.place_order(request)

        if order.status in (OrderStatus.REJECTED, OrderStatus.CANCELLED):
            self._log(symbol, AutoTradeAction.MONITOR, f"Exit order not filled: {order.message}")
            return

        pnl = trade.unrealized_pnl(trade.last_price)
        self._log(symbol, AutoTradeAction.EXIT, f"Closed @ {trade.last_price:.2f} P&L=₹{pnl:.2f}", pnl=pnl)

        # Update risk manager with realized P&L
        self._risk.update_daily_pnl(self._risk.daily_pnl + pnl)

        del self._active_trades[symbol]

    def _square_off_all(self, market_data: dict[str, pd.DataFrame]) -> None:
        """Close all positions before market close."""
        if not self._active_trades:
            return

        self._log("SYSTEM", AutoTradeAction.EXIT, f"Square-off: closing {len(self._active_trades)} trades")
        symbols = list(self._active_trades.keys())
        for symbol in symbols:
            self._exit_trade(symbol)

    def _log(self, symbol: str, action: AutoTradeAction, details: str, pnl: float = 0.0) -> None:
        entry = AutoTradeLog(symbol=symbol, action=action, details=details, pnl=pnl)
        self._trade_log.append(entry)
        log.info("[AutoTrader] %s %s: %s", symbol, action.value, details)


class _ActiveTrade:
    """Internal state for an active auto-trade."""

    def __init__(
        self,
        symbol: str,
        side: str,
        entry: float,
        stop_loss: float,
        target: float,
        quantity: int,
        last_price: float,
    ) -> None:
        self.symbol = symbol
        self.side = side
        self.entry = entry
        self.stop_loss = stop_loss
        self.target = target
        self.quantity = quantity
        self.last_price = last_price
        self.entered_at = datetime.utcnow()

    def unrealized_pnl(self, ltp: float) -> float:
        if self.side == "BUY":
            return (ltp - self.entry) * self.quantity
        return (self.entry - ltp) * self.quantity
