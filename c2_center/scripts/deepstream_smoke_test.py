"""DeepStream smoke test helper for C2 Center.

This does not require DeepStream runtime. It validates the expected JSON schema
and checks that a DeepStream install path looks plausible for 6.0.1-devel / 6.0.1.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def resolve_ds_dir() -> Path | None:
    env = os.environ.get("DS_DIR")
    if env and Path(env).exists():
        return Path(env)

    candidates = [
        Path("/opt/nvidia/deepstream/deepstream-6.0.1-devel"),
        Path("/opt/nvidia/deepstream/deepstream-6.0.1"),
        Path("/opt/nvidia/deepstream/deepstream-6.0"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def validate_payload(payload: dict) -> list[str]:
    errors: list[str] = []
    required = ["stream_id", "frame_id", "timestamp", "objects"]
    for key in required:
        if key not in payload:
            errors.append(f"missing key: {key}")

    if "objects" in payload and not isinstance(payload["objects"], list):
        errors.append("objects must be a list")

    if isinstance(payload.get("objects"), list):
        for idx, obj in enumerate(payload["objects"]):
            for key in ["tracking_id", "class_id", "class_name", "bbox", "confidence"]:
                if key not in obj:
                    errors.append(f"objects[{idx}] missing key: {key}")
            bbox = obj.get("bbox", {})
            if not all(k in bbox for k in ("x", "y", "w", "h")):
                errors.append(f"objects[{idx}].bbox missing x/y/w/h")
    return errors


def main() -> int:
    sample = {
        "stream_id": "cam_8554",
        "frame_id": 1024,
        "timestamp": "1679123456.789",
        "objects": [
            {
                "tracking_id": 45,
                "class_id": 0,
                "class_name": "car",
                "bbox": {"x": 100, "y": 200, "w": 150, "h": 80},
                "confidence": 0.89,
            }
        ],
    }

    ds_dir = resolve_ds_dir()
    if ds_dir is None:
        print("WARN: DeepStream 6.0.1-devel / 6.0.1 / 6.0 install not found in default paths")
    else:
        print(f"OK: DeepStream directory found: {ds_dir}")
        samples_dir = ds_dir / "samples"
        print(f"OK: samples dir exists: {samples_dir.exists()} ({samples_dir})")

    errors = validate_payload(sample)
    if errors:
        print("Payload validation failed:")
        for err in errors:
            print(f"- {err}")
        return 1

    print("OK: sample payload schema is valid")
    print(json.dumps(sample, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
