"""Options strategy selection engine.

Selects the optimal options strategy based on:
- Market regime (from AI regime detector)
- IV level
- Signal direction and confidence
- Risk budget
"""

from __future__ import annotations

import logging

from ai_trader.models.domain import MarketRegime, SignalDirection
from ai_trader.models.options import (
    Greeks,
    OptionChainRow,
    OptionStrategy,
    OptionStrategyType,
    PayoffPoint,
    StrategyLeg,
)

log = logging.getLogger(__name__)


def select_strategy(
    spot: float,
    chain: list[OptionChainRow],
    regime: MarketRegime,
    direction: SignalDirection,
    confidence: float,
    vix: float = 15.0,
    lot_size: int = 25,
) -> OptionStrategy | None:
    """Select the best options strategy given current conditions.

    Decision matrix:
    - Trending + High confidence → Directional spreads or naked options
    - Range-bound + High IV → Short strangle / Iron condor
    - Volatile → Short straddle with hedges
    - Quiet + Low IV → Long straddle/strangle (expect breakout)
    """
    if not chain:
        return None

    atm_strike = _find_atm_strike(spot, chain)
    iv_level = _avg_iv(chain, spot)

    # High IV environments → sell premium
    if vix > 20 or iv_level > 25:
        if regime == MarketRegime.RANGE_BOUND:
            return _build_iron_condor(spot, chain, atm_strike, lot_size)
        if regime == MarketRegime.VOLATILE:
            return _build_short_straddle(spot, chain, atm_strike, lot_size)
        if regime in (MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN):
            if confidence > 0.7:
                if direction == SignalDirection.BULLISH:
                    return _build_bull_call_spread(spot, chain, atm_strike, lot_size)
                return _build_bear_put_spread(spot, chain, atm_strike, lot_size)
            return _build_short_strangle(spot, chain, atm_strike, lot_size)

    # Low IV environments → buy premium (expect expansion)
    if (vix < 14 or iv_level < 15) and regime == MarketRegime.QUIET:
        return _build_long_straddle(spot, chain, atm_strike, lot_size)

    # Trending with confidence → directional
    if regime == MarketRegime.TRENDING_UP and confidence > 0.6 and direction == SignalDirection.BULLISH:
        return _build_bull_call_spread(spot, chain, atm_strike, lot_size)
    if regime == MarketRegime.TRENDING_DOWN and confidence > 0.6 and direction == SignalDirection.BEARISH:
        return _build_bear_put_spread(spot, chain, atm_strike, lot_size)

    # Default: iron condor for range-bound or unclear
    if regime in (MarketRegime.RANGE_BOUND, MarketRegime.UNKNOWN):
        return _build_iron_condor(spot, chain, atm_strike, lot_size)

    # Directional plays based on signal
    if direction == SignalDirection.BULLISH:
        return _build_bull_call_spread(spot, chain, atm_strike, lot_size)
    if direction == SignalDirection.BEARISH:
        return _build_bear_put_spread(spot, chain, atm_strike, lot_size)

    return _build_iron_condor(spot, chain, atm_strike, lot_size)


def _find_atm_strike(spot: float, chain: list[OptionChainRow]) -> float:
    return min(chain, key=lambda r: abs(r.strike - spot)).strike


def _avg_iv(chain: list[OptionChainRow], spot: float) -> float:
    atm_rows = sorted(chain, key=lambda r: abs(r.strike - spot))[:5]
    ivs = [r.ce_iv for r in atm_rows if r.ce_iv > 0] + [r.pe_iv for r in atm_rows if r.pe_iv > 0]
    return sum(ivs) / len(ivs) if ivs else 15.0


def _get_row(chain: list[OptionChainRow], strike: float) -> OptionChainRow | None:
    for r in chain:
        if r.strike == strike:
            return r
    return None


def _nearest_strike(chain: list[OptionChainRow], target: float) -> float:
    return min(chain, key=lambda r: abs(r.strike - target)).strike


