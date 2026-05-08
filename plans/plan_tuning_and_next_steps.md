# Hyperparameter Tuning Analysis + Next Steps Plan

## Part 1: Conceptual Answers

### What is a Trial? What is a Run?

- **Trial**: one single hyperparameter evaluation. Ray Tune picks a set of params (e.g., lr0=0.003, momentum=0.85), trains the model with those params, measures mAP, and reports back. Each unique param combo = 1 trial.
- **Run**: the entire tuning job. 50 trials = 1 run. In W&B, each trial appears as a separate "run" in the dashboard, which is confusing — W&B uses "run" to mean what Ray calls "trial".

### Random Search vs Bayesian Optimization vs TPE

```
Random Search
  └─ picks hyperparams randomly, no memory of past results
  └─ simple, embarrassingly parallel, but wasteful

Bayesian Optimization (the family)
  └─ learns from past trial results to pick smarter next params
  └─ "Bayesian" because it updates a belief (posterior) about which regions are good
  └─ Multiple implementations:
       ├─ Gaussian Process (GP-based) — classic, expensive for high dimensions
       └─ TPE (Tree-structured Parzen Estimator) — HyperOpt's default

TPE specifically:
  └─ splits past results into "good" (top 20%) and "bad" (bottom 80%)
  └─ builds two density models: l(x) for good params, g(x) for bad params
  └─ picks next params where l(x)/g(x) is highest (Expected Improvement)
  └─ it IS Bayesian — it updates beliefs based on observed data
  └─ but it models p(x|y) instead of p(y|x) like GP-based methods
```

**Answer to your confusion**: HyperOpt uses TPE. TPE IS a Bayesian optimization method. The "randomize search" phrasing from Google AI was misleading — TPE is informed/guided search, not random. HyperOpt also offers a plain Random Search option, but TPE is the default and recommended one.

