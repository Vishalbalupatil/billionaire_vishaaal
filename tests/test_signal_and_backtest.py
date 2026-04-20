from billionaire.backtest import BacktestEngine
from billionaire.models import Exchange, Instrument, Segment
from billionaire.strategy.examples import EXAMPLE_STRATEGIES
from billionaire.strategy.signal_engine import SignalEngine


def test_backtest_runs_end_to_end():
    engine = SignalEngine([cls() for cls in EXAMPLE_STRATEGIES])
    bt = BacktestEngine(engine, warmup_bars=60, confidence_threshold=0.4)
    ohlcv = bt.synthetic_ohlcv(n=400, seed=11)
    inst = Instrument(
        instrument_token=999,
        tradingsymbol="SIM",
        exchange=Exchange.NSE,
        segment=Segment.INDEX,
    )
    result = bt.run(instrument=inst, timeframe="5m", ohlcv=ohlcv)
    assert result.metrics is not None
    assert result.metrics.trades >= 0  # pipeline ran


def test_options_engine_insights():
    from billionaire.strategy.options_engine import OptionRow, OptionsEngine

    rows = [
        OptionRow(strike=17800, ce_oi=1000, pe_oi=500, ce_ltp=120, pe_ltp=40),
        OptionRow(strike=18000, ce_oi=2000, pe_oi=1500, ce_ltp=60, pe_ltp=70),
        OptionRow(strike=18200, ce_oi=500, pe_oi=2500, ce_ltp=25, pe_ltp=150),
    ]
    ins = OptionsEngine().insights(spot=18000, rows=rows)
    assert ins.atm_strike == 18000
    assert 0 < ins.pcr_oi < 10
    assert ins.call_wall in {18000, 17800, 18200}
