# %% [markdown]
# # Viewing Inference Results in a Terminal
# Source: https://docs.ultralytics.com/guides/view-results-in-terminal/
#
# When working on a remote machine via SSH, visualizing inference results
# is normally not possible without transferring files. The VSCode integrated
# terminal supports rendering images directly using the **sixel** protocol.
#
# ## Requirements
# - **Linux or macOS only** (Windows not yet supported for sixel in VSCode)
# - VSCode with integrated terminal
# - `python-sixel` library
#
# ## VSCode Settings
# Enable these in VSCode settings:
# ```json
# {
#     "terminal.integrated.enableImages": true,
#     "terminal.integrated.gpuAcceleration": "auto"
# }
# ```

# %% Installation
import subprocess
import sys

def _install(packages: list[str]) -> None:
    for pkg in packages:
        print(f"[SETUP] Installing {pkg}...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-U", pkg],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
    print("[SETUP] All packages installed.")

_install(["ultralytics", "sixel", "opencv-python-headless"])

# %% [markdown]
# ## Step-by-Step Process
#
# 1. Load model and run inference
# 2. Plot results onto a numpy array
# 3. Encode the array as PNG bytes
# 4. Wrap bytes in a file-like object
# 5. Draw using `SixelWriter`

# %% Run Inference
from ultralytics import YOLO

model = YOLO("yolo26n.pt")
print("[DEBUG] Model loaded: yolo26n.pt")

results = model.predict(
    source="https://ultralytics.com/images/bus.jpg",
    imgsz=640,
    conf=0.25,
    verbose=False,
)
print(f"[DEBUG] Inference complete: {len(results[0].boxes)} detections")

plot = results[0].plot()
print(f"[DEBUG] Plot shape: {plot.shape}, dtype: {plot.dtype}")

# %% Convert to Bytes
import io
import cv2

im_bytes: bytes = cv2.imencode(".png", plot)[1].tobytes()
mem_file = io.BytesIO(im_bytes)
print(f"[DEBUG] Image encoded: {len(im_bytes)} bytes")

# %% Display in Terminal with Sixel
try:
    from sixel import SixelWriter

    writer = SixelWriter()
    writer.draw(mem_file)
    print("[DEBUG] Image rendered in terminal via sixel")
except ImportError:
    print("[DEBUG] sixel library not available — install with: pip install sixel")
    print("[DEBUG] Note: sixel only works on Linux/macOS in VSCode terminal")
except Exception as e:
    print(f"[DEBUG] Could not render sixel image: {e}")
    print("[DEBUG] Ensure terminal.integrated.enableImages is true in VSCode settings")

# %% [markdown]
# ## Alternative: Save and Open Manually
#
# If sixel is not available, save the annotated image and open it:

# %% Save Annotated Image
OUTPUT_PATH: str = "inference_result.png"
cv2.imwrite(OUTPUT_PATH, plot)
print(f"[DEBUG] Annotated image saved to {OUTPUT_PATH}")

try:
    from IPython.display import Image, display
    display(Image(OUTPUT_PATH))
except ImportError:
    print(f"[DEBUG] Open {OUTPUT_PATH} manually to view results")

# %% [markdown]
# ## Full Code Example (Copy-Paste Ready)
#
# ```python
# import io
# import cv2
# from sixel import SixelWriter
# from ultralytics import YOLO
#
# model = YOLO("yolo26n.pt")
# results = model.predict(source="ultralytics/assets/bus.jpg")
# plot = results[0].plot()
#
# im_bytes = cv2.imencode(".png", plot)[1].tobytes()
# mem_file = io.BytesIO(im_bytes)
#
# w = SixelWriter()
# w.draw(mem_file)
# ```
#
# ## Notes
# - Use `clear` in terminal to erase the rendered image
# - Video/animated GIF rendering via sixel is **untested**
# - For Jupyter notebooks, use `IPython.display.Image` instead
