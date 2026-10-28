from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.student import Student
from app.schemas.report import DashboardStatsOut, StudentDashboardOut
from app.auth.deps import get_current_user
from app.services.stats_service import stats_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/stats", response_model=DashboardStatsOut)
def get_dashboard_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns live computed database metrics for faculty dashboard cards and charts (Admin and Teacher only)."""
    if current_user.role == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Students cannot access administrative dashboard metrics."
        )

    metrics = stats_service.get_dashboard_stats(db)
    return metrics


@router.get("/student", response_model=StudentDashboardOut)
def get_student_dashboard(
    student_id: Optional[int] = Query(None, description="Optional student ID for Admin/Teacher inspection"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Phase 8: Student Dashboard metrics endpoint.
    - Shows only the logged-in student's records (Role isolation).
    - Faculty and Administrators can inspect specific student dashboards.
    - Provides registration validity, punch history, subject-wise breakdown, and monthly summaries.
    - Ensures absent records are shown only after finalization.
    """
    target_student_id = None

    if current_user.role == "student":
        if student_id and student_id != current_user.student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Students can only view their own dashboard records."
            )
        target_student_id = current_user.student_id
        if not target_student_id:
            # Fallback by roll number matching if student_id FK was unset
            std = db.query(Student).filter(Student.roll_number == current_user.username).first()
            if std:
                target_student_id = std.id
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No student profile is associated with this student user account."
                )
    else:
        # Admin or Teacher inspecting student
        if student_id:
            target_student_id = student_id
        else:
            first_std = db.query(Student).filter(Student.is_active == True).first()
            if first_std:
                target_student_id = first_std.id
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No active student records found in institution."
                )

    data = stats_service.get_student_dashboard_stats(db, target_student_id)
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student attendance records not found.")

    return data
