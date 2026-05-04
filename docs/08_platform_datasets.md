# Ultralytics Platform Datasets

> **Source**: [Ultralytics Datasets Documentation](https://docs.ultralytics.com/platform/data/datasets/)

---

## Introduction

The [Ultralytics Platform](https://platform.ultralytics.com) provides a streamlined solution for managing, storing, and deploying your training data in the cloud. Datasets uploaded to the platform can be immediately used for model training, with automatic processing and statistics generation.

---

## Uploading a Dataset

### Supported Upload Formats

| Category | Supported File Types | Notes |
|---|---|---|
| **Images** | `.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`, `.tiff`, `.tif`, `.heic`, `.avif`, `.jp2`, `.dng`, `.mpo` | Min dimension: 28px. Resized if > 4096px. |
| **Videos** | `.mp4`, `.webm`, `.mov`, `.avi`, `.mkv`, `.m4v` | Auto-extracted to frames at 1 FPS (max 100 frames/video). |
| **Archives** | `.zip`, `.tar`, `.tar.gz`, `.tgz` | Extracted and processed automatically. |
| **Data Lists**| `.ndjson` | Ultralytics format for dataset snapshots. |

### Supported Annotation Formats

1. **Ultralytics YOLO Format** (`.txt` + `data.yaml`)
   * Uses flat `.txt` files containing normalized coordinates.
   * Dataset must include a `data.yaml` file defining classes and splits.
2. **COCO Format** (`.json`)
   * Uses the standard COCO JSON structure (`images`, `annotations`, `categories`).
   * Auto-converts absolute pixel coordinates to normalized representation.
3. **Raw (Unannotated)**
   * Images without any labels.
   * Useful when annotating directly on the platform.

### How to Upload

1. Navigate to **Datasets** in the platform sidebar.
2. Click **New Dataset** or drag-and-drop your files.
3. Select the computer vision **task type** (e.g., Detect, Segment, Pose).
4. Provide a name and optional description.
5. Set dataset **visibility** (public/private) and choose an optional license.
6. Click **Create**.

---

## Dataset Processing Pipeline

After uploading, the platform processes your data through the following pipeline:

1. **Validation**: Checks formats and sizes (minimum 28px).
2. **Normalization**: Large images >4096px are resized while preserving aspect ratio.
3. **Thumbnail Generation**: Creates 256px WebP previews for fast UI browsing.
4. **Label Parsing**: Extracts annotations from YOLO `.txt` or COCO `.json` files.
5. **Statistics**: Computes class distributions, image dimensions, and dataset health metrics.

---

## Dataset Features & Management

### The Dataset Tabs

A dataset page features six main tabs for interaction and analysis:

1. **Images**: View gallery with annotation overlays, use filters (e.g., "Unannotated"), and perform bulk actions.
2. **Classes**: View class distribution histograms, rename classes inline, and change class assign colors. Includes a logarithmic scale for imbalanced datasets.
3. **Charts**: Auto-generated statistics and heatmaps of annotation distributions across your dataset.
4. **Models**: Lists all trained machine learning models associated with the dataset.
5. **Errors**: Details on any files that failed processing, providing hints for fixes.
6. **Versions**: Create immutable `NDJSON` snapshots of your dataset to ensure reproducible training.

### Snapshot Versions
You can create an immutable `NDJSON` snapshot before or after major changes (e.g., adding labels). Each version captures class counts, annotation counts, and file sizes.

### Bulk Image Operations
From the table view, you can:
- **Move to Split**: Reassign images to Train, Validation, or Test splits.
- **Auto Split**: Automatically redistribute unassigned images across the train/val/test splits based on standard ratios.
- **Delete**: Remove images from the dataset in bulk.

---

## Using Platform Datasets (ul:// URI)

You can reference datasets stored on the Ultralytics Platform directly in your training code using the `ul://` URI scheme.

**Syntax:** `ul://username/datasets/dataset-name`

This allows you to train from anywhere — your local machine, Google Colab, or remote cloud servers — without manually downloading datasets.

### CLI Example
```bash
export ULTRALYTICS_API_KEY="YOUR_API_KEY"
yolo detect train model=yolo26n.pt data=ul://yourusername/datasets/my-dataset epochs=100
```

### Python Example
```python
from ultralytics import YOLO

# Set API key (or configure via `yolo settings`)
import os
os.environ["ULTRALYTICS_API_KEY"] = "YOUR_API_KEY"

model = YOLO("yolo26n.pt")
model.train(data="ul://yourusername/datasets/my-dataset", epochs=100)
```

---

## Storage & Export

### Content-Addressable Storage (CAS)
Ultralytics Platform uses CAS with XXH3-128 hashing:
- **Deduplication**: Identical images uploaded by different users are stored only once.
- **Data Integrity**: Cryptographic hashing ensures your data is exactly as uploaded.

### Exporting Datasets
You can export your platform dataset for offline local use.
1. Click **Export** in the top header.
2. Select your desired format (e.g., `.txt` YOLO format).
3. The export runs asynchronously, generating an NDJSON file with signed image URLs (valid for 7 days).

---

## Managing Your Platform Dataset

- **Change Task Type:** You can annotate the same dataset for multiple tasks. Switching the task type (e.g., from Detect to Segment) simply hides irrelevant labels; they are not deleted.
- **Licenses:** Supports copyleft licenses formatting. Cloned datasets inherit copyleft licenses.
- **Edit Inline:** Name, description, and task type can be edited by simply clicking them on the dataset page.
- **Trash & Restore:** Deleted datasets move to a Trash bin and can be restored within 30 days via `Settings > Trash`.
