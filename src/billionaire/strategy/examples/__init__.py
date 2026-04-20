from billionaire.strategy.examples.equity_intraday_breakout import EquityIntradayBreakout
from billionaire.strategy.examples.nifty_momentum_breakout import NiftyMomentumBreakout
from billionaire.strategy.examples.options_premium_momentum import OptionsPremiumMomentum

# Scope: Nifty 50 only (index + futures + options + 50 constituents).
# Bank Nifty / futures-scalp / options-selling variants intentionally removed.
EXAMPLE_STRATEGIES = [
    NiftyMomentumBreakout,
    EquityIntradayBreakout,
    OptionsPremiumMomentum,
]

__all__ = [
    "EXAMPLE_STRATEGIES",
    "EquityIntradayBreakout",
    "NiftyMomentumBreakout",
    "OptionsPremiumMomentum",
]
