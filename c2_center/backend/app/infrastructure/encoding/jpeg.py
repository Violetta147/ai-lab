"""JPEG encoding helpers used by the WebSocket transport."""

import base64

import cv2
import numpy as np


def frame_to_base64(frame: np.ndarray, quality: int = 75) -> str:
    """Encode a BGR frame as JPEG and return its base64 representation."""
    encode_params = [cv2.IMWRITE_JPEG_QUALITY, int(quality)]
    _, buffer = cv2.imencode(".jpg", frame, encode_params)
    return base64.b64encode(buffer).decode("utf-8")
