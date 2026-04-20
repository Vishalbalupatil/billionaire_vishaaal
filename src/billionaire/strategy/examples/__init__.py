from billionaire.strategy.examples.banknifty_reversal_scalp import BankNiftyReversalScalp
from billionaire.strategy.examples.equity_intraday_breakout import EquityIntradayBreakout
from billionaire.strategy.examples.futures_trend_follow import FuturesTrendFollow
from billionaire.strategy.examples.nifty_momentum_breakout import NiftyMomentumBreakout
from billionaire.strategy.examples.options_premium_momentum import OptionsPremiumMomentum

EXAMPLE_STRATEGIES = [
    NiftyMomentumBreakout,
    BankNiftyReversalScalp,
    EquityIntradayBreakout,
    OptionsPremiumMomentum,
    FuturesTrendFollow,
]

__all__ = [
    "BankNiftyReversalScalp",
    "EXAMPLE_STRATEGIES",
    "EquityIntradayBreakout",
    "FuturesTrendFollow",
    "NiftyMomentumBreakout",
    "OptionsPremiumMomentum",
]
