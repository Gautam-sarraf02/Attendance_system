import os
import shutil
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc
from app.database import get_db
from app.models.student import Student
from app.models.face_sample import FaceSample
from app.models.user import User
from app.schemas.student import StudentCreate, StudentUpdate, StudentOut, StudentListResponse
from app.schemas.face import UploadFaceSamplesRequest
from app.auth.deps import get_current_user, get_current_admin, verify_student_access
from app.face.detector import detector
from app.face.storage import storage

router = APIRouter(prefix="/students", tags=["Students"])

@router.get("", response_model=StudentListResponse)
def get_students(
    search: Optional[str] = None,
    section: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Students are not authorized to view the student directory."
        )

    query = db.query(Student).filter(Student.is_active == True)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Student.name.ilike(search_pattern),
                Student.roll_number.ilike(search_pattern),
                Student.email.ilike(search_pattern)
            )
        )
    
    if section:
        query = query.filter(Student.section == section)

    total = query.count()
    students = query.order_by(Student.roll_number).offset(skip).limit(limit).all()

    # Enrich with samples count
    result = []
    for s in students:
        samples_count = len(s.face_samples)
        s_out = StudentOut(
            id=s.id,
            roll_number=s.roll_number,
            name=s.name,
            section=s.section,
            email=s.email,
            is_active=s.is_active,
            created_at=s.created_at,
            samples_count=samples_count,
            face_samples=s.face_samples
        )
        result.append(s_out)

    return {"total": total, "students": result}

@router.post("", response_model=StudentOut, status_code=status.HTTP_201_CREATED)
def create_student(
    student_in: StudentCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    # Check duplicate roll number
    existing = db.query(Student).filter(Student.roll_number == student_in.roll_number.strip()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Student with Roll Number '{student_in.roll_number}' is already registered."
        )

    student = Student(
        roll_number=student_in.roll_number.strip(),
        name=student_in.name.strip(),
        section=student_in.section.strip().upper(),
        email=student_in.email.strip() if student_in.email else None,
        is_active=True
    )
    db.add(student)
    db.commit()
    db.refresh(student)

    return StudentOut(
        id=student.id,
        roll_number=student.roll_number,
        name=student.name,
        section=student.section,
        email=student.email,
        is_active=student.is_active,
        created_at=student.created_at,
        samples_count=0,
        face_samples=[]
    )

@router.get("/{student_id}", response_model=StudentOut)
def get_student_by_id(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    verify_student_access(current_user, student_id)

    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    
    return StudentOut(
        id=student.id,
        roll_number=student.roll_number,
        name=student.name,
        section=student.section,
        email=student.email,
        is_active=student.is_active,
        created_at=student.created_at,
        samples_count=len(student.face_samples),
        face_samples=student.face_samples
    )

@router.put("/{student_id}", response_model=StudentOut)
def update_student(
    student_id: int,
    student_update: StudentUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    if student_update.name is not None:
        student.name = student_update.name.strip()
    if student_update.section is not None:
        student.section = student_update.section.strip().upper()
    if student_update.email is not None:
        student.email = student_update.email.strip() if student_update.email else None
    if student_update.is_active is not None:
        student.is_active = student_update.is_active

    db.commit()
    db.refresh(student)

    return StudentOut(
        id=student.id,
        roll_number=student.roll_number,
        name=student.name,
        section=student.section,
        email=student.email,
        is_active=student.is_active,
        created_at=student.created_at,
        samples_count=len(student.face_samples),
        face_samples=student.face_samples
    )

@router.delete("/{student_id}")
def delete_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    # Delete face sample files from storage
    storage.delete_student_samples(student_id)

    db.delete(student)
    db.commit()
    return {"success": True, "message": f"Student '{student.name}' ({student.roll_number}) deleted successfully."}


@router.post("/{student_id}/samples/base64")
def upload_face_samples_base64(
    student_id: int,
    payload: UploadFaceSamplesRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """
    Accepts list of Base64 images (captured from live webcam or file picker),
    detects faces, validates quality, normalizes, and saves them for the student.
    """
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    if not payload.images or len(payload.images) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No images provided")

    saved_count = 0
    current_samples_count = db.query(FaceSample).filter(FaceSample.student_id == student_id).count()

    errors = []
    for idx, b64_str in enumerate(payload.images, start=1):
        try:
            cv_img = detector.decode_image_base64(b64_str)
            normalized_face = detector.validate_and_extract_single_face(cv_img)
            
            sample_index = current_samples_count + idx
            file_path, file_name = storage.save_face_sample(student_id, normalized_face, sample_index)

            face_sample = FaceSample(
                student_id=student_id,
                image_path=file_path,
                file_name=file_name
            )
            db.add(face_sample)
            saved_count += 1
        except Exception as e:
            errors.append(f"Image {idx}: {str(e)}")

    if saved_count > 0:
        db.commit()

    if saved_count == 0 and errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Face validation failed for all images: {'; '.join(errors)}"
        )

    return {
        "success": True,
        "samples_saved": saved_count,
        "total_samples": current_samples_count + saved_count,
        "warnings": errors if errors else None,
        "message": f"Successfully enrolled {saved_count} face samples for {student.name}."
    }

@router.post("/{student_id}/samples/upload")
async def upload_face_samples_files(
    student_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Accepts multipart uploaded image files."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    saved_count = 0
    current_samples_count = db.query(FaceSample).filter(FaceSample.student_id == student_id).count()
    errors = []

    for idx, file in enumerate(files, start=1):
        try:
            contents = await file.read()
            cv_img = detector.decode_image_bytes(contents)
            normalized_face = detector.validate_and_extract_single_face(cv_img)

            sample_index = current_samples_count + idx
            file_path, file_name = storage.save_face_sample(student_id, normalized_face, sample_index)

            face_sample = FaceSample(
                student_id=student_id,
                image_path=file_path,
                file_name=file_name
            )
            db.add(face_sample)
            saved_count += 1
        except Exception as e:
            errors.append(f"File '{file.filename}': {str(e)}")

    if saved_count > 0:
        db.commit()

    if saved_count == 0 and errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Face validation failed: {'; '.join(errors)}"
        )

    return {
        "success": True,
        "samples_saved": saved_count,
        "total_samples": current_samples_count + saved_count,
        "warnings": errors if errors else None,
        "message": f"Successfully enrolled {saved_count} face samples for {student.name}."
    }

@router.delete("/{student_id}/samples")
def clear_student_samples(
    student_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    storage.delete_student_samples(student_id)
    db.query(FaceSample).filter(FaceSample.student_id == student_id).delete()
    db.commit()

    return {"success": True, "message": f"Cleared face samples for {student.name}."}
