import os
import json
import time
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Optional, Any
import cv2
import numpy as np
from app.config import settings

logger = logging.getLogger(__name__)

class LBPHFaceRecognizerService:
    def __init__(
        self,
        model_path: Optional[Path] = None,
        meta_path: Optional[Path] = None,
        confidence_threshold: Optional[float] = None
    ):
        self.model_path = Path(model_path or settings.LBPH_MODEL_PATH)
        self.meta_path = Path(meta_path or settings.MODEL_METADATA_PATH)
        self.confidence_threshold = confidence_threshold or settings.LBPH_CONFIDENCE_THRESHOLD
        self.recognizer = cv2.face.LBPHFaceRecognizer_create(
            radius=1,
            neighbors=8,
            grid_x=8,
            grid_y=8
        )
        self._is_loaded = False
        self.load_model_if_exists()

    def load_model_if_exists(self) -> bool:
        """Loads trained LBPH model from disk if the file exists."""
        if self.model_path.exists() and self.model_path.stat().st_size > 0:
            try:
                self.recognizer.read(str(self.model_path))
                self._is_loaded = True
                logger.info(f"Loaded existing LBPH model from {self.model_path}")
                return True
            except Exception as e:
                logger.error(f"Error loading LBPH model: {e}")
                self._is_loaded = False
                return False
        self._is_loaded = False
        return False

    def is_trained(self) -> bool:
        return self._is_loaded and self.model_path.exists()

    def train(self, samples_dict: Dict[int, List[np.ndarray]]) -> Dict[str, Any]:
        """
        Trains LBPH recognizer on provided face samples.
        samples_dict format: {student_id: [img1_gray, img2_gray, ...]}
        """
        faces: List[np.ndarray] = []
        labels: List[int] = []

        for student_id, student_faces in samples_dict.items():
            for face_img in student_faces:
                if face_img is None or face_img.size == 0:
                    continue
                # Ensure 200x200 grayscale
                if len(face_img.shape) == 3:
                    face_img = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
                if face_img.shape != (200, 200):
                    face_img = cv2.resize(face_img, (200, 200), interpolation=cv2.INTER_AREA)
                
                faces.append(face_img)
                labels.append(int(student_id))

        if len(faces) == 0:
            raise ValueError("No valid face samples available for training.")

        if len(set(labels)) < 1:
            raise ValueError("At least 1 enrolled student with face samples is required to train the model.")

        start_time = time.time()
        
        # Train new recognizer instance
        new_recognizer = cv2.face.LBPHFaceRecognizer_create(
            radius=1,
            neighbors=8,
            grid_x=8,
            grid_y=8
        )
        new_recognizer.train(faces, np.array(labels, dtype=np.int32))

        # Save model file
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        new_recognizer.write(str(self.model_path))

        elapsed_time = round(time.time() - start_time, 3)

        # Update current recognizer
        self.recognizer = new_recognizer
        self._is_loaded = True

        # Save metadata
        metadata = {
            "algorithm": "LBPH (Local Binary Patterns Histograms)",
            "detector": "Haar Cascade (haarcascade_frontalface_default.xml)",
            "total_students_trained": len(set(labels)),
            "total_samples_used": len(faces),
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "confidence_threshold": self.confidence_threshold,
            "training_time_seconds": elapsed_time
        }
        with open(self.meta_path, "w") as f:
            json.dump(metadata, f, indent=2)

        return {
            "success": True,
            "students_trained": len(set(labels)),
            "samples_used": len(faces),
            "training_time_seconds": elapsed_time,
            "timestamp": metadata["trained_at"]
        }

    def predict(self, face_image: np.ndarray) -> Tuple[Optional[int], float, bool]:
        """
        Predicts student identity for a single normalized face.
        Returns: (student_id or None, distance_confidence, is_recognized)
        Note: In LBPH, lower distance means higher confidence/similarity.
        """
        if not self.is_trained():
            raise RuntimeError("Face recognition model is not trained. Please train the model first.")

        # Ensure grayscale and normalized
        if len(face_image.shape) == 3:
            face_gray = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)
        else:
            face_gray = face_image

        if face_gray.shape != (200, 200):
            face_gray = cv2.resize(face_gray, (200, 200), interpolation=cv2.INTER_AREA)

        student_id, distance = self.recognizer.predict(face_gray)
        distance = round(float(distance), 2)

        # Check against threshold: Lower distance = better match
        if distance <= self.confidence_threshold:
            return student_id, distance, True
        else:
            return None, distance, False

    def get_metadata(self) -> Dict[str, Any]:
        if self.meta_path.exists():
            try:
                with open(self.meta_path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

recognizer_service = LBPHFaceRecognizerService()
