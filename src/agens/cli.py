"""Compatibility shim for the unified CLI."""
from __future__ import annotations

from .main import app, cli


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
