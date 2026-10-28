import os
import shutil
import logging
from pathlib import Path
from typing import List, Tuple, Optional
import cv2
import numpy as np
from app.config import settings

logger = logging.getLogger(__name__)

class FaceStorage:
    """
    Manages secure biometric template storage and retention lifecycle.
    Biometric files are stored with restricted POSIX permissions (0o600).
    Never logs raw template buffers or facial image bytes.
    """
    def __init__(self, faces_dir: Optional[Path] = None):
        self.faces_dir = Path(faces_dir or settings.FACES_DIR)
        self.faces_dir.mkdir(parents=True, exist_ok=True)
        # Protect parent directory permissions
        try:
            os.chmod(self.faces_dir, 0o700)
        except Exception:
            pass

    def get_entity_dir(self, entity_id: int, is_user: bool = False) -> Path:
        """Returns secure directory for a student or teacher user."""
        prefix = "user_" if is_user else "student_"
        # Support legacy numeric directory or prefixed directory
        target_dir = self.faces_dir / f"{prefix}{entity_id}"
        legacy_dir = self.faces_dir / str(entity_id)

        if not is_user and legacy_dir.exists() and not target_dir.exists():
            return legacy_dir

        target_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(target_dir, 0o700)
        except Exception:
            pass
        return target_dir

    def get_student_dir(self, student_id: int) -> Path:
        return self.get_entity_dir(student_id, is_user=False)

    def save_face_sample(
        self,
        entity_id: int,
        face_image: np.ndarray,
        sample_index: int,
        is_user: bool = False
    ) -> Tuple[str, str]:
        """
        Saves a normalized face template into the entity's protected directory.
        Enforces restricted file permissions (0o600).
        """
        entity_dir = self.get_entity_dir(entity_id, is_user=is_user)
        file_name = f"sample_{sample_index}.jpg"
        file_path = entity_dir / file_name

        # Ensure normalized grayscale (200x200)
        if len(face_image.shape) == 3:
            norm_face = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)
        else:
            norm_face = face_image

        if norm_face.shape != (200, 200):
            norm_face = cv2.resize(norm_face, (200, 200), interpolation=cv2.INTER_AREA)

        cv2.imwrite(str(file_path), norm_face, [cv2.IMWRITE_JPEG_QUALITY, 95])

        # Enforce strict file permissions for biometric template security
        try:
            os.chmod(file_path, 0o600)
        except Exception:
            pass

        return str(file_path), file_name

    def load_entity_samples(self, entity_id: int, is_user: bool = False) -> List[np.ndarray]:
        """Loads saved face templates for an entity as grayscale numpy arrays."""
        entity_dir = self.get_entity_dir(entity_id, is_user=is_user)
        if not entity_dir.exists():
            return []

        samples = []
        for file in sorted(entity_dir.glob("*.jpg")):
            img = cv2.imread(str(file), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                samples.append(img)
        return samples

    def load_student_samples(self, student_id: int) -> List[np.ndarray]:
        return self.load_entity_samples(student_id, is_user=False)

    def delete_entity_samples(self, entity_id: int, is_user: bool = False) -> bool:
        """Securely deletes all biometric files and directory for an entity."""
        entity_dir = self.get_entity_dir(entity_id, is_user=is_user)
        legacy_dir = self.faces_dir / str(entity_id) if not is_user else None

        deleted = False
        if entity_dir.exists():
            shutil.rmtree(entity_dir)
            deleted = True
        if legacy_dir and legacy_dir.exists():
            shutil.rmtree(legacy_dir)
            deleted = True
        return deleted

    def delete_student_samples(self, student_id: int) -> bool:
        return self.delete_entity_samples(student_id, is_user=False)

    def count_entity_samples(self, entity_id: int, is_user: bool = False) -> int:
        entity_dir = self.get_entity_dir(entity_id, is_user=is_user)
        if not entity_dir.exists():
            return 0
        return len(list(entity_dir.glob("*.jpg")))

    def count_student_samples(self, student_id: int) -> int:
        return self.count_entity_samples(student_id, is_user=False)

storage = FaceStorage()
