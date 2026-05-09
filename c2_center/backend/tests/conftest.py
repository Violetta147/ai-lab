"""Test setup: ensure the backend root is on sys.path so `app.*` imports resolve."""

import os
import sys

# tests/ -> backend/. Adding backend root lets `import app.xxx` work and also
# makes `prune_module` available for any model-loading paths.
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
