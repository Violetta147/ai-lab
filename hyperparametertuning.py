# %% [markdown]
# # YOLO26n Hyperparameter Tuning
# Executed on FPT AI Factory VM (Jupyter Notebook via SSH)
# Dataset: Ultralytics Platform (`ul://` URI)
# Model: yolo26n

# %% Environment Setup — install required packages
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

_install(["ultralytics", "ray[tune]", "wandb", "ipywidgets"])

# %% GPU & Environment Verification
import torch
import os

print(f"[DEBUG] Python: {sys.version}")
print(f"[DEBUG] PyTorch: {torch.__version__}")
print(f"[DEBUG] CUDA available: {torch.cuda.is_available()}")

if not torch.cuda.is_available():
    raise RuntimeError(
        "No CUDA GPU detected. Hyperparameter tuning requires GPU. "
        "Check nvidia-smi on this FPT AI Factory VM."
    )

GPU_COUNT: int = torch.cuda.device_count()
for i in range(GPU_COUNT):
    name: str = torch.cuda.get_device_name(i)
    props = torch.cuda.get_device_properties(i)
    if hasattr(props, "total_memory"):
        mem_gb: float = float(props.total_memory) / 1e9
    elif hasattr(props, "total_mem"):
        mem_gb = float(props.total_mem) / 1e9
    else:
        raise AttributeError(
            "torch.cuda.get_device_properties(...) does not expose GPU memory as "
            "'total_memory' (or 'total_mem')."
        )
    print(f"[DEBUG] GPU {i}: {name} ({mem_gb:.1f} GB)")

print(f"[DEBUG] Total GPUs: {GPU_COUNT}")

# %% Configuration
# ──────────────────────────────────────────────────────
# API keys: reads from container env vars set in FPT AI Factory UI.
# Fall back to hardcoded values if env vars are missing.
ULTRALYTICS_API_KEY: str = os.environ.get("ULTRALYTICS_API_KEY", "")
WANDB_API_KEY: str = os.environ.get("WANDB_API_KEY", "")

# Dataset URI on Ultralytics Platform
DATASET_URI: str = os.environ.get("DATASET_URI", "").strip()

# Tuning budget
TUNING_EPOCHS: int = 10
TUNING_ITERATIONS: int = 50
IMAGE_SIZE: int = 640
BATCH_SIZE: int = 16

# Optimizer: lock it so tuned `lr0` / `momentum` are not overridden by optimizer=auto
OPTIMIZER: str = "AdamW"

# Ray Tune scheduling uses Ultralytics internal NUM_THREADS per trial.
# In your container, this currently resolves to NUM_THREADS=8, so Ray schedules only 1 trial at a time.
# Lower this to allow multiple concurrent trials.
TUNER_CPU_THREADS_PER_TRIAL: int = 3

# W&B project name (only used if WANDB_API_KEY is set)
WANDB_PROJECT: str = "YOLO26n-Vehicle-Tuning"
# ──────────────────────────────────────────────────────

if not ULTRALYTICS_API_KEY:
    raise ValueError(
        "ULTRALYTICS_API_KEY not found. Either:\n"
        "  1) Set it in FPT AI Factory container 'Environment variables', or\n"
        "  2) Run in Jupyter: %env ULTRALYTICS_API_KEY=your_key_here"
    )

if not DATASET_URI or "YOUR_USERNAME" in DATASET_URI or "YOUR_DATASET_NAME" in DATASET_URI:
    raise ValueError(
        "DATASET_URI not set correctly. Provide it as an Ultralytics Platform dataset URI:\n"
        "  ul://<username>/datasets/<dataset-name>\n"
        "Set it in FPT AI Factory container 'Environment variables' as DATASET_URI, "
        "or in Jupyter with: %env DATASET_URI=ul://... "
    )

os.environ["ULTRALYTICS_API_KEY"] = ULTRALYTICS_API_KEY
print(f"[DEBUG] ULTRALYTICS_API_KEY set (length={len(ULTRALYTICS_API_KEY)})")
print(f"[DEBUG] Dataset URI: {DATASET_URI}")

