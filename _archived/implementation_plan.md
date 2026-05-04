# 🎯 Model vs DeepStream — Giải thích & Kế hoạch nâng cấp

## Model vs DeepStream — Ai chịu trách nhiệm gì?

Từ screenshot demo, kết quả detection phụ thuộc vào **2 tầng** khác nhau:

### Tầng 1: Model (YOLOv8n FP16) — "Bộ não"

| Khía cạnh | Do Model quyết định | Cải thiện bằng |
|-----------|---------------------|----------------|
| **Detect được hay không** | ✅ Model quyết định | Train thêm data, dùng model lớn hơn |
| **Bbox chặt/lỏng** | ✅ Model quyết định | Train với augmentation tốt hơn |
| **Phân loại đúng/sai** (car vs truck) | ✅ Model quyết định | Thêm data đa dạng |
| **Detect vật nhỏ xa** | ✅ Model quyết định + `imgsz` | Train với imgsz lớn hơn (640→832) |

> **Không thể sửa bằng DeepStream config.** Phải retrain model.

### Tầng 2: DeepStream Pipeline — "Cơ thể"

| Khía cạnh | Do DeepStream quyết định | Cải thiện bằng |
|-----------|--------------------------|----------------|
| **Độ phân giải video output** | ✅ `streammux` width/height | Tăng lên 1280x720 ✅ |
| **Màu bbox, text size** | ✅ `[osd]` + `[class-attrs]` | Config per-class colors 🆕 |
| **Tracking ID liên tục** | ✅ Tracker algorithm | NvDCF thay IOU 🆕 |
| **Đếm xe qua vạch** | ✅ `nvdsanalytics` plugin | Line crossing counter 🆕 |
| **Lọc false positive** | ✅ `pre-cluster-threshold` | Tăng threshold per class |
| **Bitrate video** | ✅ `bitrate` trong `[sink0]` | Tăng 4-6 Mbps ✅ |

> **Có thể cải thiện NGAY bằng config!**

---

## Kế hoạch nâng cấp (v3)

### 1. 🎨 Màu bbox theo class (thay vì đỏ hết)

```
bus    → 🟢 Xanh lá (0;1;0;1)
car    → 🔵 Xanh dương (0;0.5;1;1)  
motor  → 🟡 Vàng (1;1;0;1)
truck  → 🔴 Đỏ (1;0;0;1)
```

Cách làm: Thay `[class-attrs-all]` bằng `[class-attrs-0]`, `[class-attrs-1]`, `[class-attrs-2]`, `[class-attrs-3]` riêng biệt.

### 2. 🔄 Nâng cấp Tracker: IOU → NvDCF Performance

| | IOU (hiện tại) | NvDCF Performance (mới) |
|---|---|---|
| **Chạy trên** | CPU | GPU (nhưng ta có headroom) |
| **Track khi bị che** | ❌ Mất ID | ✅ Giữ ID qua occlusion |
| **Track chính xác** | Thấp | Cao |
| **GPU cost** | 0% | ~10-15% (còn thừa ở 30 FPS) |

### 3. 📊 Đếm xe bằng Line Crossing (nvdsanalytics)

Thêm vạch đếm ảo trên video — mỗi xe đi qua vạch sẽ được đếm.

```
         ──────────── VẠCH ĐẾM ────────────
         ↓ xe đi qua = count+1
```

> [!IMPORTANT]
> Vị trí vạch cần điều chỉnh theo góc camera thực tế. Script sẽ tạo config mặc định có thể override.

### 4. 📝 OSD cải thiện

- Text lớn hơn (15→18px)
- Border dày hơn (3→4px)  
- Background text trong suốt hơn

---

## Thay đổi files

### [MODIFY] setup_deepstream_jetson.sh
- Per-class inference config với colors
- NvDCF tracker config
- nvdsanalytics config generation
- Env vars mới: `TRACKER_TYPE`, `ENABLE_ANALYTICS`

### [NEW] Tự tạo trong container:
- `config_nvdsanalytics.txt` — Line crossing / ROI config

---

## Dự đoán FPS sau nâng cấp

| Config | FPS dự kiến |
|--------|-------------|
| 720p + IOU + no analytics (hiện tại) | ~30 |
| **720p + NvDCF + analytics** (mới) | **~22-28** |
| 1080p + NvDCF + analytics (max quality) | ~15-20 |

> GPU headroom đang rất lớn (30 FPS capped bởi video 30fps). Thêm NvDCF + analytics vẫn dư sức.