def _compute_payoff(legs: list[StrategyLeg], spot_range: list[float], lot_size: int) -> list[PayoffPoint]:
    payoff: list[PayoffPoint] = []
    for spot in spot_range:
        pnl = 0.0
        for leg in legs:
            multiplier = lot_size * leg.lots
            intrinsic = max(spot - leg.strike, 0) if leg.option_type == "CE" else max(leg.strike - spot, 0)

            if leg.side == "BUY":
                pnl += (intrinsic - leg.premium) * multiplier
            else:
                pnl += (leg.premium - intrinsic) * multiplier
        payoff.append(PayoffPoint(spot=round(spot, 2), pnl=round(pnl, 2)))
    return payoff


def _spot_range(spot: float, width_pct: float = 5.0, steps: int = 50) -> list[float]:
    lower = spot * (1 - width_pct / 100)
    upper = spot * (1 + width_pct / 100)
    step = (upper - lower) / steps
    return [lower + i * step for i in range(steps + 1)]


def _aggregate_greeks(legs: list[StrategyLeg], lot_size: int) -> Greeks:
    d, g, t, v = 0.0, 0.0, 0.0, 0.0
    for leg in legs:
        sign = 1 if leg.side == "BUY" else -1
        mult = lot_size * leg.lots * sign
        d += leg.greeks.delta * mult
        g += leg.greeks.gamma * mult
        t += leg.greeks.theta * mult
        v += leg.greeks.vega * mult
    return Greeks(delta=round(d, 4), gamma=round(g, 6), theta=round(t, 4), vega=round(v, 4))


def _build_bull_call_spread(
    spot: float, chain: list[OptionChainRow], atm: float, lot_size: int
) -> OptionStrategy:
    buy_strike = atm
    sell_strike = _nearest_strike(chain, atm + atm * 0.02)
    buy_row = _get_row(chain, buy_strike)
    sell_row = _get_row(chain, sell_strike)

    buy_premium = buy_row.ce_ltp if buy_row else 0
    sell_premium = sell_row.ce_ltp if sell_row else 0
    buy_greeks = buy_row.ce_greeks if buy_row else Greeks()
    sell_greeks = sell_row.ce_greeks if sell_row else Greeks()

    legs = [
        StrategyLeg(strike=buy_strike, option_type="CE", side="BUY", premium=buy_premium, greeks=buy_greeks),
        StrategyLeg(strike=sell_strike, option_type="CE", side="SELL", premium=sell_premium, greeks=sell_greeks),
    ]

    net_premium = buy_premium - sell_premium
    max_profit = (sell_strike - buy_strike - net_premium) * lot_size
    max_loss = net_premium * lot_size
    breakeven = [buy_strike + net_premium]

    return OptionStrategy(
        strategy_type=OptionStrategyType.BULL_CALL_SPREAD,
        legs=legs,
        net_premium=round(net_premium, 2),
        max_profit=round(max_profit, 2),
        max_loss=round(max_loss, 2),
        breakeven=[round(b, 2) for b in breakeven],
        net_greeks=_aggregate_greeks(legs, lot_size),
        confidence=0.0,
        reason="Bullish trend with limited risk via spread",
        payoff=_compute_payoff(legs, _spot_range(spot), lot_size),
    )


def _build_bear_put_spread(
    spot: float, chain: list[OptionChainRow], atm: float, lot_size: int
) -> OptionStrategy:
    buy_strike = atm
    sell_strike = _nearest_strike(chain, atm - atm * 0.02)
    buy_row = _get_row(chain, buy_strike)
    sell_row = _get_row(chain, sell_strike)

    buy_premium = buy_row.pe_ltp if buy_row else 0
    sell_premium = sell_row.pe_ltp if sell_row else 0
    buy_greeks = buy_row.pe_greeks if buy_row else Greeks()
    sell_greeks = sell_row.pe_greeks if sell_row else Greeks()

    legs = [
        StrategyLeg(strike=buy_strike, option_type="PE", side="BUY", premium=buy_premium, greeks=buy_greeks),
        StrategyLeg(strike=sell_strike, option_type="PE", side="SELL", premium=sell_premium, greeks=sell_greeks),
    ]

    net_premium = buy_premium - sell_premium
    max_profit = (buy_strike - sell_strike - net_premium) * lot_size
    max_loss = net_premium * lot_size
    breakeven = [buy_strike - net_premium]

    return OptionStrategy(
        strategy_type=OptionStrategyType.BEAR_PUT_SPREAD,
        legs=legs,
        net_premium=round(net_premium, 2),
        max_profit=round(max_profit, 2),
        max_loss=round(max_loss, 2),
        breakeven=[round(b, 2) for b in breakeven],
        net_greeks=_aggregate_greeks(legs, lot_size),
        confidence=0.0,
        reason="Bearish trend with limited risk via spread",
        payoff=_compute_payoff(legs, _spot_range(spot), lot_size),
    )


