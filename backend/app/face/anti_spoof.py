import os
import logging
from typing import Tuple, Optional, List
import cv2
import numpy as np

try:
    import onnxruntime as ort
except ImportError:
    ort = None

from app.config import settings

logger = logging.getLogger(__name__)

class AntiSpoofClassifier:
    """
    Real-Time Face Anti-Spoofing & Liveness Detection using pretrained MiniFASNet models
    (Silent-Face-Anti-Spoofing architecture).
    
    Protects against:
    - Print attacks (printed photos, cutouts, paper replicas)
    - Video & screen replay attacks (smartphones, tablets, external displays)
    
    Runs via ONNX Runtime on CPU (< 45 MB RAM, ~3.5 ms per frame on Apple Silicon M1).
    Fails closed: if models are missing, corrupt, or an inference error occurs,
    attendance is strictly blocked.
    """
    def __init__(
        self,
        model_v2_path: Optional[str] = None,
        model_v1se_path: Optional[str] = None,
        confidence_threshold: Optional[float] = None
    ):
        self.model_v2_path = str(model_v2_path or settings.ANTI_SPOOF_MODEL_V2_PATH)
        self.model_v1se_path = str(model_v1se_path or settings.ANTI_SPOOF_MODEL_V1SE_PATH)
        self.confidence_threshold = confidence_threshold or settings.ANTI_SPOOF_CONFIDENCE_THRESHOLD

        self.session_v2: Optional["ort.InferenceSession"] = None
        self.session_v1se: Optional["ort.InferenceSession"] = None
        self._load_models()

    def _load_models(self) -> None:
        if ort is None:
            logger.error("onnxruntime is not installed. Face anti-spoofing is disabled.")
            return

        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 2
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        # Load MiniFASNetV2 (optimized for scale 2.7)
        if os.path.exists(self.model_v2_path):
            try:
                self.session_v2 = ort.InferenceSession(
                    self.model_v2_path,
                    sess_options=opts,
                    providers=["CPUExecutionProvider"]
                )
                logger.info(f"Loaded MiniFASNetV2 anti-spoof model from {self.model_v2_path}")
            except Exception as e:
                logger.error(f"Failed to load MiniFASNetV2 model: {e}")
                self.session_v2 = None
        else:
            logger.warning(f"MiniFASNetV2 model file not found at {self.model_v2_path}")

        # Load MiniFASNetV1SE (optimized for scale 4.0)
        if os.path.exists(self.model_v1se_path):
            try:
                self.session_v1se = ort.InferenceSession(
                    self.model_v1se_path,
                    sess_options=opts,
                    providers=["CPUExecutionProvider"]
                )
                logger.info(f"Loaded MiniFASNetV1SE anti-spoof model from {self.model_v1se_path}")
            except Exception as e:
                logger.error(f"Failed to load MiniFASNetV1SE model: {e}")
                self.session_v1se = None
        else:
            logger.warning(f"MiniFASNetV1SE model file not found at {self.model_v1se_path}")

    @property
    def is_available(self) -> bool:
        return (self.session_v2 is not None) or (self.session_v1se is not None)

    @staticmethod
    def _crop_face(
        image: np.ndarray,
        bbox: Tuple[int, int, int, int],
        scale: float
    ) -> np.ndarray:
        """
        Crops face region expanded by `scale` to capture screen bezels,
        paper margins, and contextual lighting artifacts.
        """
        src_h, src_w = image.shape[:2]
        x, y, box_w, box_h = bbox
        
        # Guard against zero or negative box sizes
        box_w = max(1, box_w)
        box_h = max(1, box_h)

        effective_scale = min((src_h - 1) / box_h, (src_w - 1) / box_w, scale)
        new_w = box_w * effective_scale
        new_h = box_h * effective_scale

        center_x = x + box_w / 2.0
        center_y = y + box_h / 2.0

        x1 = max(0, int(center_x - new_w / 2.0))
        y1 = max(0, int(center_y - new_h / 2.0))
        x2 = min(src_w - 1, int(center_x + new_w / 2.0))
        y2 = min(src_h - 1, int(center_y + new_h / 2.0))

        cropped = image[y1 : y2 + 1, x1 : x2 + 1]
        if cropped.size == 0:
            return np.zeros((80, 80, 3), dtype=np.uint8)

        return cv2.resize(cropped, (80, 80), interpolation=cv2.INTER_LINEAR)

    @staticmethod
    def _softmax(x: np.ndarray) -> np.ndarray:
        e = np.exp(x - np.max(x, axis=1, keepdims=True))
        return e / np.sum(e, axis=1, keepdims=True)

    def evaluate(
        self,
        full_image: np.ndarray,
        bbox: Tuple[int, int, int, int]
    ) -> Tuple[bool, float, str]:
        """
        Evaluates face liveness and anti-spoofing on the provided frame and bounding box.
        
        Returns:
            Tuple[is_live: bool, confidence_score: float, status_reason: str]
        """
        if not self.is_available:
            return False, 0.0, "Liveness check failed — anti-spoofing model unavailable"

        if full_image is None or full_image.size == 0:
            return False, 0.0, "Liveness check failed — empty camera frame"

        try:
            predictions = []

            # Model 1: MiniFASNetV2 with scale 2.7
            if self.session_v2 is not None:
                crop_v2 = self._crop_face(full_image, bbox, scale=2.7)
                tensor_v2 = np.expand_dims(
                    np.transpose(crop_v2.astype(np.float32), (2, 0, 1)),
                    axis=0
                )
                input_name_v2 = self.session_v2.get_inputs()[0].name
                logits_v2 = self.session_v2.run(None, {input_name_v2: tensor_v2})[0]
                prob_v2 = self._softmax(logits_v2)
                predictions.append(prob_v2)

            # Model 2: MiniFASNetV1SE with scale 4.0
            if self.session_v1se is not None:
                crop_v1 = self._crop_face(full_image, bbox, scale=4.0)
                tensor_v1 = np.expand_dims(
                    np.transpose(crop_v1.astype(np.float32), (2, 0, 1)),
                    axis=0
                )
                input_name_v1 = self.session_v1se.get_inputs()[0].name
                logits_v1 = self.session_v1se.run(None, {input_name_v1: tensor_v1})[0]
                prob_v1 = self._softmax(logits_v1)
                predictions.append(prob_v1)

            if not predictions:
                return False, 0.0, "Liveness check failed — no active model"

            # Ensemble average
            combined_prob = np.mean(predictions, axis=0)
            label_idx = int(np.argmax(combined_prob))
            live_confidence = float(combined_prob[0, 1])

            # Class mapping:
            # 0: Printed photograph attack (paper / print)
            # 1: Real live human face
            # 2: Digital screen / video replay attack
            if label_idx == 0:
                logger.warning(f"Anti-spoofing blocked print attack (confidence {combined_prob[0, 0]:.3f})")
                return False, round(live_confidence, 4), "Liveness check failed — printed photograph attack detected"
            elif label_idx == 2:
                logger.warning(f"Anti-spoofing blocked replay attack (confidence {combined_prob[0, 2]:.3f})")
                return False, round(live_confidence, 4), "Liveness check failed — digital screen / video replay attack detected"
            elif label_idx == 1 and live_confidence >= self.confidence_threshold:
                return True, round(live_confidence, 4), f"Live face verified ({round(live_confidence * 100, 1)}%)"
            else:
                return False, round(live_confidence, 4), f"Liveness check failed — low liveness confidence ({round(live_confidence * 100, 1)}%)"

        except Exception as e:
            logger.exception(f"Anti-spoofing inference error: {e}")
            return False, 0.0, "Liveness check failed — inference error"

anti_spoof_classifier = AntiSpoofClassifier()
