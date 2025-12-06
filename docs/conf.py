"""Sphinx configuration for the Bird Acoustic Data Cruncher documentation."""

from __future__ import annotations

import datetime as _dt
import pathlib
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from badc import __version__  # noqa: E402  (import after sys.path mutation)

project = "Bird Acoustic Data Cruncher"
author = "UBC Freshwater Research Lab"
copyright = f"{_dt.datetime.now().year}, {author}"
release = __version__

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]

templates_path = ["_templates"]
exclude_patterns: list[str] = []

html_theme = "furo"
html_static_path = ["_static"]
