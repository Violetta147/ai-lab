# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  YOLO26n — STRUCTURED PRUNING V2 (FIX modelopt_state)                      ║
# ║  Mục tiêu: Tạo file best.pt có đầy đủ modelopt metadata                   ║
# ║  Để chạy trên Google Colab: copy từng phần vào các cell riêng biệt         ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
#
# THAY ĐỔI SO VỚI Yolo26n_pruning.ipynb (V1):
# ┌─────────────────────────────────────────────────────────────────────────────┐
# │ [FIX CHÍNH] Dùng mto.save() để lưu modelopt state thay vì getattr()      │
# │ [FIX 2]     Lưu cả state_dict lẫn modelopt_state vào cùng checkpoint     │
# │ [FIX 3]     Thêm key "modelopt_state" thay vì "modelopt_config"          │
# │ [GIỮ]       Logic PrunedTrainer, collect_func, score_func giống V1       │
# │ [GIỮ]       FLOPs target 91%, batch 32, YOLO26n architecture             │
# └─────────────────────────────────────────────────────────────────────────────┘

# ==============================================================================
# CELL 0: CÀI ĐẶT MÔI TRƯỜNG
# ==============================================================================
# !pip install -U ultralytics nest_asyncio -q
# !pip install nvidia-modelopt==0.37.0 torchprofile==0.0.4 -q
# !pip install torch==2.8.0 torchvision==0.23.0 --ignore-installed -q

# ==============================================================================
# CELL 1: MOUNT GOOGLE DRIVE
# ==============================================================================
# from google.colab import drive
# drive.mount('/content/drive')

# ==============================================================================
# CELL 2: PRUNING + FINE-TUNING (CELL CHÍNH)
# ==============================================================================
import os
import io
import math
import torch
import torch.optim as torch_optim
from datetime import datetime

import nest_asyncio
nest_asyncio.apply()

from ultralytics import YOLO, hub, __version__
from ultralytics.engine.trainer import BaseTrainer
from ultralytics.models.yolo.detect.train import DetectionTrainer
from ultralytics.utils.torch_utils import ModelEMA, one_cycle
from ultralytics.utils import LOGGER
import modelopt.torch.prune as mtp
import modelopt.torch.opt as mto

# ══════════════════════════════════════════════════════════════════
# CONFIG — Chỉnh sửa các giá trị này theo nhu cầu
# ══════════════════════════════════════════════════════════════════
API_KEY      = "ul_58eaafc88c4778e76e600ce593c552699002a468"
MODEL_PATH   = "/content/drive/MyDrive/Traffic_AI_Project/YOLO26n_Traffic_Native/weights/best.pt"
OUTPUT_DIR   = "/content/drive/MyDrive/Traffic_AI_Project"
OUTPUT_NAME  = "YOLO26n_Pruned_Elegant"
DATASET_URI  = "ul://violet/datasets/work3yolov8"

PRUNE_FLOPS  = "91%"              # Giữ lại 91% FLOPs (cắt 9%)
CALIBRATION_BATCHES = 16           # Số batch cho ModelOpt phân tích
EPOCHS       = 100
BATCH_SIZE   = 32


# ══════════════════════════════════════════════════════════════════
# BƯỚC 1: OVERRIDE CƠ CHẾ LƯU — DÙNG mto.save() ĐÚNG CÁCH
# ══════════════════════════════════════════════════════════════════
def custom_save_model(self):
    """
    Ghi đè save_model để lưu modelopt_state đúng cách.
    
    ĐÂY LÀ SỰ KHÁC BIỆT DUY NHẤT SO VỚI V1:
    V1: getattr(self.model, "modelopt_config", None)  → None (SAI!)
    V2: mto.save(self.model, buf)                     → bytes đầy đủ (ĐÚNG!)
    """
    # Serialize modelopt state vào BytesIO buffer
    buf = io.BytesIO()
    mto.save(self.model, buf)
    buf.seek(0)
    modelopt_state_bytes = buf.read()
    
    ckpt = {
        "epoch":             self.epoch,
        "best_fitness":      self.best_fitness,
        "model":             self.model.state_dict(),
        "ema":               self.ema.ema.state_dict() if self.ema else None,
        "updates":           self.ema.updates if self.ema else 0,
        "optimizer":         self.optimizer.state_dict(),
        "train_args":        vars(self.args),
        "train_metrics":     getattr(self, "metrics", {}),
        "train_results":     getattr(self, "results", {}),
        "date":              datetime.now().isoformat(),
        "version":           __version__,

        # ╔═══════════════════════════════════════════════════════╗
        # ║  FIX CHÍNH: Dùng mto.save() thay vì getattr()       ║
        # ║  Key "modelopt_state" khớp với export_pruned_yolov8  ║
        # ╚═══════════════════════════════════════════════════════╝
        "modelopt_state":    modelopt_state_bytes,
        
        # Giữ yaml_config để fallback nếu cần
        "yaml_config":       getattr(self.model, "yaml", None),
    }

    torch.save(ckpt, self.last)
    if self.best_fitness == self.fitness:
        torch.save(ckpt, self.best)
    if (self.save_period > 0) and (self.epoch > 0) and (self.epoch % self.save_period == 0):
        torch.save(ckpt, self.wdir / f"epoch{self.epoch}.pt")

BaseTrainer.save_model = custom_save_model
print("✅ [Bước 1] Đã override save_model với mto.save() (V2 — Fixed!)")


