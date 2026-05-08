import os
import sys

# Ensure the backend package root (parent of tests/) is on sys.path so imports
# like `import analytics` resolve during test collection.
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
