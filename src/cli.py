"""Backward-compatible source CLI shim."""

from __future__ import annotations

from agens.cli import app, cli, main


if __name__ == "__main__":
    main()

