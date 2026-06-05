"""Test setup: ensure the backend root is on sys.path so `app.*` imports resolve."""

import os
import sys

# tests/ -> backend/. Adding backend root lets `import app.xxx` work and also
# makes `prune_module` available for any model-loading paths.
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pytest

@pytest.fixture
def sample_detection_payload():
    return [
        {
            "class_id": 0,
            "class_name": "person",
            "confidence": 0.95,
            "tracking_id": 1,
            "bbox": [10.0, 20.0, 50.0, 100.0]
        },
        {
            "class_id": 2,
            "class_name": "car",
            "confidence": 0.88,
            "tracking_id": 2,
            "bbox": [200.0, 150.0, 300.0, 250.0]
        }
    ]
