"""Make the flat project modules (cost_model, policy, schemas) importable under pytest.

The project is not an installed package (package = false), so the project root is added
to sys.path here. Scripts under eval/ and examples/ do the equivalent themselves.
"""

import sys
from pathlib import Path

ROOT = str(Path(__file__).resolve().parent)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
