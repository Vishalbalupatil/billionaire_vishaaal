"""Main strategy orchestrator.

Ties together the AI signal generator, options strategy selector,
risk manager, and execution manager into a cohesive trading loop.
"""

from __future__ import annotations

import logging
from datetime import datetime

import pandas as pd

from ai_trader.ai.signals import SignalGenerator
from ai_trader.broker.base import BrokerClient
from ai_trader.config import TradingMode, get_settings
from ai_trader.models.domain import Candle, Instrument, Signal
from ai_trader.models.options import Greeks, OptionsPosition, OptionStrategy
from ai_trader.options.chain import (
    build_chain_from_quotes,
)
from ai_trader.options.pricing import nifty_strikes
from ai_trader.options.strategies import select_strategy
from ai_trader.risk.manager import RiskManager

log = logging.getLogger(__name__)


class StrategyEngine:
    """Main orchestrator for AI-driven options trading."""

    def __init__(self, broker: BrokerClient, risk_manager: RiskManager) -> None:
        self._broker = broker
        self._risk = risk_manager
        self._signal_gen = SignalGenerator()
        self._settings = get_settings()
        self._signals: list[Signal] = []
        self._strategies: list[OptionStrategy] = []
        self._active_positions: list[OptionsPosition] = []

    @property
    def signals(self) -> list[Signal]:
        return list(self._signals)

    @property
    def strategies(self) -> list[OptionStrategy]:
        return list(self._strategies)

    @property
    def active_positions(self) -> list[OptionsPosition]:
        return list(self._active_positions)

    def on_candle(
        self,
        instrument: Instrument,
        candles: list[Candle],
        vix: float = 15.0,
        spot_price: float | None = None,
    ) -> Signal | None:
        """Process a new candle and generate a signal if conditions are met."""
        if len(candles) < 50:
            return None

        df = pd.DataFrame([c.model_dump() for c in candles])

        # Fetch options context
        pcr = 1.0  # default; updated when chain data available

        signal = self._signal_gen.generate(
            instrument=instrument,
            candles_df=df,
            vix=vix,
            pcr=pcr,
            spot_price=spot_price,
        )

        if signal:
            self._signals.append(signal)
            log.info("Signal: %s %s conf=%.2f", signal.direction.value, instrument.tradingsymbol, signal.confidence)

        return signal

    def select_options_strategy(
        self,
        spot: float,
        chain_data: dict,
        signal: Signal,
        vix: float = 15.0,
    ) -> OptionStrategy | None:
        """Select an options strategy based on signal and market context."""
        strikes = chain_data.get("strikes", nifty_strikes(spot))
        ce_prices = chain_data.get("ce_prices", {})
        pe_prices = chain_data.get("pe_prices", {})
        ce_oi = chain_data.get("ce_oi", {})
        pe_oi = chain_data.get("pe_oi", {})
        expiry = chain_data.get("expiry", "")

        chain = build_chain_from_quotes(
            spot=spot,
            strikes=strikes,
            expiry_str=expiry,
            ce_prices=ce_prices,
            pe_prices=pe_prices,
            ce_oi=ce_oi,
            pe_oi=pe_oi,
        )

        if not chain:
            return None

        strategy = select_strategy(
            spot=spot,
            chain=chain,
            regime=signal.regime,
            direction=signal.direction,
            confidence=signal.confidence,
            vix=vix,
            lot_size=self._settings.default_lot_size,
        )

        if strategy:
            # Validate against risk
            portfolio_greeks = self._get_portfolio_greeks()
            ok, reason = self._risk.validate_options_strategy(strategy, portfolio_greeks)
            if not ok:
                log.warning("Strategy rejected: %s", reason)
                return None

            strategy.confidence = signal.confidence
            self._strategies.append(strategy)
            log.info(
                "Strategy selected: %s | max_profit=₹%.2f max_loss=₹%.2f",
                strategy.strategy_type.value, strategy.max_profit, strategy.max_loss,
            )

        return strategy

    def execute_strategy(self, strategy: OptionStrategy, spot: float) -> OptionsPosition | None:
        """Execute an options strategy by placing orders for all legs."""
        if self._settings.trading_mode == TradingMode.ANALYSIS:
            log.info("Analysis mode — not executing")
            return None

        can_trade, reason = self._risk.can_trade()
        if not can_trade:
            log.warning("Cannot trade: %s", reason)
            return None

        from ai_trader.models.domain import Exchange, OrderRequest, OrderType, ProductType, Side

        for leg in strategy.legs:
            symbol = f"NIFTY{leg.strike:.0f}{leg.option_type}"
            inst = Instrument(
                instrument_token=0,
                tradingsymbol=symbol,
                exchange=Exchange.NFO,
            )
            side = Side.BUY if leg.side == "BUY" else Side.SELL
            qty = leg.lots * self._settings.default_lot_size

            request = OrderRequest(
                instrument=inst,
                side=side,
                quantity=qty,
                order_type=OrderType.MARKET,
                product=ProductType.NRML,
                tag="AI_STRATEGY",
            )

            order = self._broker.place_order(request)
            log.info("Order placed: %s %s %d → %s", side.value, symbol, qty, order.status.value)

        position = OptionsPosition(
            strategy=strategy,
            entry_spot=spot,
            current_spot=spot,
            entry_time=datetime.utcnow().isoformat(),
            status="OPEN",
        )
        self._active_positions.append(position)
        return position

    def check_exits(self, spot: float) -> list[OptionsPosition]:
        """Check if any active positions should be closed."""
        closed: list[OptionsPosition] = []

        if self._risk.should_square_off():
            log.info("Square-off time — closing all positions")
            for pos in self._active_positions:
                if pos.status == "OPEN":
                    pos.status = "CLOSED"
                    closed.append(pos)
            self._active_positions = [p for p in self._active_positions if p.status == "OPEN"]
            return closed

        for pos in self._active_positions:
            if pos.status != "OPEN":
                continue

            # Check stop loss / target
            pnl_pct = 0.0
            if pos.strategy.max_loss != 0:
                pnl_pct = pos.unrealized_pnl / abs(pos.strategy.max_loss)

            if pnl_pct < -1.0:
                pos.status = "STOPPED_OUT"
                closed.append(pos)
                log.info("Position stopped out at %.2f%% loss", pnl_pct * 100)
            elif pnl_pct > 0.8:  # Take profit at 80% of max profit
                pos.status = "TARGET_HIT"
                closed.append(pos)
                log.info("Position target hit at %.2f%% profit", pnl_pct * 100)

        self._active_positions = [p for p in self._active_positions if p.status == "OPEN"]
        return closed

    def _get_portfolio_greeks(self) -> Greeks:
        """Aggregate Greeks across all active positions."""
        total = Greeks()
        for pos in self._active_positions:
            if pos.status == "OPEN":
                g = pos.strategy.net_greeks
                total = Greeks(
                    delta=total.delta + g.delta,
                    gamma=total.gamma + g.gamma,
                    theta=total.theta + g.theta,
                    vega=total.vega + g.vega,
                )
        return total
