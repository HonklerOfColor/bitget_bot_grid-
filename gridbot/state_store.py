"""JSON-Zustand. Schreiben ist atomar, damit ein Abbruch keine halbe Datei hinterlässt."""

from __future__ import annotations

import json
import os
from pathlib import Path

from gridbot.engine import ActiveGrid
from gridbot.risk import RiskGuard


class StateStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> dict:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.path)


def export_state(mode: str, equity_anchor: float, risk: RiskGuard, grids: dict[str, ActiveGrid], extra: dict | None = None) -> dict:
    payload = {
        "version": 1,
        "mode": mode,
        "equity_anchor": equity_anchor,
        "risk": risk.to_dict(),
        "grids": {symbol: grid.to_dict() for symbol, grid in grids.items()},
    }
    if extra:
        payload.update(extra)
    return payload


def import_grids(raw: dict) -> dict[str, ActiveGrid]:
    return {symbol: ActiveGrid.from_dict(body) for symbol, body in (raw.get("grids") or {}).items()}
