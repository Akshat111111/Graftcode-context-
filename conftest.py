"""
conftest.py
~~~~~~~~~~~

Shared pytest fixtures and path configuration.
Adds the project root to sys.path so `from graftcode import ...` and
`from src.service import ...` work in tests without installation.
"""

import sys
from pathlib import Path

# Allow `from graftcode import ...` and `from src.service import ...`
root = Path(__file__).parent
sys.path.insert(0, str(root / "src"))
sys.path.insert(0, str(root))
