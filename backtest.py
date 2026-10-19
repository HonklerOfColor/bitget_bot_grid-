#!/usr/bin/env python3
"""Backtest auf historischen Bitget-1h-Kerzen, mit Maker/Taker-Fees und Funding-Abschlag."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from bitget_client import BitgetClient
from gridbot.backtest_engine import run_backtest, run_portfolio
from gridbot.candles import parse_candle, sort_unique
from gridbot.params import params_from_config, parse_symbols
from gridbot.settings import load_user_config
from gridbot.specs import FALLBACK_SPECS, ContractSpec

REPORT_PATH = Path("backtest/latest_report.json")
DATA_DIR = Path("data")


def fetch(client: BitgetClient, symbol: str, days: int) -> list:
    end = int(time.time() * 1000)
    start = end - days * 86_400_000
    cache = DATA_DIR / f"{symbol}_1H_{days}d.json"
    if cache.exists() and time.time() - cache.stat().st_mtime < 12 * 3600:
        rows = json.loads(cache.read_text(encoding="utf-8"))
    else:
        rows = client.get_history_candles(symbol, "1H", start, end)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(rows), encoding="utf-8")
    candles = sort_unique(parse_candle(row) for row in rows if int(row[0]) >= start)
    return candles


def spec_for(client: BitgetClient, symbol: str) -> ContractSpec:
    row = client.get_contract(symbol)
    if row:
        return ContractSpec.from_bitget(row)
    if symbol not in FALLBACK_SPECS:
        raise SystemExit(f"kein Kontrakt für {symbol}")
    return FALLBACK_SPECS[symbol]


def _stamp(ts: int) -> str:
    if not ts:
        return "-"
    return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def print_result(title: str, result: dict) -> None:
    exits = result.get("exits") or {}
    print(f"\n{title}")
    print(f"  Zeitraum:        {_stamp(result['from_ts'])} bis {_stamp(result['to_ts'])} ({result['bars']} Stunden)")
    print(f"  Start / Ende:    {result['start_equity']:.2f} → {result['end_equity']:.2f} USDT")
    print(f"  Netto:           {result['net']:+.2f} USDT")
    print(f"  davon realisiert {result['realized']:+.2f}, offen {result['unrealized']:+.2f}")
    print(f"  Fees:            {result['fees']:.2f} (Maker {result['maker_fees']:.2f} / Taker {result['taker_fees']:.2f})")
    print(f"  Funding-Abschlag:{result['funding']:.2f}")
    print(f"  Netto ohne Funding: {result['net_without_funding']:+.2f}")
    print(f"  Max Drawdown:    {result['max_drawdown_pct']:.2f}%")
    print(f"  Grids:           {result['grids_started']}  Maker-Fills: {result['maker_fills']}  Round-Trips: {result['round_trips']} (davon plus {result['round_trip_wins']})")
    print(f"  Ausstiege:       {exits or '-'}")
    if result.get("open_symbol"):
        print(f"  Offen am Ende:   {result['open_symbol']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Grid-Backtest auf Bitget-Klines")
    parser.add_argument("--days", type=int, default=120)
    parser.add_argument("--equity", type=float, default=50.0)
    parser.add_argument("--symbols", default="", help="Komma-Liste, leer = config/Default")
    args = parser.parse_args()
    cfg = load_user_config()
    params = params_from_config(cfg)
    if args.symbols:
        symbols = [item.strip().upper() for item in args.symbols.split(",") if item.strip()]
        leverage = {symbol: min(params.leverage, params.max_leverage) for symbol in symbols}
    else:
        parsed = parse_symbols(cfg, params)
        symbols = [item.symbol for item in parsed]
        leverage = {item.symbol: item.leverage for item in parsed}
    client = BitgetClient(product_type=params.product_type)
    candles = {}
    specs = {}
    for symbol in symbols:
        print(f"Lade {symbol} …")
        specs[symbol] = spec_for(client, symbol)
        candles[symbol] = fetch(client, symbol, args.days)
        print(f"  {len(candles[symbol])} Kerzen, minQty={specs[symbol].min_qty} minUSDT={specs[symbol].min_notional}")
    per_symbol = {}
    for symbol in symbols:
        per_symbol[symbol] = run_backtest(candles[symbol], specs[symbol], params, args.equity, leverage[symbol])
        print_result(symbol, per_symbol[symbol])
    portfolio = run_portfolio(candles, specs, leverage, params, args.equity)
    print_result("Portfolio (ein Grid zur Zeit, gemeinsames Kapital)", portfolio)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "days": args.days,
        "equity": args.equity,
        "assumptions": {
            "maker_fee": params.maker_fee,
            "taker_fee": params.taker_fee,
            "fee_spacing_mult": params.fee_spacing_mult,
            "min_spacing_pct": params.min_spacing_pct,
            "funding_rate_8h": params.funding_rate_8h,
            "funding_note": "pauschal auf |Netto-Position|, nicht die historischen Funding-Raten",
            "emergency_exit": "Taker plus Slippage, kein optimistischer Maker-Fill",
            "leverage": leverage,
            "max_inventory_levels": params.max_inventory_levels,
            "hard_stop_pct": params.hard_stop_pct,
            "daily_loss_pct": params.daily_loss_pct,
        },
        "symbols": per_symbol,
        "portfolio": portfolio,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nReport: {REPORT_PATH}")


if __name__ == "__main__":
    main()
