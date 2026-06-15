"""CLI entry point for the AI Trader platform."""

from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Trader — Nifty 50 Options Platform")
    sub = parser.add_subparsers(dest="command")

    # Server
    serve_parser = sub.add_parser("serve", help="Start the API server")
    serve_parser.add_argument("--host", default="0.0.0.0")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.add_argument("--reload", action="store_true")

    # Train
    sub.add_parser("train", help="Train the AI model on historical data")

    # Status
    sub.add_parser("status", help="Show current system status")

    args = parser.parse_args()

    if args.command == "serve":
        import uvicorn
        uvicorn.run(
            "ai_trader.app:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
        )
    elif args.command == "train":
        _train()
    elif args.command == "status":
        _status()
    else:
        parser.print_help()


def _train() -> None:
    """Train the ensemble model on historical data."""
    import numpy as np
    import pandas as pd
    from rich.console import Console

    from ai_trader.ai.features import build_features
    from ai_trader.ai.model import EnsembleModel

    console = Console()
    console.print("[bold]Training AI ensemble model...[/bold]")

    # Generate synthetic training data for demonstration
    np.random.seed(42)
    n = 1000
    dates = pd.date_range("2024-01-01", periods=n, freq="5min")
    base_price = 22000
    prices = base_price + np.cumsum(np.random.randn(n) * 10)

    df = pd.DataFrame({
        "open": prices + np.random.randn(n) * 5,
        "high": prices + abs(np.random.randn(n) * 15),
        "low": prices - abs(np.random.randn(n) * 15),
        "close": prices,
        "volume": np.random.randint(1000, 50000, n),
        "ts": dates,
    })

    features_df = build_features(df)
    features_df = features_df.dropna()

    # Labels: next-period return direction
    features_df["fwd_return"] = features_df["close"].shift(-5).pct_change(5)
    features_df = features_df.dropna()

    labels = pd.Series(0, index=features_df.index)
    labels[features_df["fwd_return"] > 0.001] = 1
    labels[features_df["fwd_return"] < -0.001] = -1

    model = EnsembleModel()
    metrics = model.train(features_df, labels, features_df["fwd_return"])

    console.print("[green]Training complete![/green]")
    for k, v in metrics.items():
        console.print(f"  {k}: {v:.4f}")


def _status() -> None:
    """Print system status."""
    from rich.console import Console
    from rich.table import Table

    from ai_trader.config import get_settings
    from ai_trader.execution.scheduler import session_info

    console = Console()
    settings = get_settings()
    info = session_info()

    table = Table(title="AI Trader Status")
    table.add_column("Parameter", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Trading Mode", settings.trading_mode.value)
    table.add_row("Capital", f"₹{settings.max_capital:,.0f}")
    table.add_row("Risk/Trade", f"{settings.risk_per_trade_pct}%")
    table.add_row("Max Daily Loss", f"{settings.max_daily_loss_pct}%")
    table.add_row("IST Time", info["ist_time"])
    table.add_row("Market Open", str(info["market_open"]))
    table.add_row("Expiry Day", str(info["expiry_day"]))
    table.add_row("Minutes to Close", str(info["minutes_to_close"]))
    table.add_row("Kite API Key", "configured" if settings.kite_api_key else "NOT SET")

    console.print(table)


if __name__ == "__main__":
    main()