# %% W&B Setup (optional)
# W&B with model.tune(use_ray=True):
#   - wandb.init() here runs in the MAIN process only.
#   - Ray spawns worker processes that do NOT inherit this session.
#   - Ultralytics workers auto-detect WANDB_API_KEY env var and init their own W&B runs.
#   - Known issue: worker W&B runs may all be named "train" instead of trial IDs.
#     Fix: upgrade ultralytics >= 8.4.19 (PR #23492 fixes project/entity propagation).
if WANDB_API_KEY:
    import wandb
    os.environ["WANDB_API_KEY"] = WANDB_API_KEY
    wandb.login(key=WANDB_API_KEY)
    print(f"[DEBUG] W&B logged in — project will be: {WANDB_PROJECT}")
    print("[DEBUG] Note: each Ray worker will create its own W&B run automatically.")
    print("[DEBUG] Check W&B dashboard for per-trial metrics after tuning starts.")
else:
    print("[DEBUG] W&B skipped (WANDB_API_KEY env var not set)")

# %% Define Custom Search Space
from ray import tune

# Augmentation params (flip, crop, saturation, brightness, blur, noise)
# are already applied at dataset level on Ultralytics Platform — not tuned here.
SEARCH_SPACE: dict[str, tune.search.sample.Domain] = {
    # Learning rate
    "lr0": tune.loguniform(1e-5, 1e-2),
    "lrf": tune.uniform(0.01, 0.2),
    # Optimizer dynamics
    "momentum": tune.uniform(0.7, 0.98),
    "weight_decay": tune.loguniform(1e-5, 1e-3),
    # Warmup
    "warmup_epochs": tune.uniform(1.0, 5.0),
    "warmup_momentum": tune.uniform(0.5, 0.95),
}

print(f"[DEBUG] Search space defined — {len(SEARCH_SPACE)} hyperparameters")
for param_name in SEARCH_SPACE:
    print(f"  - {param_name}")

# %% Run Hyperparameter Tuning with Ray Tune
from ultralytics import YOLO

print("[DEBUG] Loading yolo26n.pt pretrained model...")
model: YOLO = YOLO("yolo26n.pt")

print(f"[DEBUG] Starting Ray Tune — {TUNING_ITERATIONS} iterations, {TUNING_EPOCHS} epochs each")
print(f"[DEBUG] Dataset: {DATASET_URI}")
print(f"[DEBUG] Image size: {IMAGE_SIZE}, Batch size: {BATCH_SIZE}")
print(f"[DEBUG] Optimizer locked to: {OPTIMIZER}")

# Patch Ultralytics tuner NUM_THREADS so Ray can run multiple trials concurrently.
# Note: this affects Ray trial resource accounting only; the dataloader `workers` is controlled separately.
import ultralytics.utils.tuner as yolo_tuner

original_num_threads: int = int(yolo_tuner.NUM_THREADS)
print(f"[DEBUG] Ultralytics tuner NUM_THREADS (original): {original_num_threads}")
yolo_tuner.NUM_THREADS = int(TUNER_CPU_THREADS_PER_TRIAL)
print(f"[DEBUG] Ultralytics tuner NUM_THREADS (patched): {yolo_tuner.NUM_THREADS}")

result_grid = model.tune(
    data=DATASET_URI,
    space=SEARCH_SPACE,
    epochs=TUNING_EPOCHS,
    iterations=TUNING_ITERATIONS,
    imgsz=IMAGE_SIZE,
    batch=BATCH_SIZE,
    workers=2,
    use_ray=True,
    gpu_per_trial=0.25,
    optimizer=OPTIMIZER,
)

print("[DEBUG] Tuning complete!")

# %% Analyze Tuning Results
import json

best_result = result_grid.get_best_result(metric="metrics/mAP50-95(B)", mode="max")
best_hyperparams: dict = best_result.config

print("=" * 60)
print("BEST HYPERPARAMETERS FOUND")
print("=" * 60)
for k, v in sorted(best_hyperparams.items()):
    if k in SEARCH_SPACE:
        print(f"  {k}: {v}")
print("=" * 60)
print(f"Best mAP50-95: {best_result.metrics.get('metrics/mAP50-95(B)', 'N/A')}")
print(f"Best mAP50:    {best_result.metrics.get('metrics/mAP50(B)', 'N/A')}")

best_params_path: str = "best_hyperparams.json"
tuned_params: dict = {k: v for k, v in best_hyperparams.items() if k in SEARCH_SPACE}
with open(best_params_path, "w") as f:
    json.dump(tuned_params, f, indent=2)
print(f"[DEBUG] Best hyperparams saved to {best_params_path}")

