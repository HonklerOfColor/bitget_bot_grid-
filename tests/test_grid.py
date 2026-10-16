"""Orders, Abstände, Regime, Risiko, Neustart. Kein Netz."""

from __future__ import annotations

import unittest

from gridbot.backtest_engine import run_backtest
from gridbot.candles import Candle
from gridbot.engine import ActiveGrid, build_plan
from gridbot.params import GridParams, SymbolConfig, parse_symbols, resolve_mode
from gridbot.payloads import Intent, build_payload
from gridbot.reconcile import absorb_exchange_order, position_mismatch
from gridbot.regime import assess
from gridbot.risk import RiskGuard
from gridbot.specs import ContractSpec


def spec_alt() -> ContractSpec:
    return ContractSpec("ALTUSDT", min_qty=0.01, min_notional=5.0, qty_step=0.01, price_tick=0.01, price_place=2, qty_place=2)


def spec_btc() -> ContractSpec:
    return ContractSpec("BTCUSDT", 0.0001, 5.0, 0.0001, 0.1, 1, 4)


def bounded_range(n: int, lower: float, upper: float, end: float | None = None) -> list[Candle]:
    """Preis bleibt in [lower, upper], berührt beide Seiten und schließt in der Mitte."""
    mid = (lower + upper) / 2.0
    end = mid if end is None else end
    out = []
    for i in range(n):
        phase = (i % 16) / 16.0
        if phase < 0.5:
            px = lower + (upper - lower) * (phase / 0.5)
        else:
            px = upper - (upper - lower) * ((phase - 0.5) / 0.5)
        if i == n - 1:
            px = end
        high = min(upper, max(px, upper if i % 16 == 8 else px))
        low = max(lower, min(px, lower if i % 16 == 0 else px))
        out.append(Candle(i * 3_600_000, px, high, low, px, 1.0))
    return out


def chop_candles(n: int = 400, seed: int = 7) -> list[Candle]:
    """Gezähmter Random Walk. ADX bleibt niedrig, im Gegensatz zu einer glatten Sinuswelle."""
    import random

    rng = random.Random(seed)
    price = 100.0
    out = []
    for i in range(n):
        price += rng.uniform(-0.35, 0.35)
        price = min(102.5, max(97.5, price))
        out.append(Candle(i * 3_600_000, price, price + 0.08, price - 0.08, price, 1.0))
    return out


def trend_candles(n: int = 200) -> list[Candle]:
    out = []
    price = 100.0
    for i in range(n):
        price *= 1.008
        out.append(Candle(i * 3_600_000, price * 0.998, price * 1.002, price * 0.997, price, 1.0))
    return out


def params(**overrides) -> GridParams:
    base = GridParams()
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


class FakeClient:
    def __init__(self):
        self.placed: list[dict] = []
        self.cancelled: list[dict] = []

    def place_order(self, payload: dict) -> dict:
        self.placed.append(payload)
        return {"code": "00000", "data": {"orderId": f"id{len(self.placed)}", "clientOid": payload.get("clientOid")}}

    def cancel_order(self, payload: dict) -> dict:
        self.cancelled.append(payload)
        return {"code": "00000"}


def payloads_of(grid: ActiveGrid, spec: ContractSpec, pos_mode: str) -> list[dict]:
    out = []
    for order in grid.orders.values():
        intent = Intent(
            symbol=grid.symbol,
            book_side=order.book_side,
            purpose=order.purpose,
            position_side=order.position_side,
            level=order.level,
            price=order.price,
            size=order.size,
            order_type="limit",
            client_oid=order.client_oid,
        )
        out.append(build_payload(intent, spec, pos_mode, "USDT-FUTURES", "isolated", "USDT"))
    return out


