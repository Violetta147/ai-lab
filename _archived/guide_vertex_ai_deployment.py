# %% [markdown]
# # Deploy YOLO26 on Google Cloud Vertex AI with Docker
# Source: https://docs.ultralytics.com/guides/vertex-ai-deployment-with-docker/
#
# This guide covers containerizing a pretrained YOLO26 model with Ultralytics,
# building a FastAPI inference server, and deploying it on Vertex AI.
#
# ## What You Will Learn
# 1. Create an inference backend for YOLO26 using FastAPI
# 2. Create a GCP Artifact Registry repository for Docker images
# 3. Build and push the Docker image to Artifact Registry
# 4. Import the model in Vertex AI
# 5. Create a Vertex AI endpoint and deploy the model
#
# ## Prerequisites
# - Docker installed locally
# - Google Cloud SDK installed and authenticated (`gcloud` CLI)
# - Familiarity with Ultralytics Docker images

# %% [markdown]
# ## 1. Vertex AI Compliance
#
# Vertex AI requires two specific endpoints:
# - **Health** (`/health`): returns HTTP 200 OK when service is ready
# - **Predict** (`/predict`): accepts base64-encoded images with optional parameters
#
# Request payload format:
# ```json
# {
#     "instances": [{"image": "base64_encoded_image"}],
#     "parameters": {"confidence": 0.5}
# }
# ```
#
# ## Project Folder Structure
# ```
# YOUR_PROJECT/
# +-- src/
# |   +-- __init__.py
# |   +-- app.py              # Core YOLO26 inference logic
# |   +-- main.py             # FastAPI inference server
# +-- tests/
# +-- .env
# +-- Dockerfile
# +-- LICENSE                 # AGPL-3.0 License
# +-- pyproject.toml
# ```

# %% Core Inference Logic (src/app.py)
import io
from typing import Any, Dict

from PIL import Image
from ultralytics import YOLO

model_yolo: YOLO | None = None
_model_ready: bool = False


def _initialize_model() -> None:
    """Initialize the YOLO model."""
    global model_yolo, _model_ready
    try:
        model_yolo = YOLO("yolo26n.pt")
        _model_ready = True
        print("[DEBUG] YOLO model initialized successfully")
    except Exception as e:
        print(f"[ERROR] Error initializing YOLO model: {e}")
        _model_ready = False
        model_yolo = None


_initialize_model()


def is_model_ready() -> bool:
    """Check if the model is ready for inference."""
    return _model_ready and model_yolo is not None


def get_image_from_bytes(binary_image: bytes) -> Image.Image:
    """Convert image from bytes to PIL RGB format."""
    return Image.open(io.BytesIO(binary_image)).convert("RGB")


def get_bytes_from_image(image: Image.Image) -> bytes:
    """Convert PIL image to bytes."""
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    buffer.seek(0)
    return buffer.getvalue()


def run_inference(input_image: Image.Image, confidence_threshold: float = 0.5) -> Dict[str, Any]:
    """Run inference on an image using YOLO26n model."""
    global model_yolo

    if not is_model_ready():
        print("[ERROR] Model not ready for inference")
        return {"detections": [], "results": None}

    try:
        results = model_yolo.predict(
            imgsz=640,
            source=input_image,
            conf=confidence_threshold,
            save=False,
            augment=False,
            verbose=False,
        )

        detections: list[Dict[str, Any]] = []
        if results and len(results) > 0:
            result = results[0]
            if result.boxes is not None and len(result.boxes.xyxy) > 0:
                boxes = result.boxes
                xyxy = boxes.xyxy.cpu().numpy()
                conf = boxes.conf.cpu().numpy()
                cls = boxes.cls.cpu().numpy().astype(int)

                for i in range(len(xyxy)):
                    detection: Dict[str, Any] = {
                        "xmin": float(xyxy[i][0]),
                        "ymin": float(xyxy[i][1]),
                        "xmax": float(xyxy[i][2]),
                        "ymax": float(xyxy[i][3]),
                        "confidence": float(conf[i]),
                        "class": int(cls[i]),
                        "name": model_yolo.names.get(int(cls[i]), f"class_{int(cls[i])}"),
                    }
                    detections.append(detection)

        print(f"[DEBUG] Inference complete: {len(detections)} detections")
        return {"detections": detections, "results": results}
    except Exception as e:
        print(f"[ERROR] Error in YOLO detection: {e}")
        return {"detections": [], "results": None}


def get_annotated_image(results: list) -> Image.Image:
    """Get annotated image using Ultralytics built-in plot method."""
    if not results or len(results) == 0:
        raise ValueError("No results provided for annotation")
    return results[0].plot(pil=True)

# %% Test Inference Locally
from PIL import Image as PILImage

print("[DEBUG] Testing local inference...")
test_img = PILImage.new("RGB", (640, 640), color=(128, 128, 128))
test_result = run_inference(test_img, confidence_threshold=0.25)
print(f"[DEBUG] Test result: {len(test_result['detections'])} detections on blank image (expected 0)")

# %% [markdown]
# ## 2. FastAPI Inference Server (src/main.py)
#
# The server implements Vertex AI-required endpoints:
# - `GET /health` — returns 200 when model is ready, 503 otherwise
# - `POST /predict` — accepts base64-encoded images, returns detections

# %% FastAPI Server Code
import base64
import os
from typing import Optional

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

AIP_HTTP_PORT: int = int(os.getenv("AIP_HTTP_PORT", "8080"))
AIP_HEALTH_ROUTE: str = os.getenv("AIP_HEALTH_ROUTE", "/health")
AIP_PREDICT_ROUTE: str = os.getenv("AIP_PREDICT_ROUTE", "/predict")

