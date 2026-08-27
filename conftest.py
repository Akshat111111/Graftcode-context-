"""
conftest.py
~~~~~~~~~~~

Shared pytest fixtures and path configuration.
Adds the project root to sys.path so ``from vision.request_context_demo import ...``
resolves correctly in tests.
"""

import sys
from pathlib import Path

root = Path(__file__).parent
sys.path.insert(0, str(root))