class PayloadTests(unittest.TestCase):
    def test_post_only_sizes_and_reduce_only_exits(self):
        spec = spec_alt()
        cfg = params()
        candles = bounded_range(80, 100.0, 103.0, 101.5)
        plan, why = build_plan(candles, spec, 50.0, cfg, leverage=2)
        self.assertIsNotNone(plan, why)
        assert plan is not None
        self.assertGreaterEqual(plan.spacing_pct, cfg.min_spacing_pct * 0.98)
        self.assertGreaterEqual(plan.qty * plan.levels[0], spec.min_notional)
        self.assertEqual(round(plan.qty / spec.qty_step) * spec.qty_step, plan.qty)
        grid = ActiveGrid.from_plan(plan)
        mark = candles[-1].close
        grid.sync_orders(mark, 50.0, spec, cfg)
        self.assertTrue(grid.orders)
        fake = FakeClient()
        for payload in payloads_of(grid, spec, "hedge"):
            fake.place_order(payload)
        self.assertTrue(fake.placed)
        for payload in fake.placed:
            self.assertEqual(payload["force"], "post_only")
            self.assertEqual(payload["orderType"], "limit")
            self.assertEqual(payload["tradeSide"], "open")
            self.assertNotIn("reduceOnly", payload)
            self.assertNotIn("e", payload["size"].lower())
            size = float(payload["size"])
            self.assertGreaterEqual(size + 1e-12, spec.min_qty)
            self.assertGreaterEqual(size * float(payload["price"]) + 1e-8, spec.min_notional)
            self.assertIn(payload["side"], ("buy", "sell"))

        buy = next(order for order in grid.orders.values() if order.book_side == "buy" and order.purpose == "open")
        grid.apply_fill(buy, buy.price, buy.size, cfg.maker_fee)
        grid.sync_orders(mark, 50.0, spec, cfg)
        close_payloads = [item for item in payloads_of(grid, spec, "hedge") if item.get("tradeSide") == "close"]
        self.assertTrue(close_payloads)
        for payload in close_payloads:
            self.assertEqual(payload["force"], "post_only")
            self.assertEqual(payload["orderType"], "limit")
            self.assertEqual(payload["side"], "buy")  # Hedge: Close-Long = Positionsrichtung buy
            self.assertNotIn("reduceOnly", payload)
            self.assertAlmostEqual(float(payload["size"]), plan.qty, places=8)

        emergency = grid.emergency_intents()
        self.assertTrue(emergency)
        hedge_exit = build_payload(emergency[0], spec, "hedge", "USDT-FUTURES", "isolated", "USDT")
        one_way_exit = build_payload(emergency[0], spec, "one_way", "USDT-FUTURES", "isolated", "USDT")
        fake.place_order(hedge_exit)
        fake.place_order(one_way_exit)
        self.assertEqual(hedge_exit["orderType"], "market")
        self.assertEqual(hedge_exit["force"], "ioc")
        self.assertEqual(hedge_exit["tradeSide"], "close")
        self.assertEqual(hedge_exit["side"], "buy")
        self.assertEqual(one_way_exit["reduceOnly"], "YES")
        self.assertEqual(one_way_exit["side"], "sell")
        self.assertNotIn("tradeSide", one_way_exit)
        self.assertEqual(one_way_exit["force"], "ioc")

    def test_btc_min_size_refuses_too_small_account(self):
        candles = bounded_range(80, 80_000, 83_000, 81_500)
        plan, why = build_plan(candles, spec_btc(), 10.0, params(), leverage=2)
        self.assertIsNone(plan)
        self.assertEqual(why, "unter_mindestgroesse")
        plan_ok, why_ok = build_plan(bounded_range(80, 80_000, 83_000, 81_500), spec_btc(), 50.0, params(), leverage=2)
        self.assertIsNotNone(plan_ok, why_ok)

    def test_spacing_refuses_tight_range(self):
        tight = params(min_range_pct=0.001, max_range_pct=0.5, edge_inset=0.05, grid_levels=8, min_grid_levels=4)
        candles = bounded_range(80, 100.0, 100.30, 100.15)
        plan, why = build_plan(candles, spec_alt(), 50.0, tight, leverage=2)
        self.assertIsNone(plan)
        self.assertIn(why, ("abstand_unter_fee", "range_zu_eng"))


class RoundTripTests(unittest.TestCase):
    def test_oscillation_pays_more_than_maker_fees_until_a_stop(self):
        spec = spec_alt()
        cfg = params()
        candles = bounded_range(48, 98.0, 102.0, 100.0)
        plan, why = build_plan(candles, spec, 80.0, cfg, leverage=2)
        self.assertIsNotNone(plan, why)
        assert plan is not None
        grid = ActiveGrid.from_plan(plan)
        mark = 100.0
        grid.sync_orders(mark, 80.0, spec, cfg)
        buys = [order for order in list(grid.orders.values()) if order.book_side == "buy"]
        self.assertTrue(buys)
        buy = max(buys, key=lambda order: order.price)
        grid.apply_fill(buy, buy.price, buy.size, cfg.maker_fee)
        grid.sync_orders(mark, 80.0, spec, cfg)
        close = next(order for order in grid.orders.values() if order.purpose == "close" and order.position_side == "long")
        grid.apply_fill(close, close.price, close.size, cfg.maker_fee)
        self.assertGreater(grid.fees, 0)
        self.assertGreater(grid.realized, grid.fees)
        self.assertGreater(grid.net_pnl(mark), 0)
        self.assertAlmostEqual(grid.long_qty, 0.0, places=8)


