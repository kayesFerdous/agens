"""Agens application package."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("agens")
except PackageNotFoundError:
    __version__ = "0+local"

__all__ = ["__version__"]
