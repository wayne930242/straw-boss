"""Shared library behind Straw Boss's script entry points.

Entry points stay flat in `scripts/` so every skill, hook, and contract can
keep invoking them by path with no install step; Python puts that directory on
`sys.path`, which is what makes this package importable from them.

`SCRIPTS_DIR` and `PLUGIN_ROOT` are named here rather than counted out as
`__file__.parents[n]` at each use site, so moving a module between subpackages
cannot silently change which directory it resolves to.
"""

from __future__ import annotations

from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = SCRIPTS_DIR.parent