class RegimeTests(unittest.TestCase):
    def test_range_passes_and_trend_does_not(self):
        cfg = params()
        ranging = assess(chop_candles(300, seed=1), None, cfg)
        self.assertTrue(ranging.ranging, ranging.reason_text())
        trending = assess(trend_candles(220), None, cfg)
        self.assertFalse(trending.ranging)
        self.assertTrue(set(trending.reasons) & {"adx_1h", "adx_4h", "efficiency"})


class RiskAndRestartTests(unittest.TestCase):
    def test_daily_loss_and_kill_switch(self):
        guard = RiskGuard()
        guard.on_day("2026-10-16", 50.0)
        self.assertFalse(guard.check_daily(48.0, 0.05))
        self.assertTrue(guard.check_daily(47.0, 0.05))
        self.assertEqual(guard.halt_reason, "daily_loss")
        guard.on_day("2026-10-17", 47.0)
        self.assertFalse(guard.halted)
        guard.engage_kill()
        self.assertEqual(guard.halt_reason, "kill_switch")
        guard.on_day("2026-10-18", 47.0)
        self.assertTrue(guard.halted)
        guard.release_kill_if_clear()
        self.assertFalse(guard.halted)

    def test_reconcile_applies_fill_and_flags_mismatch(self):
        spec = spec_alt()
        candles = bounded_range(80, 100.0, 103.0, 101.5)
        plan, why = build_plan(candles, spec, 50.0, params(), leverage=2)
        self.assertIsNotNone(plan, why)
        assert plan is not None
        grid = ActiveGrid.from_plan(plan)
        grid.sync_orders(candles[-1].close, 50.0, spec, params())
        order = next(iter(grid.orders.values()))
        note = absorb_exchange_order(
            grid,
            order,
            {"state": "filled", "filled": order.size, "avg": order.price},
            0.0002,
        )
        self.assertEqual(note, "filled")
        self.assertNotIn(order.client_oid, grid.orders)
        self.assertTrue(position_mismatch(grid, 0.0, 0.0, spec.qty_step))
        plan2, _ = build_plan(candles, spec, 50.0, params(), leverage=2)
        assert plan2 is not None
        resting = ActiveGrid.from_plan(plan2)
        resting.sync_orders(candles[-1].close, 50.0, spec, params())
        live = next(iter(resting.orders.values()))
        note_live = absorb_exchange_order(resting, live, {"state": "live", "filled": 0, "avg": live.price}, 0.0002)
        self.assertEqual(note_live, "resting")
        self.assertIn(live.client_oid, resting.orders)

    def test_state_roundtrip(self):
        spec = spec_alt()
        plan, why = build_plan(bounded_range(80, 100.0, 103.0, 101.5), spec, 50.0, params(), leverage=2)
        assert plan is not None, why
        grid = ActiveGrid.from_plan(plan)
        grid.sync_orders(100.0, 50.0, spec, params())
        restored = ActiveGrid.from_dict(grid.to_dict())
        self.assertEqual(set(restored.orders), set(grid.orders))
        self.assertEqual(restored.levels, grid.levels)

    def test_mode_and_leverage_cap(self):
        self.assertEqual(resolve_mode(None), "paper")

        class OldV2:
            DRY_RUN = False

        self.assertEqual(resolve_mode(OldV2()), "paper")

        class Live:
            DRY_RUN = False
            LIVE_TRADING = True

        self.assertEqual(resolve_mode(Live()), "live")
        symbols = parse_symbols(type("C", (), {"SYMBOLS": [{"symbol": "ETHUSDT", "leverage": 10}]})(), params())
        self.assertEqual(symbols, [SymbolConfig("ETHUSDT", 3)])


class BacktestGuardTests(unittest.TestCase):
    def test_trend_does_not_open_and_range_pays_fees(self):
        cfg = params()
        trend = run_backtest(trend_candles(240), spec_alt(), cfg, 50.0, 2)
        self.assertEqual(trend["grids_started"], 0)
        self.assertEqual(trend["fees"], 0)
        quiet = run_backtest(chop_candles(420), spec_alt(), cfg, 80.0, 2)
        self.assertGreater(quiet["grids_started"], 0)
        self.assertGreater(quiet["fees"], 0)
        self.assertGreater(quiet["maker_fills"], 0)


if __name__ == "__main__":
    unittest.main()
