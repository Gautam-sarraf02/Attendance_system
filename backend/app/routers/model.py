from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.student import Student
from app.models.face_sample import FaceSample
from app.models.user import User
from app.schemas.face import ModelStatusResponse, TrainModelResponse
from app.auth.deps import get_current_user, get_current_admin
from app.face.recognizer import recognizer_service
from app.face.storage import storage
from app.config import settings

router = APIRouter(prefix="/model", tags=["Face Recognition Model"])


@router.get("/status", response_model=ModelStatusResponse)
def get_model_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """View model status (Admin and Teacher only)."""
    if current_user.role == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Students cannot inspect model metadata."
        )

    total_students = db.query(Student).filter(Student.is_active == True).count()
    
    # Students who have at least 1 face sample
    students_with_samples = (
        db.query(FaceSample.student_id)
        .join(Student, FaceSample.student_id == Student.id)
        .filter(Student.is_active == True)
        .distinct()
        .count()
    )
    
    total_samples = (
        db.query(FaceSample)
        .join(Student, FaceSample.student_id == Student.id)
        .filter(Student.is_active == True)
        .count()
    )

    metadata = recognizer_service.get_metadata()
    is_trained = recognizer_service.is_trained()

    return ModelStatusResponse(
        is_trained=is_trained,
        algorithm="LBPH (Local Binary Patterns Histograms)",
        detector="Haar Cascade (haarcascade_frontalface_default.xml)",
        total_students_enrolled=total_students,
        total_students_with_samples=students_with_samples,
        total_samples=total_samples,
        last_trained=metadata.get("trained_at"),
        confidence_threshold=recognizer_service.confidence_threshold,
        model_file_exists=settings.LBPH_MODEL_PATH.exists()
    )


@router.post("/train", response_model=TrainModelResponse)
def train_model(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Trigger facial recognition model retraining (Admin only)."""
    students = db.query(Student).filter(Student.is_active == True).all()
    if not students:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active students found in the database. Please register students first."
        )

    samples_dict = {}
    for student in students:
        samples = storage.load_student_samples(student.id)
        if samples:
            samples_dict[student.id] = samples

    if not samples_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No face samples found for any student. Please upload or capture face images for students before training."
        )

    try:
        result = recognizer_service.train(samples_dict)
        return TrainModelResponse(
            success=True,
            message=f"LBPH face model successfully trained with {result['samples_used']} samples across {result['students_trained']} student(s).",
            students_trained=result["students_trained"],
            samples_used=result["samples_used"],
            training_time_seconds=result["training_time_seconds"],
            timestamp=result["timestamp"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Face model training failed: {str(e)}"
        )


@router.put("/threshold")
def update_confidence_threshold(
    threshold: float = Body(..., embed=True, ge=20.0, le=120.0),
    current_admin: User = Depends(get_current_admin)
):
    """Update LBPH confidence distance threshold (Admin only)."""
    recognizer_service.confidence_threshold = float(threshold)
    return {
        "success": True,
        "message": f"LBPH confidence distance threshold updated to {threshold}.",
        "threshold": threshold
    }