print(f"[DEBUG] Vertex AI config: port={AIP_HTTP_PORT}, health={AIP_HEALTH_ROUTE}, predict={AIP_PREDICT_ROUTE}")


class PredictionRequest(BaseModel):
    instances: list
    parameters: Optional[Dict[str, Any]] = None


class PredictionResponse(BaseModel):
    predictions: list


app = FastAPI(title="YOLO26 Vertex AI Inference")


@app.get(AIP_HEALTH_ROUTE, status_code=status.HTTP_200_OK)
def health_check() -> Dict[str, str]:
    """Health check endpoint for Vertex AI."""
    if not is_model_ready():
        raise HTTPException(status_code=503, detail="Model not ready")
    return {"status": "healthy"}


@app.post(AIP_PREDICT_ROUTE, response_model=PredictionResponse)
async def predict(request: PredictionRequest) -> PredictionResponse:
    """Prediction endpoint for Vertex AI."""
    try:
        predictions: list[Dict[str, Any]] = []

        for instance in request.instances:
            if not isinstance(instance, dict) or "image" not in instance:
                raise HTTPException(status_code=400, detail="Instance must contain 'image' field")

            image_data: bytes = base64.b64decode(instance["image"])
            input_image: PILImage.Image = get_image_from_bytes(image_data)

            parameters: Dict[str, Any] = request.parameters or {}
            confidence_threshold: float = parameters.get("confidence", 0.5)
            return_annotated: bool = parameters.get("return_annotated_image", False)

            result = run_inference(input_image, confidence_threshold=confidence_threshold)

            detections: list[Dict[str, Any]] = []
            for det in result["detections"]:
                detections.append({
                    "class": det["name"],
                    "confidence": det["confidence"],
                    "bbox": {
                        "xmin": det["xmin"],
                        "ymin": det["ymin"],
                        "xmax": det["xmax"],
                        "ymax": det["ymax"],
                    },
                })

            prediction: Dict[str, Any] = {
                "detections": detections,
                "detection_count": len(detections),
            }

            if return_annotated and result["results"]:
                annotated = get_annotated_image(result["results"])
                img_bytes = get_bytes_from_image(annotated)
                prediction["annotated_image"] = base64.b64encode(img_bytes).decode("utf-8")

            predictions.append(prediction)

        return PredictionResponse(predictions=predictions)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {e}")


print("[DEBUG] FastAPI app defined with health and predict endpoints")

# %% [markdown]
# ## 3. Dockerfile
#
# ```dockerfile
# FROM ultralytics/ultralytics:latest
#
# ENV PYTHONUNBUFFERED=1 \
#     PYTHONDONTWRITEBYTECODE=1
#
# RUN uv pip install fastapi[all] uvicorn[standard] loguru
#
# WORKDIR /app
# COPY src/ ./src/
# COPY pyproject.toml ./
# RUN uv pip install -e .
# RUN mkdir -p /app/logs
# ENV PYTHONPATH=/app/src
#
# EXPOSE 8080
# ENTRYPOINT ["python", "src/main.py"]
# ```
#
# ## Build and Test
# ```bash
# # Build (must target linux/amd64 for Vertex AI)
# docker build --platform linux/amd64 -t yolo26-fastapi:0.1 .
#
# # Run locally
# docker run --platform linux/amd64 -p 8080:8080 yolo26-fastapi:0.1
#
# # Test health
# curl http://localhost:8080/health
#
# # Test predict (macOS/Linux)
# curl -X POST -H "Content-Type: application/json" \
#   -d "{\"instances\": [{\"image\": \"$(base64 -i tests/test_image.jpg)\"}]}" \
#   http://localhost:8080/predict
# ```

# %% [markdown]
# ## 4. Upload to GCP Artifact Registry
#
# ```bash
# # Authenticate Docker to Artifact Registry
# gcloud auth configure-docker YOUR_REGION-docker.pkg.dev
#
# # Tag the image
# docker tag yolo26-fastapi:0.1 \
#   YOUR_REGION-docker.pkg.dev/YOUR_PROJECT_ID/YOUR_REPO/yolo26-fastapi:0.1
#
# # Push
# docker push YOUR_REGION-docker.pkg.dev/YOUR_PROJECT_ID/YOUR_REPO/yolo26-fastapi:0.1
# ```

# %% [markdown]
# ## 5. Import Model in Vertex AI
#
# 1. Go to **Vertex AI > Model Registry** in GCP Console
# 2. Click **Import** > **Import as a new model**
# 3. Select region matching your Artifact Registry
# 4. Choose **Import an existing model container**
# 5. Browse and select your pushed image
# 6. Set environment variables:
#    - `AIP_HEALTH_ROUTE` = `/health`
#    - `AIP_PREDICT_ROUTE` = `/predict`
#    - `AIP_HTTP_PORT` = `8080`
# 7. Click **Import**

# %% [markdown]
# ## 6. Create Endpoint and Deploy
#
# 1. Go to **Vertex AI > Endpoints** > **Create**
# 2. Name the endpoint, choose private access (recommended for higher payload limits)
# 3. Select the imported model, configure machine type and GPU (start with NVIDIA T4)
# 4. Click **Create** and wait for deployment (~30 min)
#
# ## 7. Test Deployed Model
#
# ```bash
# curl -X POST \
#   -H "Authorization: Bearer $(gcloud auth print-access-token)" \
#   -H "Content-Type: application/json" \
#   -d "{\"instances\": [{\"image\": \"$(base64 -i tests/test_image.jpg)\"}]}" \
#   https://REGION-aiplatform.googleapis.com/v1/projects/PROJECT_ID/locations/REGION/endpoints/ENDPOINT_ID:predict
# ```
