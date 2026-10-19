#!/usr/bin/env python3
"""Universum-Backtest ohne BTC, ETH und BNB.

Protokoll, vor dem Lauf festgelegt:
- Fenster 120 Tage, Split nach 80 Tagen (In-Sample) / 40 Tagen (Out-of-Sample).
- Pro Coin fünf Ein-Faktor-Varianten. Die Wahl fällt nur auf dem In-Sample,
  und nur wenn mindestens 4 Grids liefen und der Drawdown höchstens 15 % war.
- Empfehlung nur, wenn In-Sample und Out-of-Sample nach Fees positiv sind
  und Out-of-Sample mindestens 2 Grids hatte.
- Höchstens 8 Coins, sortiert nach Out-of-Sample-Netto.
"""

from __future__ import annotations

import json
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from bitget_client import BitgetClient
from gridbot.backtest_engine import run_backtest, run_portfolio
from gridbot.candles import parse_candle, sort_unique
from gridbot.params import GridParams
from gridbot.specs import ContractSpec

EQUITY = 50.0
LEVERAGE = 2
DAYS = 120
IS_DAYS = 80
DATA_DIR = Path("data/universe")
JSON_PATH = Path("backtest/universe_report.json")
MD_PATH = Path("backtest/universe_report.md")

EXCLUDED = {"BTCUSDT", "ETHUSDT", "BNBUSDT"}
STABLES = {
    "USDCUSDT",
    "DAIUSDT",
    "TUSDUSDT",
    "FDUSDUSDT",
    "USDEUSDT",
    "EURUSDT",
    "USD1USDT",
}

# Ein Faktor weicht vom Default ab. Kein kombinatorisches Gitter.
VARIANTS = [
    {"name": "default", "grid_levels": 6, "fee_spacing_mult": 3.0, "adx_max_1h": 22.0, "adx_max_4h": 25.0},
    {"name": "levels_4", "grid_levels": 4, "fee_spacing_mult": 3.0, "adx_max_1h": 22.0, "adx_max_4h": 25.0},
    {"name": "levels_8", "grid_levels": 8, "fee_spacing_mult": 3.0, "adx_max_1h": 22.0, "adx_max_4h": 25.0},
    {"name": "spacing_4_5", "grid_levels": 6, "fee_spacing_mult": 4.5, "adx_max_1h": 22.0, "adx_max_4h": 25.0},
    {"name": "adx_18", "grid_levels": 6, "fee_spacing_mult": 3.0, "adx_max_1h": 18.0, "adx_max_4h": 21.0},
    {"name": "adx_28", "grid_levels": 6, "fee_spacing_mult": 3.0, "adx_max_1h": 28.0, "adx_max_4h": 32.0},
]

MIN_IS_GRIDS = 4
MAX_IS_DD = 15.0
MIN_OOS_GRIDS = 2
MAX_RECOMMENDED = 8
MIN_ORDER_USDT = 25.0  # ein Level muss ins 50%-Margin-Budget bei 2× passen
MIN_QUOTE_VOLUME = 1_000_000.0
UNIVERSE_CAP = 60


def _stamp(ts: int) -> str:
    if not ts:
        return "-"
    return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def _params(spec: dict) -> GridParams:
    base = GridParams()
    return replace(
        base,
        grid_levels=int(spec["grid_levels"]),
        fee_spacing_mult=float(spec["fee_spacing_mult"]),
        adx_max_1h=float(spec["adx_max_1h"]),
        adx_max_4h=float(spec["adx_max_4h"]),
        leverage=LEVERAGE,
    )


def _metrics(result: dict) -> dict:
    factor = result["profit_factor"]
    return {
        "net": round(result["net"], 4),
        "fees": round(result["fees"], 4),
        "funding": round(result["funding"], 4),
        "max_drawdown_pct": round(result["max_drawdown_pct"], 2),
        "grids_started": result["grids_started"],
        "breakout_exits": result["breakout_exits"],
        "regime_exits": int(result["exits"].get("regime", 0)),
        "hard_stop_exits": int(result["exits"].get("hard_stop", 0)),
        "profit_factor": None if factor is None else round(factor, 3),
        "closed_grid_wins": result["closed_grid_wins"],
        "closed_grid_losses": result["closed_grid_losses"],
        "round_trips": result["round_trips"],
        "bars": result["bars"],
        "from_ts": result["from_ts"],
        "to_ts": result["to_ts"],
    }


