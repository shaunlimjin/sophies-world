"""pytest configuration: add scripts/ to Python path for all tests."""

import sys
from pathlib import Path

# scripts/ is two levels up from tests/
_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))
