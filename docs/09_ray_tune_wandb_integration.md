# Hyperparameter Tuning Guide (with Ray Tune & W&B)

> **Source**: [Ultralytics Hyperparameter Tuning](https://docs.ultralytics.com/guides/hyperparameter-tuning/) & [Ray Tune Integration](https://docs.ultralytics.com/integrations/ray-tune/)

---

## Execution Environments & Tuning Methods

Before diving into advanced integrations, it's important to understand *how* and *where* tuning happens:

- **Local/Cloud Execution**: You must run the tuning script using the `ultralytics` Python library on your own infrastructure (such as a local workstation GPU or a cloud instance like AWS/GCP). Using the default `model.tune()` method automates the hyperparameter search using built-in **genetic algorithms**, slowly mutating parameters over multiple iterations to maximize mAP.
- **Platform Integration**: While the tuning iterations physically run on your own hardware, you can leverage the Ultralytics Platform to manage your custom datasets (via `ul://` URIs) and visually track the resulting experiments once they are uploaded.
- **Advanced Tuning**: For large-scale optimization, genetic algorithms can be slow. You can accelerate tuning by integrating **Ray Tune**, which interfaces with YOLO26 to provide advanced search strategies (like Bayesian optimization) and run multiple trials in parallel.

---

## Ray Tune Integration Overview

Hyperparameter tuning is a critical step to achieve the highest possible accuracy (mAP) for your custom YOLO26 models. Running a grid search or genetic algorithm manually can be very slow. 

Ultralytics integrates directly with **Ray Tune**, a highly efficient library built specifically for distributed hyperparameter optimization. Ray Tune offers:
- **Parallelism**: Run multiple training instances at the same time.
- **Advanced Search**: Bayesian Optimization, HyperOpt, etc.
- **Early Stopping (ASHA)**: Quickly kill unpromising tuning runs to save GPU hours.

By integrating **Weights & Biases (W&B)** into this pipeline, you can visually monitor all of these parallel tuning runs in real-time on a single, beautiful dashboard.

---

## Prerequisites & Installation

To use Ray Tune and log the results to W&B, you must have both libraries installed in your environment:

```bash
# Install Ultralytics with Ray Tune support
pip install -U ultralytics "ray[tune]"

# Install Weights & Biases for experiment tracking
pip install wandb
```

---

## Integrating W&B with YOLO Tuning

Integrating W&B into your tuning script is incredibly simple. You simply need to login to W&B and initialize a project run **before** you call the YOLO `.tune()` method.

Here is the complete workflow:

```python
import wandb
from ultralytics import YOLO

# 1. Initialize Weights & Biases
# This creates a project and prepares W&B to listen to the incoming Ray Tune logs
wandb.init(project="YOLO26-Tuning-Project", entity="your-wandb-username")

# 2. Load the base YOLO26 model
model = YOLO("yolo26n.pt")

# 3. Start tuning
# By setting use_ray=True, Ray Tune takes over the search process.
# W&B automatically captures the metrics from Ray Tune!
result_grid = model.tune(
    data="your_dataset.yaml", 
    epochs=30,               # Keep epochs low for tuning iterations
    use_ray=True,            # CRITICAL: Enables Ray Tune
    iterations=50            # Number of hyperparameter combinations to try
)
```

### What You Will See in W&B
Once you run the script above:
1. W&B will generate a live dashboard link in your terminal.
2. The dashboard will show a **Parallel Coordinates Plot**, which maps every single hyperparameter (learning rate, momentum, etc.) to the final accuracy metric.
3. You can visually identify which parameter ranges yield the best results and use those for your final training run!

---

## Advanced Usage: Custom Search Spaces

By default, Ray Tune searches over a predefined range of standard YOLO hyperparameters (e.g., `lr0` from `1e-5` to `1e-2`). 

If you want to restrict the search space or tune specific parameters (like focusing solely on data augmentation parameters or learning rates), you can pass a custom dictionary.

```python
import wandb
from ray import tune
from ultralytics import YOLO

wandb.init(project="YOLO26-Tuning-Project")

model = YOLO("yolo26n.pt")

# Define exactly what you want Ray Tune to explore
custom_search_space = {
    "lr0": tune.loguniform(1e-5, 1e-2),     # Learning rate on a log scale
    "momentum": tune.uniform(0.7, 0.98),    # Standard uniform distribution
    "degrees": tune.uniform(0.0, 45.0)      # Image rotation augmentation
}

# Run tuning using only the custom search space
result_grid = model.tune(
    data="your_dataset.yaml", 
    space=custom_search_space, 
    epochs=50, 
    use_ray=True
)
```

---

## Resuming an Interrupted Tuning Run

Tuning takes a long time and might crash or be interrupted. Ray Tune makes it easy to resume from exactly where it left off without losing progress:

```python
from ultralytics import YOLO

model = YOLO("yolo26n.pt")

# Include resume=True and pass the EXACT SAME arguments you passed originally
results = model.tune(
    data="your_dataset.yaml", 
    epochs=50, 
    use_ray=True, 
    resume=True
)
```

## Summary Checklist

1. ✅ Install `ray[tune]` and `wandb`.
2. ✅ Run `wandb login` in your terminal to authenticate.
3. ✅ Call `wandb.init()` in your Python script.
4. ✅ Add `use_ray=True` to `model.tune()`.
