"""Backward-compatible source bootstrap shim."""

from __future__ import annotations

from agens.app_bootstrap import bootstrap_database, bootstrap_runtime

__all__ = ["bootstrap_database", "bootstrap_runtime"]
