"""Backtest auf geschlossenen Kerzen. Dieselbe Grid-Engine wie Paper und Live."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from gridbot.candles import Candle
from gridbot.engine import ActiveGrid, build_plan
from gridbot.params import GridParams
from gridbot.regime import assess
from gridbot.risk import RiskGuard
from gridbot.specs import ContractSpec


def _day(ts: int) -> str:
    return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).date().isoformat()


def run_backtest(
    candles: list[Candle],
    spec: ContractSpec,
    params: GridParams,
    equity0: float,
    leverage: int | None = None,
) -> dict:
    """Ein Symbol, eigenes Startkapital. Notausstiege zahlen Taker plus Slippage."""
    lev = leverage if leverage is not None else params.leverage
    return _run({spec.symbol: candles}, {spec.symbol: spec}, {spec.symbol: lev}, params, equity0, portfolio=False)


def run_portfolio(
    candles_by_symbol: dict[str, list[Candle]],
    specs: dict[str, ContractSpec],
    leverage: dict[str, int],
    params: GridParams,
    equity0: float,
) -> dict:
    return _run(candles_by_symbol, specs, leverage, params, equity0, portfolio=True)


def _align(candles_by_symbol: dict[str, list[Candle]]) -> dict[str, list[Candle]]:
    common: set[int] | None = None
    for series in candles_by_symbol.values():
        stamps = {candle.ts for candle in series}
        common = stamps if common is None else common & stamps
    assert common is not None
    aligned = {
        symbol: [candle for candle in series if candle.ts in common]
        for symbol, series in candles_by_symbol.items()
    }
    return aligned


def _run(
    candles_by_symbol: dict[str, list[Candle]],
    specs: dict[str, ContractSpec],
    leverage: dict[str, int],
    params: GridParams,
    equity0: float,
    portfolio: bool,
) -> dict:
    symbols = list(candles_by_symbol)
    series = _align(candles_by_symbol) if portfolio else candles_by_symbol
    length = min(len(series[symbol]) for symbol in symbols)
    if portfolio:
        for symbol in symbols:
            series[symbol] = series[symbol][:length]

    grid: ActiveGrid | None = None
    active = ""
    banked = 0.0
    banked_realized = 0.0
    banked_fees = 0.0
    banked_funding = 0.0
    taker_fees = 0.0
    trips = 0
    trip_wins = 0
    peak = equity0
    max_dd = 0.0
    risk = RiskGuard()
    cooldown = {symbol: 0 for symbol in symbols}
    counts: Counter[str] = Counter()
    grids_started = 0
    exit_reasons: Counter[str] = Counter()
    maker_fills = 0

    def equity_at(mark_by_symbol: dict[str, float]) -> float:
        if grid is None:
            return equity0 + banked
        mark = mark_by_symbol.get(grid.symbol, 0.0)
        return equity0 + banked + grid.net_pnl(mark)

    def bank(reason: str, mark: float) -> None:
        nonlocal grid, active, banked, banked_realized, banked_fees, banked_funding, taker_fees
        assert grid is not None
        before_fees = grid.fees
        grid.flatten(mark, params.taker_slippage_pct, params.taker_fee)
        taker_fees += grid.fees - before_fees
        banked += grid.net_pnl(mark)
        banked_realized += grid.realized
        banked_fees += grid.fees
        banked_funding += grid.funding
        exit_reasons[reason] += 1
        cooldown[grid.symbol] = i + params.cooldown_bars
        grid = None
        active = ""

    for i in range(length):
        marks = {symbol: series[symbol][i].close for symbol in symbols}
        now = series[symbols[0]][i]
        equity = equity_at(marks)
        risk.on_day(_day(now.ts), equity)
        stopped = False

        if grid is not None:
            candle = series[grid.symbol][i]
            if candle.ts % (8 * 3_600_000) == 0:
                grid.charge_funding(candle.close, params.funding_rate_8h)
            breakout = grid.outside(candle.close, params.breakout_buffer_pct)
            for order in list(grid.orders.values()):
                if not (candle.low <= order.price <= candle.high):
                    continue
                if breakout and order.purpose != "open":
                    continue
                before = grid.realized
                grid.apply_fill(order, order.price, order.size, params.maker_fee)
                maker_fills += 1
                if order.purpose != "open" and grid.realized != before:
                    trips += 1
                    if grid.realized > before:
                        trip_wins += 1
            if breakout:
                bank("breakout", candle.close)
                stopped = True
            elif grid is not None and grid.net_pnl(candle.close) <= -grid.hard_stop_usdt:
                bank("hard_stop", candle.close)
                stopped = True
            elif grid is not None:
                window = series[grid.symbol][max(0, i - 249): i + 1]
                if not assess(window, None, params).ranging:
                    bank("regime", candle.close)
                    stopped = True
                else:
                    eq = equity_at(marks)
                    grid.sync_orders(candle.close, eq, specs[grid.symbol], params)

        equity = equity_at(marks)
        if risk.check_daily(equity, params.daily_loss_pct) and grid is not None:
            bank("daily_loss", series[grid.symbol][i].close)
            stopped = True
            equity = equity_at(marks)

        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak)

        if grid is None and not stopped and not risk.halted:
            for symbol in symbols:
                if i < cooldown[symbol]:
                    counts["cooldown"] += 1
                    continue
                window = series[symbol][max(0, i - 249): i + 1]
                regime = assess(window, None, params)
                if not regime.ranging:
                    for reason in regime.reasons:
                        counts[reason] += 1
                    continue
                counts["ranging"] += 1
                plan, why = build_plan(window, specs[symbol], equity, params, leverage[symbol])
                if plan is None:
                    counts[why] += 1
                    continue
                grid = ActiveGrid.from_plan(plan, created_ms=series[symbol][i].ts)
                grid.sync_orders(series[symbol][i].close, equity, specs[symbol], params)
                active = symbol
                grids_started += 1
                counts["started"] += 1
                if portfolio:
                    break

    last_marks = {symbol: series[symbol][length - 1].close for symbol in symbols} if length else {}
    final = equity_at(last_marks) if length else equity0
    open_unreal = grid.unrealized(last_marks[grid.symbol]) if grid is not None else 0.0
    open_realized = grid.realized if grid is not None else 0.0
    open_fees = grid.fees if grid is not None else 0.0
    open_funding = grid.funding if grid is not None else 0.0
    realized = banked_realized + open_realized
    fees = banked_fees + open_fees
    funding = banked_funding + open_funding
    return {
        "bars": length,
        "start_equity": equity0,
        "end_equity": final,
        "net": final - equity0,
        "realized": realized,
        "unrealized": open_unreal,
        "fees": fees,
        "maker_fees": fees - taker_fees,
        "taker_fees": taker_fees,
        "funding": funding,
        "net_without_funding": final - equity0 + funding,
        "max_drawdown_pct": max_dd * 100.0,
        "grids_started": grids_started,
        "maker_fills": maker_fills,
        "round_trips": trips,
        "round_trip_wins": trip_wins,
        "exits": dict(exit_reasons),
        "counts": dict(counts),
        "open_symbol": grid.symbol if grid is not None else "",
        "from_ts": series[symbols[0]][0].ts if length else 0,
        "to_ts": series[symbols[0]][length - 1].ts if length else 0,
    }
