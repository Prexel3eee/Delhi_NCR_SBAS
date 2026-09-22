#!/usr/bin/env python
"""
Compatibility shim for running MintPy CLIs in this environment.

Why this exists
---------------
MintPy's local dask cluster is created as a bare `LocalCluster()`
(`mintpy/objects/cluster.py`), which enables the dask **dashboard**. The
dashboard imports **bokeh**, and this bokeh build still references
`np.bool8` — an alias **removed in NumPy 2.x**:

    RuntimeError: Cluster failed to start: module 'numpy' has no attribute 'bool8'

The environment has numpy 2.4.6, so parallel inversion dies at cluster start
(INC-004). Upgrading dask/distributed does not help: the reference is in bokeh,
not dask. `skimage.util.dtype` has the same stale reference.

Restoring the removed alias is the minimal, targeted fix. It changes no
numerical behaviour — `np.bool8` was always an alias for `np.bool_`.

Usage
-----
    python scripts/run_mintpy.py smallbaselineApp.py --dir ... --dostep ...
    python scripts/run_mintpy.py load_data.py -t template.txt

Any MintPy console-script name may be given as the first argument.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import numpy as np

# --- the shim -------------------------------------------------------------
if not hasattr(np, "bool8"):
    np.bool8 = np.bool_
    _PATCHED = True
else:
    _PATCHED = False


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2

    script = sys.argv[1]
    module_name = Path(script).stem
    # forwards the remaining argv unchanged, so MintPy CLIs parse normally
    sys.argv = [script] + sys.argv[2:]

    print(f"[run_mintpy] numpy {np.__version__}; np.bool8 shim applied: {_PATCHED}")

    module = importlib.import_module(f"mintpy.cli.{module_name}")
    return module.main()


if __name__ == "__main__":
    raise SystemExit(main())
