import os
from typing import Optional
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "Classroom Attendance System Using Face Recognition"
    SECRET_KEY: str = "college-btech-cse-facial-attendance-jwt-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/data/attendance.db"

    # Face Recognition Config
    LBPH_CONFIDENCE_THRESHOLD: float = 75.0
    FRAME_PROCESS_INTERVAL_MS: int = 1200
    RECOGNITION_WINDOW_MINUTES: int = 15  # Duration of the attendance recognition window
    
    # Paths
    DATA_DIR: Path = BASE_DIR / "data"
    FACES_DIR: Path = BASE_DIR / "data" / "faces"
    MODELS_DIR: Path = BASE_DIR / "data" / "models"
    EXPORTS_DIR: Path = BASE_DIR / "data" / "exports"
    HAAR_CASCADE_PATH: Path = BASE_DIR / "data" / "haarcascades" / "haarcascade_frontalface_default.xml"
    LBPH_MODEL_PATH: Path = BASE_DIR / "data" / "models" / "lbph_model.xml"
    MODEL_METADATA_PATH: Path = BASE_DIR / "data" / "models" / "model_meta.json"
    ANTI_SPOOF_MODEL_DIR: Path = BASE_DIR / "data" / "models" / "anti_spoofing"
    ANTI_SPOOF_MODEL_V2_PATH: Path = BASE_DIR / "data" / "models" / "anti_spoofing" / "minifasnet_v2.onnx"
    ANTI_SPOOF_MODEL_V1SE_PATH: Path = BASE_DIR / "data" / "models" / "anti_spoofing" / "minifasnet_v1se.onnx"
    ANTI_SPOOF_CONFIDENCE_THRESHOLD: float = 0.50

    # Environment & Security
    ENVIRONMENT: str = "development"
    INITIAL_ADMIN_USERNAME: Optional[str] = None
    INITIAL_ADMIN_PASSWORD: Optional[str] = None
    INITIAL_ADMIN_EMAIL: Optional[str] = None

    # Default Seed Admin (used only in development when INITIAL_ADMIN_* is not provided)
    DEFAULT_ADMIN_USERNAME: str = "admin"
    DEFAULT_ADMIN_PASSWORD: str = "admin123"
    DEFAULT_ADMIN_EMAIL: str = "admin@college.edu"

    model_config = SettingsConfigDict(env_file=".env", extra="allow")

settings = Settings()

# Ensure directories exist
for path in [settings.DATA_DIR, settings.FACES_DIR, settings.MODELS_DIR, settings.ANTI_SPOOF_MODEL_DIR, settings.EXPORTS_DIR, settings.HAAR_CASCADE_PATH.parent]:
    path.mkdir(parents=True, exist_ok=True)
