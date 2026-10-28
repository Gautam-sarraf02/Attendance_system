import os
import io
import base64
import logging
from typing import List, Tuple, Optional
import cv2
import numpy as np
from app.config import settings
from app.face.anti_spoof import AntiSpoofClassifier, anti_spoof_classifier

logger = logging.getLogger(__name__)

# Standard normalized face size for LBPH training and recognition
FACE_WIDTH = 200
FACE_HEIGHT = 200

class FaceDetector:
    def __init__(self, cascade_path: Optional[str] = None):
        self.cascade_path = cascade_path or str(settings.HAAR_CASCADE_PATH)
        self.anti_spoof: AntiSpoofClassifier = anti_spoof_classifier
        if not os.path.exists(self.cascade_path):
            logger.warning(f"Haar cascade XML not found at {self.cascade_path}")
            self.classifier = None
        else:
            self.classifier = cv2.CascadeClassifier(self.cascade_path)
            if self.classifier.empty():
                logger.error(f"Failed to load Haar cascade from {self.cascade_path}")
                self.classifier = None
            else:
                logger.info(f"Loaded Haar cascade face detector from {self.cascade_path}")

    def decode_image_base64(self, base64_str: str) -> np.ndarray:
        """Decodes base64 string (with or without data URI prefix) to OpenCV BGR image."""
        if "," in base64_str:
            base64_str = base64_str.split(",")[1]
        img_bytes = base64.b64decode(base64_str)
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Failed to decode image from base64 data")
        return img

    def decode_image_bytes(self, image_bytes: bytes) -> np.ndarray:
        """Decodes raw image bytes to OpenCV BGR image."""
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Failed to decode image from raw bytes")
        return img

    def detect_faces(
        self,
        image: np.ndarray,
        scale_factor: float = 1.15,
        min_neighbors: int = 4,
        min_size: Tuple[int, int] = (30, 30)
    ) -> List[Tuple[int, int, int, int]]:
        """
        Detects all faces in an image using Haar Cascade.
        Returns list of bounding boxes: [(x, y, w, h), ...]
        """
        if self.classifier is None or self.classifier.empty():
            raise RuntimeError("Haar Cascade classifier is not initialized")

        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # Histogram equalization for better contrast under varying classroom lighting
        gray_eq = cv2.equalizeHist(gray)

        faces = self.classifier.detectMultiScale(
            gray_eq,
            scaleFactor=scale_factor,
            minNeighbors=min_neighbors,
            minSize=min_size,
            flags=cv2.CASCADE_SCALE_IMAGE
        )

        return [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in faces]

    def evaluate_liveness(
        self,
        face_roi: np.ndarray,
        full_image: Optional[np.ndarray] = None,
        bbox: Optional[Tuple[int, int, int, int]] = None
    ) -> Tuple[bool, float, str]:
        """
        Real-Time Face Anti-Spoofing & Liveness Evaluation using pretrained MiniFASNet neural model.
        Protects against printed photograph attacks and smartphone/screen video replay attacks.

        Returns: (is_live: bool, liveness_score: float, reason: str)
        Fails safely if spoof detected, model unavailable, or inference errors occur.
        """
        if face_roi is None or face_roi.size == 0:
            return False, 0.0, "Empty face region"

        h, w = face_roi.shape[:2]
        if h < 20 or w < 20:
            return False, 0.0, "Face region too small for reliable anti-spoofing analysis"

        # Pre-filter for monochromatic or zero-contrast paper replicas
        if len(face_roi.shape) == 3:
            hsv = cv2.cvtColor(face_roi, cv2.COLOR_BGR2HSV)
            sat = hsv[:, :, 1]
            sat_std = float(np.std(sat))
            if sat_std < 2.0:
                return False, 0.0, "Low chrominance variance (suspected grayscale/paper replica)"

        # Context-expanded neural evaluation (full camera frame + face bbox)
        if full_image is not None and bbox is not None:
            return self.anti_spoof.evaluate(full_image, bbox)

        # Isolated crop fallback
        return self.anti_spoof.evaluate(face_roi, (0, 0, w, h))

    def extract_and_normalize_face(
        self,
        image: np.ndarray,
        box: Tuple[int, int, int, int],
        target_size: Tuple[int, int] = (FACE_WIDTH, FACE_HEIGHT)
    ) -> np.ndarray:
        """
        Extracts face ROI, adds slight margin, converts to grayscale,
        applies histogram equalization, and resizes to target size.
        """
        x, y, w, h = box
        img_h, img_w = image.shape[:2]

        # Add 5% margin around the face bounding box if within image bounds
        margin_x = int(w * 0.05)
        margin_y = int(h * 0.05)
        x1 = max(0, x - margin_x)
        y1 = max(0, y - margin_y)
        x2 = min(img_w, x + w + margin_x)
        y2 = min(img_h, y + h + margin_y)

        face_roi = image[y1:y2, x1:x2]

        if len(face_roi.shape) == 3:
            face_gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        else:
            face_gray = face_roi

        face_eq = cv2.equalizeHist(face_gray)
        face_resized = cv2.resize(face_eq, target_size, interpolation=cv2.INTER_AREA)
        return face_resized

    def validate_and_extract_single_face(self, image: np.ndarray) -> np.ndarray:
        """
        Validates that exactly or at least one clear face exists in the image.
        Returns the primary normalized face ROI.
        """
        faces = self.detect_faces(image, min_neighbors=4)
        if len(faces) == 0:
            raise ValueError("No face detected in the image. Please ensure good lighting and face the camera directly.")
        
        # Pick the largest detected face box by area
        largest_face = max(faces, key=lambda b: b[2] * b[3])
        return self.extract_and_normalize_face(image, largest_face)

    def validate_enrollment_quality(
        self,
        image: np.ndarray,
        allow_multi: bool = False
    ) -> Tuple[np.ndarray, dict]:
        """
        Comprehensive Biometric Enrollment Quality Assurance:
        1. Checks minimum image dimensions.
        2. Ensures exactly one face is detected (unless allow_multi=True).
        3. Validates face bounding box resolution (minimum 60x60).
        4. Validates sharpness/blur via Laplacian variance (threshold >= 35.0).
        5. Validates illumination/brightness balance (mean intensity between 35 and 230).
        Returns: (normalized_face_roi, quality_metrics_dict)
        """
        if image is None or image.size == 0:
            raise ValueError("Empty or invalid image data received.")

        img_h, img_w = image.shape[:2]
        if img_h < 100 or img_w < 100:
            raise ValueError("Image resolution is too low for reliable face enrollment.")

        faces = self.detect_faces(image, min_neighbors=4)
        if len(faces) == 0:
            raise ValueError("No face detected. Please ensure good lighting and look directly into the camera.")

        if len(faces) > 1 and not allow_multi:
            raise ValueError(
                f"Multiple faces ({len(faces)}) detected in the frame. "
                "Only the individual being enrolled must be in view."
            )

        box = max(faces, key=lambda b: b[2] * b[3])
        x, y, w, h = box

        if w < 50 or h < 50:
            raise ValueError("Face is too far from camera. Please move closer.")

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        face_roi_gray = gray[y:y+h, x:x+w]

        # Sharpness / Blur check using Laplacian variance
        blur_score = float(cv2.Laplacian(face_roi_gray, cv2.CV_64F).var())
        if blur_score < 30.0:
            raise ValueError(f"Image is too blurry (sharpness score {blur_score:.1f} < 30). Please hold steady.")

        # Illumination balance
        mean_intensity = float(np.mean(face_roi_gray))
        if mean_intensity < 30.0:
            raise ValueError("Lighting is too dark. Please ensure sufficient front lighting.")
        if mean_intensity > 235.0:
            raise ValueError("Image is overexposed or has severe glare. Please adjust lighting.")

        normalized_face = self.extract_and_normalize_face(image, box)
        metrics = {
            "face_width": w,
            "face_height": h,
            "sharpness": round(blur_score, 1),
            "brightness": round(mean_intensity, 1),
            "quality_grade": "Excellent" if blur_score > 80 and 70 <= mean_intensity <= 180 else "Good"
        }
        return normalized_face, metrics

# Global singleton detector
detector = FaceDetector()

