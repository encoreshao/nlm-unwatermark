"""Standalone entry point used only by PyInstaller (see nlm-unwatermark.spec).

PyInstaller runs its entry script outside of any package context, so
`nlm_unwatermark/__main__.py`'s relative import (`from .cli import main`)
fails when frozen. This script lives outside the package and imports it
absolutely instead, with the project root added to `sys.path`.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nlm_unwatermark.cli import main

if __name__ == "__main__":
    main()