Source: [TPE as Bayesian Optimization](https://albertuskelvin.github.io/posts/2020/12/tree-structured-parzen-estimator-bayesian-optimization/)

### Knowledge Distillation — What Cường Did

**The logits vs probability vs features problem:**

```
Raw image
  → CNN backbone extracts FEATURES (spatial maps, patterns)
    → Head produces LOGITS (raw unnormalized scores per class)
      → Softmax converts to PROBABILITIES (0-1, sum to 1)
```

The problem you identified correctly:
- Features contain rich spatial/structural info about objects
- By the time you reach logits/probabilities, that spatial info is compressed into class scores
- You're NOT learning "how the teacher sees features" — you're learning "what the teacher thinks the answer is"

**Why logits with MSE loss, not probabilities with KL divergence?**

Logits preserve the raw scale of the teacher's confidence. Example:
- Teacher logits: [8.2, 1.5, 0.3, -2.1] for [car, bus, truck, motor]
- After softmax: [0.97, 0.012, 0.003, 0.003]

The logits tell the student: "car is dominant, but bus has SOME signal (1.5 is meaningful)". Probabilities crush this nuance into 0.97 vs 0.01.

MSE on logits directly matches these raw scales. Research shows MSE loss outperforms KL divergence for this reason.

Source: [KL vs MSE for Knowledge Distillation](https://ritvik19.medium.com/papers-explained-381-kl-divergence-vs-mse-for-knowledge-distillation-97988e80de3e)

**Why Cường chose YOLOv8m (medium) as teacher, not YOLOv8x (extra-large):**

The "capacity gap problem" — a teacher that's too strong relative to the student creates outputs the student physically cannot mimic. Research (ICCV 2019) proved that larger/more accurate teachers do NOT always produce better students. A medium teacher (YOLOv8m) is close enough in capacity to YOLOv8n that the student can actually learn from it.

Source: [On the Efficacy of Knowledge Distillation (ICCV 2019)](https://openaccess.thecvf.com/content_ICCV_2019/papers/Cho_On_the_Efficacy_of_Knowledge_Distillation_ICCV_2019_paper.pdf)

**Why prune THEN distill, not distill THEN prune?**

Think of it like brain surgery:
- Prune first = remove the unimportant neurons, make the model smaller
- THEN distill = teach this pruned model to recover accuracy using teacher guidance
- If you distill first (student learns from teacher), then prune the student — you destroy the carefully learned knowledge

Pruning damages accuracy. Distillation repairs it. Order matters: damage → repair, not repair → damage.

### Hyperparameter Tuning — Is It Useless Now?

You're right that with <5000 clean images, hyperparameter tuning has diminishing returns. The model can't learn robust patterns from limited data no matter what lr0 you pick. Priority should be:
1. Get more/cleaner data
2. Knowledge distillation (improve the model itself)
3. THEN tune hyperparameters on the improved setup


## Part 2: W&B Logging Issue in hyperparametertuning.py

### Root Cause

When `model.tune(use_ray=True)` is used, Ray Tune spawns **separate worker processes** for each trial. The `wandb.init()` in the main notebook process does NOT propagate to worker processes. Each Ray worker is a fresh Python process that never calls `wandb.init()`.

Known Ultralytics issues confirm this:
- W&B run names don't match local trial names ([Issue #23000](https://github.com/ultralytics/ultralytics/issues/23000))
- Project directory not respected with `use_ray=True` ([Issue #17473](https://github.com/ultralytics/ultralytics/issues/17473))
- Hyperparameters were completely ignored in some versions ([Issue #23791](https://github.com/ultralytics/ultralytics/issues/23791), fixed in 8.4.19+)

### Fix Options

1. **Upgrade ultralytics** to latest (8.4.19+) where these bugs are fixed
2. **Use Ray Tune's W&B integration** instead of Ultralytics' — set `WANDB_API_KEY` as env var and Ray workers will auto-detect it
3. **Switch to hyperparametertuning2.py approach** where you control the training loop and can init W&B per worker

The real answer: the W&B `wandb.init()` call in the main process ran fine (you saw the `[DEBUG] W&B initialized` message). But each Ray Tune worker process doesn't inherit that session. Ultralytics internally may or may not re-init W&B per worker depending on version.


## Part 3: Fixes for hyperparametertuning2.py

### Bugs to Fix

| Bug | Line | Fix |
|-----|------|-----|
| `"pi"` instead of `"pip"` | L16 | Change to `"pip"` |
| No env var validation | L31-33 | Add ValueError checks like file 1 |
| No GPU debug info | L26-28 | Add GPU name/memory logging |
| `wandb.login()` but no `wandb.init()` | L40 | Add `wandb.init(project=...)` |
| No W&B init inside `train_yolo` | L49 | Workers need W&B env var set |
| Loading new model every trial | L51 | Acceptable — Ray workers are separate processes, model MUST be loaded fresh |
| `model.train` returns `Results` object | L54 | Verify `.results_dict` exists on the return type |
| `train.report` only called once at end | L67 | ASHA needs per-epoch reporting to do early stopping — currently broken |
| No `batch` in YOLO train kwargs validation | L72 | `batch` is valid for `model.train()` |

### Critical Issue: ASHA Early Stopping is Broken

ASHA (`grace_period=3`) expects `train.report()` to be called **every epoch**, not just at the end. Currently `train_yolo` calls `train.report()` once after all 10 epochs complete. This means ASHA never gets intermediate metrics and cannot early-stop bad trials.

Fix: use Ultralytics callbacks to report per-epoch, OR use `model.train(epochs=1)` in a loop.

### "Each trial loads a new model — is that bad?"

No, it's correct. Ray workers are separate processes. They don't share memory. Each worker MUST load its own model. This is how Ray Tune works. The model file (yolo26n.pt, ~5MB) loads in <1 second — not a bottleneck.

### "Custom metric key map50_95 — bad for RAM?"

No. It's just a string key in a dictionary. Has zero RAM impact. The custom key is fine — it's just a naming choice.


## Part 4: Jetson Nano Deployment Reality Check

### Hardware Constraints

| Spec | Jetson Nano |
|------|-------------|
| GPU | 128 CUDA cores, Maxwell |
| RAM | 4 GB shared CPU+GPU |
| CUDA | 10.2 |
| Ubuntu | **18.04 only** (official) |
| JetPack | 4.x only |
| DeepStream | 5.0 or 6.0.1 |

### DeepStream on Nano — Will It Work?

**Problem 1: OS mismatch.** Cường's setup uses Ubuntu 20.04 + Python 3.8 from a Chinese repo. Official Jetson Nano only supports Ubuntu 18.04 + Python 3.6. These are incompatible — you cannot run JetPack 4 on Ubuntu 20.04.

Source: [NVIDIA Developer Forums](https://forums.developer.nvidia.com/t/upgrade-from-ubuntu-18-04-to-22-04-or-20-4/282531)

**Problem 2: Resource overhead.** DeepStream adds GStreamer pipeline overhead. On 4GB RAM with 128 cores, this may leave insufficient memory for the model. DeepStream is designed for Orin-class devices (8-64GB).

**Problem 3: Cường's C++ CUDA inference.** A custom C++ inference binary with direct CUDA calls has MUCH less overhead than DeepStream's full pipeline. For Nano, this is likely the better approach.

### Recommendation

```
DON'T: Try to install DeepStream on the current Ubuntu 20.04 Nano setup
DON'T: Reflash to Ubuntu 18.04 just for DeepStream (you'd lose Cường's setup)

DO: Keep Cường's C++ CUDA inference on Nano
DO: Focus on improving the MODEL (distillation, pruning) rather than the RUNTIME
DO: Test lower imgsz (320, 416) to find speed/accuracy sweet spot
DO: Export ONNX here, rebuild TensorRT on Nano
```


## Part 5: What To Do Next (Priority Order)

### Immediate (this session)

- [ ] Fix hyperparametertuning2.py bugs (pip typo, env validation, ASHA reporting)
- [ ] Add multi-resolution test cells to test.ipynb (imgsz=320, 416, 640 comparison)
- [ ] Add ONNX export with opset=12 for Nano/DeepStream compatibility

### Short-term (next sessions)

- [ ] Investigate W&B logging: upgrade ultralytics, re-run a small tuning test (5 iterations) to verify logging works
- [ ] If data is still <5000 images: skip full hyperparameter tuning, focus on distillation
- [ ] Improve knowledge distillation: experiment with MSE loss on logits vs KL divergence

### Medium-term (project milestones)

- [ ] Test best.pt at imgsz=320 and 416 on actual Nano hardware via Cường's C++ pipeline
- [ ] Compare: current C++ CUDA inference vs TensorRT engine on Nano
- [ ] Build monitoring dashboard/frontend for inference results
- [ ] If Nano is too slow even at 320: consider upgrading to Orin Nano ($200) where DeepStream works properly
