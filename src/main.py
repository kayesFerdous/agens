"""Backward-compatible source entrypoint.

Use ``python -m agens`` or the ``agens`` console script for installed usage.
"""

from __future__ import annotations

from agens.main import app, cli


if __name__ == "__main__":
    cli()