def _fmt_pf(value) -> str:
    if value is None:
        return "–"
    return f"{value:.2f}"


def _fmt_net(value: float) -> str:
    return f"{value:+.2f}"


def screen_universe(client: BitgetClient) -> list[dict]:
    tickers = client.public_get("/api/v2/mix/market/tickers", {"productType": "USDT-FUTURES"})
    contracts = client.public_get("/api/v2/mix/market/contracts", {"productType": "USDT-FUTURES"})
    by_symbol = {}
    for row in contracts.get("data") or []:
        if str(row.get("symbolType", "perpetual")) not in ("perpetual", ""):
            continue
        status = str(row.get("symbolStatus", "normal")).lower()
        if status not in ("normal", "listed", ""):
            continue
        by_symbol[row["symbol"]] = ContractSpec.from_bitget(row)
    ranked = []
    for row in tickers.get("data") or []:
        symbol = str(row.get("symbol", ""))
        if not symbol.endswith("USDT") or symbol in EXCLUDED or symbol in STABLES:
            continue
        spec = by_symbol.get(symbol)
        if spec is None:
            continue
        try:
            last = float(row.get("lastPr") or 0)
            volume = float(row.get("usdtVolume") or row.get("quoteVolume") or 0)
        except (TypeError, ValueError):
            continue
        if last <= 0 or volume < MIN_QUOTE_VOLUME:
            continue
        min_order = max(spec.min_qty * last, spec.min_notional)
        if min_order > MIN_ORDER_USDT:
            continue
        ranked.append(
            {
                "symbol": symbol,
                "last": last,
                "quote_volume_24h": volume,
                "min_qty": spec.min_qty,
                "min_notional": spec.min_notional,
                "min_order_usdt": min_order,
                "spec": spec,
            }
        )
    ranked.sort(key=lambda item: item["quote_volume_24h"], reverse=True)
    return ranked[:UNIVERSE_CAP]


def load_candles(client: BitgetClient, symbol: str, start_ms: int, end_ms: int) -> list:
    cache = DATA_DIR / f"{symbol}_1H.json"
    rows: list
    if cache.exists() and time.time() - cache.stat().st_mtime < 18 * 3600:
        rows = json.loads(cache.read_text(encoding="utf-8"))
    else:
        rows = client.get_history_candles(symbol, "1H", start_ms, end_ms)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(rows), encoding="utf-8")
    candles = sort_unique(parse_candle(row) for row in rows if start_ms <= int(row[0]) <= end_ms)
    return candles


def choose_variant(is_runs: list[dict]) -> dict:
    eligible = [
        item
        for item in is_runs
        if item["metrics"]["grids_started"] >= MIN_IS_GRIDS and item["metrics"]["max_drawdown_pct"] <= MAX_IS_DD
    ]
    pool = eligible or is_runs
    default = next(item for item in is_runs if item["name"] == "default")
    if not eligible:
        return default
    return max(pool, key=lambda item: item["metrics"]["net"])