# ══════════════════════════════════════════════════════════════════
# BƯỚC 2: PRUNED TRAINER
# ══════════════════════════════════════════════════════════════════
class PrunedTrainer(DetectionTrainer):
    """
    Custom Trainer tích hợp NVIDIA ModelOpt Structured Pruning.
    Pattern lấy từ Untitled14.ipynb (đã chạy thành công với yolov8n).
    """

    def _setup_train(self, *args, **kwargs):
        super()._setup_train(*args, **kwargs)

        # Lách cơ chế fuse của Ultralytics (ModelOpt cần graph nguyên vẹn)
        self.model.is_fused = lambda: True
        self.model.fuse = lambda *a, **kw: self.model

        print("\n" + "=" * 65)
        print("⏳ [Bước 2] NVIDIA ModelOpt — Structured Pruning")
        print(f"   🎯 Target: Giữ {PRUNE_FLOPS} FLOPs")

        params_before = sum(p.numel() for p in self.model.parameters())
        print(f"   📊 Params trước prune: {params_before:,}")

        # Thu thập dữ liệu Calibration
        def collect_func(batch):
            return batch["img"].to(self.device, non_blocking=True).float() / 255.0

        # Đánh giá Mạng con (Subnet)
        def score_func(model):
            self.validator.args.save = False
            self.validator.args.plots = False
            self.validator.args.verbose = False
            self.validator.is_coco = False
            model.eval()
            metrics = self.validator(model=model)
            model.train()
            return metrics["fitness"] if isinstance(metrics, dict) else metrics.box.map50

        print("   🔍 Đang trace model graph và tìm Subnet tối ưu...")
        dummy_input = torch.zeros(1, 3, self.args.imgsz, self.args.imgsz, device=self.device)

        # Kích hoạt FastNAS
        self.model, prune_res = mtp.prune(
            self.model,
            mode="fastnas",
            constraints={"flops": PRUNE_FLOPS},
            dummy_input=dummy_input,
            config={
                "score_func": score_func,
                "data_loader": self.train_loader,
                "collect_func": collect_func,
                "max_iter_data_loader": CALIBRATION_BATCHES,
            }
        )

        print(f"   ✅ Hoàn tất FastNAS! Kết quả: {prune_res}")

        # Thống kê sau cắt tỉa
        params_after = sum(p.numel() for p in self.model.parameters())
        print(f"   📊 Params sau prune: {params_after:,} (↓{(1 - params_after/params_before)*100:.1f}%)")

        # Reset EMA + Optimizer + Scheduler (pattern từ Untitled14.ipynb)
        self.model.to(self.device)
        self.ema = ModelEMA(self.model)

        weight_decay = self.args.weight_decay * self.batch_size * self.accumulate / self.args.nbs
        iterations = math.ceil(len(self.train_loader.dataset) / max(self.batch_size, self.args.nbs)) * self.epochs
        self.optimizer = self.build_optimizer(
            model=self.model,
            name=self.args.optimizer,
            lr=self.args.lr0,
            momentum=self.args.momentum,
            decay=weight_decay,
            iterations=iterations,
        )
        self._setup_scheduler()

        print("✅ [Bước 2] Pruning & Setup hoàn tất! Bắt đầu Fine-tuning...\n")
        print("=" * 65 + "\n")


# ══════════════════════════════════════════════════════════════════
# BƯỚC 3: CẤU HÌNH TRAINING & CHẠY
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    os.environ["ULTRALYTICS_API_KEY"] = API_KEY
    hub.login(API_KEY)

    model = YOLO(MODEL_PATH)

    print("🚀 [Bước 3] Khởi động PrunedTrainer V2 (Fixed mto.save)...")
    model.train(
        data      = DATASET_URI,
        trainer   = PrunedTrainer,
        epochs    = EPOCHS,
        imgsz     = 640,
        batch     = BATCH_SIZE,
        optimizer = "MuSGD",
        device    = 0,
        workers   = 8,
        cache     = True,
        patience  = 50,
        save      = True,
        plots     = True,
        augment   = True,
        project   = OUTPUT_DIR,
        name      = OUTPUT_NAME,
        exist_ok  = True,
    )
    print("✅ [Bước 3] Fine-tuning hoàn tất!")


# ==============================================================================
# CELL 3: VALIDATION (Chạy sau khi train xong)
# ==============================================================================
# from ultralytics import YOLO
# 
# PRUNED_BEST = "/content/drive/MyDrive/Traffic_AI_Project/YOLO26n_Pruned_V2/weights/best.pt"
# model = YOLO(PRUNED_BEST)
# metrics = model.val(data="ul://violet/datasets/work3yolov8", device=0)
# print(f"mAP50: {metrics.box.map50:.4f}")
# print(f"mAP50-95: {metrics.box.map:.4f}")


# ==============================================================================
# CELL 4: EXPORT ONNX (Chạy sau khi validation OK)
# ==============================================================================
# from ultralytics import YOLO
#
# PRUNED_BEST = "/content/drive/MyDrive/Traffic_AI_Project/YOLO26n_Pruned_V2/weights/best.pt"
# model = YOLO(PRUNED_BEST)
# model.export(format="onnx", imgsz=640, simplify=True, opset=12, dynamic=False)
# print("✅ ONNX exported!")


# ==============================================================================
# CELL 5: KIỂM TRA CHECKPOINT CÓ MODELOPT_STATE KHÔNG (Debug)
# ==============================================================================
# import torch
# ckpt = torch.load(PRUNED_BEST, map_location="cpu", weights_only=False)
# print("Keys:", list(ckpt.keys()))
# print("modelopt_state:", type(ckpt.get("modelopt_state")))
# print("Has modelopt_state:", ckpt.get("modelopt_state") is not None)
# # ← Phải in ra: Has modelopt_state: True
