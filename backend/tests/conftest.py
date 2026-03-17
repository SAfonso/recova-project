from __future__ import annotations

from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_SRC = PROJECT_ROOT / "backend" / "src"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))


@pytest.fixture(autouse=True)
def _reset_sb_singleton():
    """Reset Supabase singleton between tests to prevent cross-test leaks."""
    import backend.src.triggers.shared as shared
    shared._SB_SINGLETON = None
    yield
    shared._SB_SINGLETON = None
