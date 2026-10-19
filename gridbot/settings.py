"""Lädt config.py, wenn vorhanden. Paper und Backtest laufen auch ohne Datei."""

from __future__ import annotations

import importlib


def load_user_config():
    try:
        return importlib.import_module("config")
    except ImportError:
        return None
