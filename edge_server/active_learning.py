from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import time

import cv2
import numpy as np
from ultralytics.engine.results import Results


@dataclass(frozen=True)
class ActiveLearningConfig:
    conf_min: float
    conf_max: float
    min_brightness: float
    max_brightness: float
    min_blur: float


@dataclass(frozen=True)
class PublishGateConfig:
    publish_cooldown_seconds: float
    publish_window_seconds: float
    max_uploads_per_window: int
    frame_dedup_phash_distance_max: int


@dataclass(frozen=True)
class RuleOodConfig:
    enabled: bool
    vehicle_top_zone_max_y: float
    extreme_area_max_ratio: float
    bus_vertical_ratio_min: float
    edge_touch_min_edges: int
    edge_touch_min_area_ratio: float
    forbidden_classes: tuple[str, ...]
    class_aspect_ratio_limits: tuple[tuple[str, float, float], ...]
    persistence_window_frames: int
    persistence_min_hits: int
    score_threshold: float
    score_forbidden_class: float
    score_extreme_area: float
    score_bus_vertical: float
    score_aspect_ratio: float
    score_top_zone_vehicle: float
    score_edge_touch: float


class ActiveLearningFilter:
    def __init__(self, config: ActiveLearningConfig) -> None:
        self.config = config

    def analyze_image_quality(self, frame: cv2.typing.MatLike) -> tuple[bool, str]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        brightness = float(np.mean(gray))
        if brightness < self.config.min_brightness:
            return True, f"OOD: Too Dark (brightness={brightness:.1f})"
        if brightness > self.config.max_brightness:
            return True, f"OOD: Too Bright/Glare (brightness={brightness:.1f})"

        blur_val = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if blur_val < self.config.min_blur:
            return True, f"OOD: Blurry (Val: {blur_val:.1f})"

        return False, ""

    def should_save_frame(
        self,
        frame: cv2.typing.MatLike,
        result: Results,
    ) -> tuple[bool, str]:
        for box in result.boxes:
            conf = float(box.conf[0])
            if self.config.conf_min <= conf <= self.config.conf_max:
                class_id = int(box.cls[0])
                return True, f"Uncertainty: Class {class_id} at {conf:.2f}"

        if len(result.boxes) > 0:
            is_ood, reason = self.analyze_image_quality(frame)
            if is_ood:
                return True, reason

        return False, "Clear"


class PublishGate:
    def __init__(self, config: PublishGateConfig) -> None:
        self.config = config
        self.last_publish_ts = 0.0
        self.window_start_ts = time.time()
        self.window_upload_count = 0
        self.last_frame_hash: np.ndarray | None = None

    def _frame_hash(self, frame: cv2.typing.MatLike) -> np.ndarray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (8, 8), interpolation=cv2.INTER_AREA)
        avg = float(np.mean(resized))
        return resized > avg

    def _hamming_distance(self, left: np.ndarray, right: np.ndarray) -> int:
        return int(np.count_nonzero(left != right))

    def should_publish(self, frame: cv2.typing.MatLike) -> tuple[bool, str]:
        now = time.time()
        if now - self.last_publish_ts < self.config.publish_cooldown_seconds:
            wait_left = self.config.publish_cooldown_seconds - (now - self.last_publish_ts)
            return False, f"Cooldown active ({wait_left:.2f}s left)"

        if now - self.window_start_ts >= self.config.publish_window_seconds:
            self.window_start_ts = now
            self.window_upload_count = 0

        if self.window_upload_count >= self.config.max_uploads_per_window:
            return False, "Window quota reached"

        current_hash = self._frame_hash(frame)
        if self.last_frame_hash is not None:
            distance = self._hamming_distance(current_hash, self.last_frame_hash)
            if distance <= self.config.frame_dedup_phash_distance_max:
                return False, f"Frame deduplicated (distance={distance})"

        self.last_publish_ts = now
        self.window_upload_count += 1
        self.last_frame_hash = current_hash
        return True, "Publish gate accepted"


