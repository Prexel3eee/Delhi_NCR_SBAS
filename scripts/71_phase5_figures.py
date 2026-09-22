#!/usr/bin/env python
"""
SUPERSEDED - do not run.

This script rendered F1-F8 in the Phase V internal style. It was replaced in
Phase V-B by:

    scripts/73_phase5b_restyle.py    F1-F8, F12   (shared publication style)
    scripts/72_phase5b_figures.py    F9-F11       (shared publication style)

Both write to the same output paths, so running this file would silently
overwrite the publication figures with the superseded internal styling.

It is retained rather than deleted so that the Phase V rendering remains
inspectable in the version history, and it now fails loudly instead of
overwriting anything.

Usage
-----
    python scripts/71_phase5_figures.py     -> exits 2
"""

from __future__ import annotations

import sys

MESSAGE = """
scripts/71_phase5_figures.py is SUPERSEDED and will not run.

It would overwrite the publication figures with the superseded Phase V
internal styling. Use instead:

    python scripts/73_phase5b_restyle.py    # F1-F8, F12
    python scripts/72_phase5b_figures.py    # F9-F11

The Phase V-B style module is scripts/pubstyle.py.
"""


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
