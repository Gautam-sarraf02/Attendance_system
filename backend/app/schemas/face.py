from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict

class FaceSampleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    image_path: str
    file_name: str
    created_at: datetime

class ModelStatusResponse(BaseModel):
    is_trained: bool
    algorithm: str = "LBPH (Local Binary Patterns Histograms)"
    detector: str = "Haar Cascade (haarcascade_frontalface_default.xml)"
    total_students_enrolled: int
    total_students_with_samples: int
    total_samples: int
    last_trained: Optional[str] = None
    confidence_threshold: float
    model_file_exists: bool

class TrainModelResponse(BaseModel):
    success: bool
    message: str
    students_trained: int
    samples_used: int
    training_time_seconds: float
    timestamp: str

class BoundingBox(BaseModel):
    x: int
    y: int
    width: int
    height: int

class RecognitionDetection(BaseModel):
    box: BoundingBox
    student_id: Optional[int] = None
    roll_number: Optional[str] = None
    name: str
    section: Optional[str] = None
    confidence: float  # LBPH distance (lower = higher similarity)
    is_known: bool
    attendance_marked: bool = False
    status_message: str
    liveness_score: Optional[float] = None
    is_live: Optional[bool] = None

class RecognizeFrameRequest(BaseModel):
    image_base64: str
    session_id: Optional[int] = None
    auto_mark: bool = True

class RecognizeFrameResponse(BaseModel):
    session_id: Optional[int]
    session_status: Optional[str] = None
    session_section: Optional[str] = None
    total_faces_detected: int
    known_faces_count: int
    unknown_faces_count: int
    detections: List[RecognitionDetection]
    timestamp: str

class UploadFaceBase64Item(BaseModel):
    image_base64: str

class UploadFaceSamplesRequest(BaseModel):
    images: List[str]  # Base64 data strings
