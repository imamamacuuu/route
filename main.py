#!/usr/bin/env python3
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
PARENT_DIR = CURRENT_DIR.parent

if str(PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(PARENT_DIR))
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

try:
    from route.server import run
except ImportError:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "route",
        CURRENT_DIR / "__init__.py",
        submodule_search_locations=[str(CURRENT_DIR)]
    )
    if spec and spec.loader:
        mod = importlib.util.module_from_spec(spec)
        sys.modules["route"] = mod
        spec.loader.exec_module(mod)
    from route.server import run

if __name__ == "__main__":
    run()