def _table(rows: list[dict], columns: list[tuple[str, str]]) -> str:
    header = "| " + " | ".join(title for _, title in columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    lines = [header, sep]
    for row in rows:
        lines.append("| " + " | ".join(str(row[key]) for key, _ in columns) + " |")
    return "\n".join(lines)


def write_markdown(report: dict) -> str:
    coins = report["coins"]
    recommended = [item for item in coins if item["recommended"]]
    recommended.sort(
        key=lambda item: min(item["chosen"]["is"]["net"], item["chosen"]["oos"]["net"]),
        reverse=True,
    )
    lines = [
        "# Universum-Backtest ohne BTC, ETH, BNB",
        "",
        f"Erzeugt {report['generated_at']}. Startkapital {EQUITY:.0f} USDT, Hebel {LEVERAGE}×, "
        f"Maker {report['fees']['maker'] * 100:.2f} %, Taker {report['fees']['taker'] * 100:.2f} %, "
        f"Slippage auf Notausstiegen {report['fees']['taker_slippage'] * 10000:.0f} bp, "
        f"Funding-Abschlag {report['fees']['funding_8h'] * 100:.2f} % je 8h auf die Nettoposition.",
        "",
        f"Fenster {_stamp(report['window']['start_ms'])} bis {_stamp(report['window']['end_ms'])}. "
        f"In-Sample bis {_stamp(report['window']['split_ms'])} ({IS_DAYS} Tage), "
        f"danach Out-of-Sample. Die Parameterwahl sieht die letzten 40 Tage nicht.",
        "",
        "## Auswahlregel",
        "",
        "Varianten sind Ein-Faktor-Abweichungen vom Default (6 Levels, Abstand 3× Maker-Round-Trip, ADX 22/25): "
        "4 Levels, 8 Levels, weiter Abstand (4,5×), strenger ADX (18/21), lockerer ADX (28/32).",
        "",
        f"Pro Coin gewinnt auf dem In-Sample die Variante mit dem höchsten Netto, sofern mindestens {MIN_IS_GRIDS} Grids "
        f"liefen und der Drawdown höchstens {MAX_IS_DD:.0f} % war. Sonst bleibt der Default.",
        "",
        f"Empfohlen wird ein Coin nur, wenn In-Sample und Out-of-Sample nach Fees positiv sind und Out-of-Sample "
        f"mindestens {MIN_OOS_GRIDS} Grids hatte. Sortierung nach dem schwächeren der beiden Abschnitte, höchstens {MAX_RECOMMENDED}.",
        "",
        f"Universum: die liquidesten USDT-M-Perps mit 24h-Umsatz ab {MIN_QUOTE_VOLUME:,.0f} USDT, "
        f"deren Mindestorder bei 2× in 25 USDT Margin passt (ein Level ≤ {MIN_ORDER_USDT:.0f} USDT Notional). "
        f"BTC, ETH, BNB und Stablecoin-Paare sind draußen. Geprüft: {report['universe_size']} Coins, "
        f"mit genug Historie: {len(coins)}.",
        "",
        "## Empfehlung für die Config",
        "",
        "Der Bot hat einen Parametersatz für alle Symbole. In `config.example.py` stehen deshalb nur Coins, "
        "die unter dem Default (6 Levels, Abstand 3×, ADX 22/25) in beiden Abschnitten positiv sind. "
        "Per-Coin-Varianten teilt sich der laufende Bot nicht.",
        "",
    ]
    config_rows = []
    by_symbol = {item["symbol"]: item for item in coins}
    for symbol in report.get("config_symbols") or []:
        item = by_symbol[symbol]
        block = item["default"]
        config_rows.append(
            {
                "symbol": symbol,
                "is_net": _fmt_net(block["is"]["net"]),
                "oos_net": _fmt_net(block["oos"]["net"]),
                "full_net": _fmt_net(block["full"]["net"]),
                "dd": f"{block['full']['max_drawdown_pct']:.1f} %",
                "grids": f"{block['is']['grids_started']}/{block['oos']['grids_started']}/{block['full']['grids_started']}",
                "bo": f"{block['is']['breakout_exits']}/{block['oos']['breakout_exits']}/{block['full']['breakout_exits']}",
                "pf": f"{_fmt_pf(block['is']['profit_factor'])} / {_fmt_pf(block['oos']['profit_factor'])}",
            }
        )
    if config_rows:
        lines.append(
            _table(
                config_rows,
                [
                    ("symbol", "Coin"),
                    ("is_net", "IS-Netto"),
                    ("oos_net", "OOS-Netto"),
                    ("full_net", "120T-Netto"),
                    ("dd", "120T-DD"),
                    ("grids", "Grids IS/OOS/120T"),
                    ("bo", "Breakouts IS/OOS/120T"),
                    ("pf", "PF IS/OOS"),
                ],
            )
        )
        lines.append("")
    else:
        lines.append("Unter dem Default ist kein Coin in beiden Abschnitten positiv.")
        lines.append("")
    lines.extend(["## Per-Coin-Variante, beide Abschnitte positiv", ""])
    if not recommended:
        lines.append("Kein Coin ist in beiden Abschnitten positiv. Es gibt keine empfohlene Symbol-Liste.")
        lines.append("")
    if recommended:
        lines.append(
            "Jede Zeile benutzt die Variante, die auf dem In-Sample am besten war. "
            "Das ist nicht die Config des Bots: die Symbole teilen sich dort einen Parametersatz. "
            "Wer nur die Out-of-Sample-Gewinner behält, sieht ein schöneres Bild als die In-Sample-Rangliste."
        )
        lines.append("")
        rec_rows = []
        for item in recommended:
            chosen = item["chosen"]
            rec_rows.append(
                {
                    "symbol": item["symbol"],
                    "variant": chosen["name"],
                    "is_net": _fmt_net(chosen["is"]["net"]),
                    "oos_net": _fmt_net(chosen["oos"]["net"]),
                    "full_net": _fmt_net(chosen["full"]["net"]),
                    "oos_dd": f"{chosen['oos']['max_drawdown_pct']:.1f} %",
                    "full_dd": f"{chosen['full']['max_drawdown_pct']:.1f} %",
                    "grids": f"{chosen['is']['grids_started']}/{chosen['oos']['grids_started']}/{chosen['full']['grids_started']}",
                    "bo": f"{chosen['is']['breakout_exits']}/{chosen['oos']['breakout_exits']}/{chosen['full']['breakout_exits']}",
                    "pf": f"{_fmt_pf(chosen['is']['profit_factor'])} / {_fmt_pf(chosen['oos']['profit_factor'])}",
                }
            )
        lines.append(
            _table(
                rec_rows,
                [
                    ("symbol", "Coin"),
                    ("variant", "Variante"),
                    ("is_net", "IS-Netto"),
                    ("oos_net", "OOS-Netto"),
                    ("full_net", "120T-Netto"),
                    ("oos_dd", "OOS-DD"),
                    ("full_dd", "120T-DD"),
                    ("grids", "Grids IS/OOS/120T"),
                    ("bo", "Breakouts IS/OOS/120T"),
                    ("pf", "PF IS/OOS"),
                ],
            )
        )
    lines.extend(["", "## Portfolio", ""])
    for key, title in (
        (
            "default_is_top_oos",
            "Ehrlich: Default-Parameter, die 8 besten In-Sample-Coins, nur die folgenden 40 Tage, Verlierer bleiben drin",
        ),
        (
            "config_oos",
            "Config-Liste (Default, beide Fenster positiv), nur Out-of-Sample — nach oben verzerrt, Verlierer wurden mit dem OOS-Filter entfernt",
        ),
        (
            "config_full",
            "Dieselbe Config-Liste über die vollen 120 Tage, ebenfalls mit diesem Filter",
        ),
        ("is_top_oos", "Per-Coin-Variante nach In-Sample gewählt, Slot aber mit Default-Parametern, nur Out-of-Sample"),
        ("recommended_oos", "Die 8 Varianten-Überlebenden, Slot mit Default-Parametern, nur Out-of-Sample"),
        ("recommended_full", "Dieselben 8 Namen, Default-Parameter, volle 120 Tage"),
    ):
        block = report["portfolios"].get(key)
        lines.append(f"### {title}")
        lines.append("")
        if not block or not block.get("symbols") or not block.get("metrics"):
            lines.append("Kein Portfolio, weil keine Coins in dieser Gruppe sind.")
            lines.append("")
            continue
        metrics = block["metrics"]
        lines.append(
            f"Parametersatz: {block.get('param_set', 'default')}. "
            f"Reihenfolge im einen Grid-Slot: {', '.join(block['symbols'])}. "
            f"Netto {_fmt_net(metrics['net'])} USDT, Max-DD {metrics['max_drawdown_pct']:.1f} %, "
            f"Grids {metrics['grids_started']}, Breakouts {metrics['breakout_exits']}, "
            f"Profit Factor {_fmt_pf(metrics['profit_factor'])}, Fees {metrics['fees']:.2f}."
        )
        lines.append("")
    lines.extend(
        [
            "Ein Grid zur Zeit, gemeinsames 50-USDT-Kapital, Priorität in der genannten Reihenfolge. "
            "Der erste Block wählt die Coins nur nach In-Sample und lässt die Out-of-Sample-Verlierer drin.",
            "",
            "## Alle geprüften Coins",
            "",
            "Sortiert nach Out-of-Sample-Netto der gewählten Variante. Default-OOS steht daneben, "
            "damit sichtbar ist, ob die Variante out-of-sample etwas geändert hat.",
            "",
        ]
    )
    all_rows = []
    ordered = sorted(coins, key=lambda item: item["chosen"]["oos"]["net"], reverse=True)
    for item in ordered:
        chosen = item["chosen"]
        all_rows.append(
            {
                "symbol": item["symbol"],
                "vol": f"{item['quote_volume_24h'] / 1e6:.0f}M",
                "min": f"{item['min_order_usdt']:.1f}",
                "variant": chosen["name"],
                "is_net": _fmt_net(chosen["is"]["net"]),
                "oos_net": _fmt_net(chosen["oos"]["net"]),
                "def_oos": _fmt_net(item["default"]["oos"]["net"]),
                "dd": f"{chosen['oos']['max_drawdown_pct']:.1f} %",
                "grids": str(chosen["oos"]["grids_started"]),
                "bo": str(chosen["oos"]["breakout_exits"]),
                "pf": _fmt_pf(chosen["oos"]["profit_factor"]),
                "flag": (
                    "Config"
                    if item["symbol"] in set(report.get("config_symbols") or [])
                    else ("Variante" if item["recommended"] else "")
                ),
            }
        )
    lines.append(
        _table(
            all_rows,
            [
                ("symbol", "Coin"),
                ("vol", "24h-Umsatz"),
                ("min", "Min-Order"),
                ("variant", "Wahl"),
                ("is_net", "IS"),
                ("oos_net", "OOS"),
                ("def_oos", "Default-OOS"),
                ("dd", "OOS-DD"),
                ("grids", "OOS-Grids"),
                ("bo", "OOS-Breakouts"),
                ("pf", "OOS-PF"),
                ("flag", "Liste"),
            ],
        )
    )
    lines.extend(
        [
            "",
            "## Was das nicht ist",
            "",
            "24h-Volumen ist der Stand zum Lauf, nicht das historische Volumen. Neue oder sterbende Coins "
            "sind damit falsch gewichtet. Docht-Fills sind für Post-only leicht optimistisch, Notausstiege "
            "zahlen Taker plus 2 bp. Funding ist eine Pauschale. Wer auf dem Out-of-Sample die Verlierer "
            "streichen darf, sieht ein schöneres Portfolio als der, der die Liste vorher festnageln muss.",
            "",
            f"Zu wenig Historie und deshalb nicht gewertet: {', '.join(report['dropped_short_history']) or '—'}.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    client = BitgetClient()
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - DAYS * 86_400_000
    split_ms = start_ms + IS_DAYS * 86_400_000
    print("Screening …")
    screened = screen_universe(client)
    print(f"{len(screened)} Coins nach Volumen und Mindestgröße")
    base_params = GridParams()
    coins = []
    dropped = []
    for item in screened:
        symbol = item["symbol"]
        print(f"Lade {symbol} …", flush=True)
        candles = load_candles(client, symbol, start_ms, end_ms)
        if not candles or candles[-1].ts < split_ms or candles[0].ts > start_ms + 5 * 86_400_000:
            dropped.append(symbol)
            print(f"  zu wenig Historie ({len(candles)} Kerzen)")
            continue
        is_candles = [candle for candle in candles if candle.ts < split_ms]
        oos_index = next((i for i, candle in enumerate(candles) if candle.ts >= split_ms), len(candles) - 1)
        is_runs = []
        for spec in VARIANTS:
            params = _params(spec)
            is_result = run_backtest(is_candles, item["spec"], params, EQUITY, LEVERAGE)
            is_runs.append({"name": spec["name"], "metrics": _metrics(is_result)})
        chosen_is = choose_variant(is_runs)
        chosen_spec = next(spec for spec in VARIANTS if spec["name"] == chosen_is["name"])
        chosen_params = _params(chosen_spec)
        default_params = _params(VARIANTS[0])
        chosen_oos = _metrics(run_backtest(candles, item["spec"], chosen_params, EQUITY, LEVERAGE, start_index=oos_index))
        chosen_full = _metrics(run_backtest(candles, item["spec"], chosen_params, EQUITY, LEVERAGE))
        default_oos = _metrics(run_backtest(candles, item["spec"], default_params, EQUITY, LEVERAGE, start_index=oos_index))
        default_is = next(run["metrics"] for run in is_runs if run["name"] == "default")
        default_full = _metrics(run_backtest(candles, item["spec"], default_params, EQUITY, LEVERAGE))
        recommended = (
            chosen_is["metrics"]["net"] > 0
            and chosen_is["metrics"]["grids_started"] >= MIN_IS_GRIDS
            and chosen_oos["net"] > 0
            and chosen_oos["grids_started"] >= MIN_OOS_GRIDS
        )
        public = {key: value for key, value in item.items() if key != "spec"}
        public.update(
            {
                "candles": len(candles),
                "chosen": {
                    "name": chosen_is["name"],
                    "is": chosen_is["metrics"],
                    "oos": chosen_oos,
                    "full": chosen_full,
                },
                "default": {"is": default_is, "oos": default_oos, "full": default_full},
                "variants_is": is_runs,
                "recommended": recommended,
            }
        )
        coins.append({"_candles": candles, "_spec": item["spec"], **public})
        print(
            f"  {chosen_is['name']} IS {chosen_is['metrics']['net']:+.2f} "
            f"OOS {chosen_oos['net']:+.2f} empfohlen={recommended}"
        )

    recommended = [item for item in coins if item["recommended"]]
    recommended.sort(
        key=lambda item: min(item["chosen"]["is"]["net"], item["chosen"]["oos"]["net"]),
        reverse=True,
    )
    recommended = recommended[:MAX_RECOMMENDED]
    recommended_symbols = {item["symbol"] for item in recommended}

    is_ranked = [
        item
        for item in coins
        if item["chosen"]["is"]["grids_started"] >= MIN_IS_GRIDS and item["chosen"]["is"]["net"] > 0
    ]
    is_ranked.sort(key=lambda item: item["chosen"]["is"]["net"], reverse=True)
    is_top = is_ranked[:MAX_RECOMMENDED]

    def portfolio_block(group: list[dict], start_index_mode: str) -> dict:
        if not group:
            return {"symbols": [], "metrics": None}
        # Gemeinsame Zeitstempel, damit der eine Slot vergleichbar ist.
        stamps: set[int] | None = None
        for item in group:
            own = {candle.ts for candle in item["_candles"]}
            stamps = own if stamps is None else stamps & own
        assert stamps is not None
        series = {}
        specs = {}
        leverage = {}
        ordered = []
        for item in group:
            ordered_candles = [candle for candle in item["_candles"] if candle.ts in stamps]
            if len(ordered_candles) < 200:
                continue
            series[item["symbol"]] = ordered_candles
            specs[item["symbol"]] = item["_spec"]
            leverage[item["symbol"]] = LEVERAGE
            ordered.append(item["symbol"])
        if not ordered:
            return {"symbols": [], "metrics": None}
        # Reihenfolge der Dicts ist die Priorität. group ist bereits sortiert.
        series = {symbol: series[symbol] for symbol in ordered}
        start_index = 0
        if start_index_mode == "oos":
            start_index = next((i for i, candle in enumerate(series[ordered[0]]) if candle.ts >= split_ms), 0)
        params_by_symbol = {}
        # Portfolio-Engine nimmt ein Params-Objekt. Unterschiedliche ADX/Levels pro Coin
        # unterstützt sie nicht. Für das Portfolio gilt der Default, außer alle gewählten
        # Varianten sind identisch — dann diese. Sonst Default und das im Report sagen.
        names = []
        for item in group:
            if item["symbol"] in series:
                names.append(item["chosen"]["name"])
        shared = names[0] if names and len(set(names)) == 1 else "default"
        params = _params(next(spec for spec in VARIANTS if spec["name"] == shared))
        result = run_portfolio(series, specs, leverage, params, EQUITY, start_index=start_index)
        return {
            "symbols": ordered,
            "param_set": shared,
            "note": "ein Parametersatz für alle, weil der Slot eine Config teilt",
            "metrics": _metrics(result),
        }

    portfolios = {
        "is_top_oos": portfolio_block(is_top, "oos"),
        "recommended_oos": portfolio_block(recommended, "oos"),
        "recommended_full": portfolio_block(recommended, "full"),
    }

    public_coins = []
    for item in coins:
        public_coins.append({key: value for key, value in item.items() if not key.startswith("_")})
    for item in public_coins:
        item["recommended"] = item["symbol"] in recommended_symbols

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window": {"start_ms": start_ms, "split_ms": split_ms, "end_ms": end_ms},
        "fees": {
            "maker": base_params.maker_fee,
            "taker": base_params.taker_fee,
            "taker_slippage": base_params.taker_slippage_pct,
            "funding_8h": base_params.funding_rate_8h,
            "spacing_mult_default": base_params.fee_spacing_mult,
        },
        "equity": EQUITY,
        "leverage": LEVERAGE,
        "universe_size": len(screened),
        "dropped_short_history": dropped,
        "selection": {
            "min_is_grids": MIN_IS_GRIDS,
            "max_is_dd_pct": MAX_IS_DD,
            "min_oos_grids": MIN_OOS_GRIDS,
            "variants": [item["name"] for item in VARIANTS],
        },
        "recommended_symbols": [item["symbol"] for item in recommended],
        "coins": public_coins,
        "portfolios": portfolios,
    }
    text = write_markdown(report)
    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    MD_PATH.write_text(text, encoding="utf-8")
    print(text)
    print(f"\n{JSON_PATH}\n{MD_PATH}")


if __name__ == "__main__":
    main()