def _build_short_straddle(
    spot: float, chain: list[OptionChainRow], atm: float, lot_size: int
) -> OptionStrategy:
    row = _get_row(chain, atm)
    ce_prem = row.ce_ltp if row else 0
    pe_prem = row.pe_ltp if row else 0
    ce_greeks = row.ce_greeks if row else Greeks()
    pe_greeks = row.pe_greeks if row else Greeks()

    legs = [
        StrategyLeg(strike=atm, option_type="CE", side="SELL", premium=ce_prem, greeks=ce_greeks),
        StrategyLeg(strike=atm, option_type="PE", side="SELL", premium=pe_prem, greeks=pe_greeks),
    ]

    total_premium = ce_prem + pe_prem
    max_profit = total_premium * lot_size
    breakeven = [atm - total_premium, atm + total_premium]

    return OptionStrategy(
        strategy_type=OptionStrategyType.SHORT_STRADDLE,
        legs=legs,
        net_premium=round(total_premium, 2),
        max_profit=round(max_profit, 2),
        max_loss=round(max_profit * 5, 2),  # approximate
        breakeven=[round(b, 2) for b in breakeven],
        net_greeks=_aggregate_greeks(legs, lot_size),
        confidence=0.0,
        reason="High IV environment — selling premium at ATM",
        payoff=_compute_payoff(legs, _spot_range(spot), lot_size),
    )


def _build_short_strangle(
    spot: float, chain: list[OptionChainRow], atm: float, lot_size: int
) -> OptionStrategy:
    ce_strike = _nearest_strike(chain, atm + atm * 0.02)
    pe_strike = _nearest_strike(chain, atm - atm * 0.02)
    ce_row = _get_row(chain, ce_strike)
    pe_row = _get_row(chain, pe_strike)

    ce_prem = ce_row.ce_ltp if ce_row else 0
    pe_prem = pe_row.pe_ltp if pe_row else 0
    ce_greeks = ce_row.ce_greeks if ce_row else Greeks()
    pe_greeks = pe_row.pe_greeks if pe_row else Greeks()

    legs = [
        StrategyLeg(strike=ce_strike, option_type="CE", side="SELL", premium=ce_prem, greeks=ce_greeks),
        StrategyLeg(strike=pe_strike, option_type="PE", side="SELL", premium=pe_prem, greeks=pe_greeks),
    ]

    total_premium = ce_prem + pe_prem
    max_profit = total_premium * lot_size
    breakeven = [pe_strike - total_premium, ce_strike + total_premium]

    return OptionStrategy(
        strategy_type=OptionStrategyType.SHORT_STRANGLE,
        legs=legs,
        net_premium=round(total_premium, 2),
        max_profit=round(max_profit, 2),
        max_loss=round(max_profit * 5, 2),
        breakeven=[round(b, 2) for b in breakeven],
        net_greeks=_aggregate_greeks(legs, lot_size),
        confidence=0.0,
        reason="High IV, range-bound — selling OTM premium",
        payoff=_compute_payoff(legs, _spot_range(spot), lot_size),
    )


