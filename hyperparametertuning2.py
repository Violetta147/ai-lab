# %% [markdown]
# # YOLO Hyperparameter Tuning with Ray Tune (HyperOpt + ASHA)
# Custom Ray Tune loop — gives full control over search algorithm,
# early stopping (ASHA), per-epoch metric reporting, and resource allocation.
# Executed on FPT AI Factory VM (Jupyter Notebook via SSH)

# %% Environment Setup
import subprocess
import sys
import os
import json

def _install(packages: list[str]) -> None:
    for pkg in packages:
        print(f"[SETUP] Installing {pkg}...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-U", pkg],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
    print("[SETUP] All packages installed.")

_install(["ultralytics", "ray[tune]", "hyperopt", "wandb", "ipywidgets"])

# %% GPU & Environment Verification
import torch

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
ULTRALYTICS_API_KEY: str = os.environ.get("ULTRALYTICS_API_KEY", "")
WANDB_API_KEY: str = os.environ.get("WANDB_API_KEY", "")
DATASET_URI: str = os.environ.get("DATASET_URI", "").strip()

TUNING_EPOCHS: int = 10
TUNING_ITERATIONS: int = 50
IMAGE_SIZE: int = 640
OPTIMIZER: str = "AdamW"
WANDB_PROJECT: str = "YOLO26n-Vehicle-Tuning-v2"

# CPU/GPU per Ray trial — adjust to your VM hardware
CPU_PER_TRIAL: int = 3
GPU_PER_TRIAL: float = 0.5

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
        "or in Jupyter with: %env DATASET_URI=ul://..."
    )

os.environ["ULTRALYTICS_API_KEY"] = ULTRALYTICS_API_KEY
print(f"[DEBUG] ULTRALYTICS_API_KEY set (length={len(ULTRALYTICS_API_KEY)})")
print(f"[DEBUG] Dataset URI: {DATASET_URI}")

# %% W&B Setup (optional — env var WANDB_API_KEY propagates to Ray workers automatically)
if WANDB_API_KEY:
    import wandb
    os.environ["WANDB_API_KEY"] = WANDB_API_KEY
    wandb.login(key=WANDB_API_KEY)
    wandb.init(project=WANDB_PROJECT)
    print(f"[DEBUG] W&B initialized — project: {WANDB_PROJECT}")
else:
    print("[DEBUG] W&B skipped (WANDB_API_KEY env var not set)")

# %% Training function for Ray Tune (per-epoch reporting for ASHA)
from ultralytics import YOLO
import ray
from ray import train, tune
from ray.tune.search.hyperopt import HyperOptSearch
from ray.tune.schedulers import ASHAScheduler

def train_yolo(config: dict) -> None:
    """Train YOLO with per-epoch metric reporting so ASHA can early-stop bad trials."""
    dataset_uri: str = os.environ["DATASET_URI"]

    # Separate Ray-specific params from YOLO train kwargs
    yolo_hparams: dict = {k: v for k, v in config.items() if k != "batch"}
    batch_size: int = config.get("batch", 16)

    # Each Ray worker is a separate process — must load model fresh
    model: YOLO = YOLO("yolo26n.pt")

    # Train 1 epoch at a time in a loop, report metrics after each epoch.
    # ASHA uses these intermediate reports to kill underperforming trials early.
    for epoch_idx in range(TUNING_EPOCHS):
        results = model.train(
            data=dataset_uri,
            epochs=1,
            imgsz=IMAGE_SIZE,
            batch=batch_size,
            optimizer=OPTIMIZER,
            project="YOLO26n-Vehicle-Tuning-v2",
            resume=(epoch_idx > 0),
            verbose=False,
            **yolo_hparams,
        )

        metrics: dict = results.results_dict
        map50_95: float = metrics.get("metrics/mAP50-95(B)", 0.0)
        map50: float = metrics.get("metrics/mAP50(B)", 0.0)

        train.report({
            "map50_95": map50_95,
            "map50": map50,
            "epoch": epoch_idx + 1,
        })
        print(f"[TRIAL] epoch {epoch_idx + 1}/{TUNING_EPOCHS} — mAP50-95={map50_95:.4f}")

# %% Search space (batch + dropout on top of file 1's 6 params)
SEARCH_SPACE: dict = {
    "batch": tune.choice([8, 16, 32]),
    "dropout": tune.uniform(0.1, 0.5),
    "lr0": tune.loguniform(1e-5, 1e-2),
    "lrf": tune.uniform(0.01, 0.2),
    "momentum": tune.uniform(0.7, 0.98),
    "weight_decay": tune.loguniform(1e-5, 1e-3),
    "warmup_epochs": tune.uniform(1.0, 5.0),
    "warmup_momentum": tune.uniform(0.5, 0.95),
}

print(f"[DEBUG] Search space defined — {len(SEARCH_SPACE)} hyperparameters")
for param_name in SEARCH_SPACE:
    print(f"  - {param_name}")

# %% HyperOpt (Bayesian/TPE) search + ASHA early stopping
algo_hyperopt: HyperOptSearch = HyperOptSearch(metric="map50_95", mode="max")

# ASHA kills underperforming trials after grace_period epochs
scheduler_asha: ASHAScheduler = ASHAScheduler(
    metric="map50_95",
    mode="max",
    max_t=TUNING_EPOCHS,
    grace_period=3,
)

# %% Launch Ray Tune
ray.init(ignore_reinit_error=True)

tune_config: tune.TuneConfig = tune.TuneConfig(
    search_alg=algo_hyperopt,
    scheduler=scheduler_asha,
    num_samples=TUNING_ITERATIONS,
)

tuner: tune.Tuner = tune.Tuner(
    tune.with_resources(train_yolo, resources={"cpu": CPU_PER_TRIAL, "gpu": GPU_PER_TRIAL}),
    tune_config=tune_config,
    param_space=SEARCH_SPACE,
)

print(f"[DEBUG] Starting HyperOpt+ASHA tuning — {TUNING_ITERATIONS} trials, up to {TUNING_EPOCHS} epochs each")
print(f"[DEBUG] Resources per trial: CPU={CPU_PER_TRIAL}, GPU={GPU_PER_TRIAL}")
results: tune.ResultGrid = tuner.fit()

# %% Analyze results
best_result = results.get_best_result(metric="map50_95", mode="max")
best_hyperparams: dict = best_result.config

print("=" * 60)
print("BEST HYPERPARAMETERS FOUND (HyperOpt + ASHA)")
print("=" * 60)
for k, v in sorted(best_hyperparams.items()):
    if k in SEARCH_SPACE:
        print(f"  {k}: {v}")
print("=" * 60)
print(f"Best mAP50-95: {best_result.metrics.get('map50_95', 'N/A')}")
print(f"Best mAP50:    {best_result.metrics.get('map50', 'N/A')}")
print(f"Epochs run:    {best_result.metrics.get('epoch', 'N/A')}")

best_params_path: str = "best_hyperparams_v2.json"
tuned_params: dict = {k: v for k, v in best_hyperparams.items() if k in SEARCH_SPACE}
with open(best_params_path, "w") as f:
    json.dump(tuned_params, f, indent=2)
print(f"[DEBUG] Best hyperparams saved to {best_params_path}")