class RuleBasedOodFilter:
    def __init__(self, config: RuleOodConfig) -> None:
        self.config = config
        self.vehicle_classes = {"bus", "truck", "car", "motorcycle"}
        self.persistence_history: deque[bool] = deque(maxlen=config.persistence_window_frames)
        self.class_aspect_ratio_limits_map = {
            class_name: (min_ratio, max_ratio)
            for class_name, min_ratio, max_ratio in config.class_aspect_ratio_limits
        }

    def _touching_edges_count(
        self,
        left: float,
        top: float,
        right: float,
        bottom: float,
        width: float,
        height: float,
    ) -> int:
        tolerance_px = 2.0
        edges = 0
        if left <= tolerance_px:
            edges += 1
        if top <= tolerance_px:
            edges += 1
        if right >= width - tolerance_px:
            edges += 1
        if bottom >= height - tolerance_px:
            edges += 1
        return edges

    def should_flag_ood(self, result: Results) -> tuple[bool, str]:
        if not self.config.enabled:
            return False, "Rule OOD disabled"

        frame_h = float(result.orig_shape[0])
        frame_w = float(result.orig_shape[1])
        frame_area = frame_w * frame_h
        if frame_area <= 0:
            raise RuntimeError("Invalid frame area for rule-based OOD.")

        soft_reasons: list[str] = []
        ood_score = 0.0

        for box in result.boxes:
            left = float(box.xyxy[0][0])
            top = float(box.xyxy[0][1])
            right = float(box.xyxy[0][2])
            bottom = float(box.xyxy[0][3])
            width = max(1.0, right - left)
            height = max(1.0, bottom - top)
            area_ratio = (width * height) / frame_area
            center_y_norm = ((top + bottom) * 0.5) / frame_h
            aspect_h_over_w = height / width
            class_idx = int(box.cls[0])
            class_name = str(result.names.get(class_idx, str(class_idx)))

            if class_name in self.config.forbidden_classes:
                ood_score += self.config.score_forbidden_class
                soft_reasons.append(
                    f"Forbidden class: {class_name} (+{self.config.score_forbidden_class:.2f})"
                )

            if area_ratio >= self.config.extreme_area_max_ratio:
                ood_score += self.config.score_extreme_area
                soft_reasons.append(
                    "Extreme scale: "
                    f"class={class_name}, area_ratio={area_ratio:.2f} (+{self.config.score_extreme_area:.2f})"
                )

            if class_name == "bus" and aspect_h_over_w >= self.config.bus_vertical_ratio_min:
                ood_score += self.config.score_bus_vertical
                soft_reasons.append(
                    f"Bus vertical shape: h/w={aspect_h_over_w:.2f} (+{self.config.score_bus_vertical:.2f})"
                )

            ratio_limits = self.class_aspect_ratio_limits_map.get(class_name)
            if ratio_limits is not None:
                min_ratio, max_ratio = ratio_limits
                if aspect_h_over_w < min_ratio or aspect_h_over_w > max_ratio:
                    ood_score += self.config.score_aspect_ratio
                    soft_reasons.append(
                        "Aspect ratio out-of-range: "
                        f"class={class_name}, h/w={aspect_h_over_w:.2f}, "
                        f"expected=[{min_ratio:.2f},{max_ratio:.2f}] (+{self.config.score_aspect_ratio:.2f})"
                    )

            if class_name in self.vehicle_classes and center_y_norm <= self.config.vehicle_top_zone_max_y:
                ood_score += self.config.score_top_zone_vehicle
                soft_reasons.append(
                    "Vehicle in top zone: "
                    f"class={class_name}, center_y_norm={center_y_norm:.2f} (+{self.config.score_top_zone_vehicle:.2f})"
                )

            touched_edges = self._touching_edges_count(left, top, right, bottom, frame_w, frame_h)
            if (
                touched_edges >= self.config.edge_touch_min_edges
                and area_ratio >= self.config.edge_touch_min_area_ratio
            ):
                ood_score += self.config.score_edge_touch
                soft_reasons.append(
                    "Edge-touch large box: "
                    f"class={class_name}, edges={touched_edges}, area_ratio={area_ratio:.2f} (+{self.config.score_edge_touch:.2f})"
                )

        is_score_hit = ood_score >= self.config.score_threshold
        self.persistence_history.append(is_score_hit)
        soft_hits = sum(1 for value in self.persistence_history if value)
        if is_score_hit and soft_hits >= self.config.persistence_min_hits:
            return True, (
                f"Rule OOD score={ood_score:.2f} threshold={self.config.score_threshold:.2f} | "
                + " | ".join(soft_reasons[:1])
                + f" | hits={soft_hits}/{len(self.persistence_history)}"
            )
        if is_score_hit:
            return False, (
                f"Rule OOD score hit but waiting persistence: score={ood_score:.2f}, "
                f"hits={soft_hits}/{len(self.persistence_history)}"
            )
        return False, f"Rule OOD clear: score={ood_score:.2f}"