def _build_long_straddle(
    spot: float, chain: list[OptionChainRow], atm: float, lot_size: int
) -> OptionStrategy:
    row = _get_row(chain, atm)
    ce_prem = row.ce_ltp if row else 0
    pe_prem = row.pe_ltp if row else 0
    ce_greeks = row.ce_greeks if row else Greeks()
    pe_greeks = row.pe_greeks if row else Greeks()

    legs = [
        StrategyLeg(strike=atm, option_type="CE", side="BUY", premium=ce_prem, greeks=ce_greeks),
        StrategyLeg(strike=atm, option_type="PE", side="BUY", premium=pe_prem, greeks=pe_greeks),
    ]

    total_premium = ce_prem + pe_prem
    max_loss = total_premium * lot_size
    breakeven = [atm - total_premium, atm + total_premium]

    return OptionStrategy(
        strategy_type=OptionStrategyType.LONG_STRADDLE,
        legs=legs,
        net_premium=round(-total_premium, 2),
        max_profit=round(max_loss * 5, 2),  # unlimited, but approximate
        max_loss=round(max_loss, 2),
        breakeven=[round(b, 2) for b in breakeven],
        net_greeks=_aggregate_greeks(legs, lot_size),
        confidence=0.0,
        reason="Low IV, quiet market — expecting volatility expansion",
        payoff=_compute_payoff(legs, _spot_range(spot), lot_size),
    )


def _build_iron_condor(
    spot: float, chain: list[OptionChainRow], atm: float, lot_size: int
) -> OptionStrategy:
    sell_ce = _nearest_strike(chain, atm + atm * 0.015)
    buy_ce = _nearest_strike(chain, atm + atm * 0.03)
    sell_pe = _nearest_strike(chain, atm - atm * 0.015)
    buy_pe = _nearest_strike(chain, atm - atm * 0.03)

    sell_ce_row = _get_row(chain, sell_ce)
    buy_ce_row = _get_row(chain, buy_ce)
    sell_pe_row = _get_row(chain, sell_pe)
    buy_pe_row = _get_row(chain, buy_pe)

    legs = [
        StrategyLeg(
            strike=sell_ce, option_type="CE", side="SELL",
            premium=sell_ce_row.ce_ltp if sell_ce_row else 0,
            greeks=sell_ce_row.ce_greeks if sell_ce_row else Greeks(),
        ),
        StrategyLeg(
            strike=buy_ce, option_type="CE", side="BUY",
            premium=buy_ce_row.ce_ltp if buy_ce_row else 0,
            greeks=buy_ce_row.ce_greeks if buy_ce_row else Greeks(),
        ),
        StrategyLeg(
            strike=sell_pe, option_type="PE", side="SELL",
            premium=sell_pe_row.pe_ltp if sell_pe_row else 0,
            greeks=sell_pe_row.pe_greeks if sell_pe_row else Greeks(),
        ),
        StrategyLeg(
            strike=buy_pe, option_type="PE", side="BUY",
            premium=buy_pe_row.pe_ltp if buy_pe_row else 0,
            greeks=buy_pe_row.pe_greeks if buy_pe_row else Greeks(),
        ),
    ]

    credit = (
        (sell_ce_row.ce_ltp if sell_ce_row else 0)
        - (buy_ce_row.ce_ltp if buy_ce_row else 0)
        + (sell_pe_row.pe_ltp if sell_pe_row else 0)
        - (buy_pe_row.pe_ltp if buy_pe_row else 0)
    )
    width = max(buy_ce - sell_ce, sell_pe - buy_pe)
    max_profit = credit * lot_size
    max_loss = (width - credit) * lot_size
    breakeven = [sell_pe - credit, sell_ce + credit]

    return OptionStrategy(
        strategy_type=OptionStrategyType.IRON_CONDOR,
        legs=legs,
        net_premium=round(credit, 2),
        max_profit=round(max_profit, 2),
        max_loss=round(max_loss, 2),
        breakeven=[round(b, 2) for b in breakeven],
        net_greeks=_aggregate_greeks(legs, lot_size),
        confidence=0.0,
        reason="Range-bound market — selling premium with defined risk",
        payoff=_compute_payoff(legs, _spot_range(spot), lot_size),
    )
