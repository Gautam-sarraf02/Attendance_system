from datetime import date, datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, Response, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.attendance import Attendance
from app.models.student import Student
from app.models.user import User
from app.schemas.report import (
    StudentAttendanceStats,
    SubjectAttendanceStats,
    DailyAttendanceStats,
    MonthlyTrendStats,
    SemesterAttendanceStats,
    SectionAttendanceStats,
    ComprehensiveReportOut,
)
from app.auth.deps import get_current_user, verify_teacher_class_access
from app.services.stats_service import stats_service
from app.services.export_service import export_service

router = APIRouter(prefix="/reports", tags=["Reports & Analytics"])


@router.get("/students", response_model=List[StudentAttendanceStats])
def get_student_reports(
    subject: Optional[str] = None,
    section: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Calculates attendance percentages:
    - Students strictly receive only their own personal attendance report.
    - Teachers and Admins can view section or subject reports.
    """
    if current_user.role == "student":
        return stats_service.get_student_attendance_stats(
            db, subject=subject, student_id=current_user.student_id
        )

    if current_user.role in ("teacher", "faculty") and section:
        verify_teacher_class_access(current_user, db, subject=subject, section=section)

    return stats_service.get_student_attendance_stats(db, subject=subject, section=section)


@router.get("/subjects", response_model=List[SubjectAttendanceStats])
def get_subject_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Subject-wise reports for Faculty and Administrator."""
    if current_user.role == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Students cannot access faculty analytics."
        )
    return stats_service.get_subject_attendance_stats(db)


@router.get("/daily", response_model=List[DailyAttendanceStats])
def get_daily_reports(
    limit: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Daily trends for Faculty and Administrator."""
    if current_user.role == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Students cannot access daily administrative reports."
        )
    return stats_service.get_daily_attendance_stats(db, limit=limit)


@router.get("/monthly", response_model=List[MonthlyTrendStats])
def get_monthly_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Monthly trends for Faculty and Administrator."""
    if current_user.role == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Students cannot access monthly administrative reports."
        )
    return stats_service.get_monthly_attendance_stats(db)


@router.get("/semesters", response_model=List[SemesterAttendanceStats])
def get_semester_reports(
    academic_year_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Phase 7: Semester-wise attendance reports for Faculty and Administrator."""
    if current_user.role == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Students cannot access semester-level reports."
        )
    return stats_service.get_semester_attendance_stats(db, academic_year_id=academic_year_id)


@router.get("/sections", response_model=List[SectionAttendanceStats])
def get_section_reports(
    semester_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Phase 7: Section-wise attendance reports for Faculty and Administrator."""
    if current_user.role == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Students cannot access section-level reports."
        )
    return stats_service.get_section_attendance_stats(db, semester_id=semester_id)


@router.get("/comprehensive", response_model=ComprehensiveReportOut)
def get_comprehensive_report(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    subject: Optional[str] = None,
    section: Optional[str] = None,
    semester_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Phase 7: Multi-dimensional reports (Date-wise, Subject-wise, Semester-wise, and Section-wise)."""
    if current_user.role == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Students cannot access comprehensive institutional reports."
        )
    return stats_service.get_comprehensive_stats(
        db,
        start_date=start_date,
        end_date=end_date,
        subject=subject,
        section=section,
        semester_id=semester_id
    )


@router.get("/export/csv")
def export_csv_report(
    report_type: str = Query("detailed", pattern="^(detailed|student_summary|comprehensive)$"),
    date_val: Optional[date] = Query(None, alias="date"),
    subject: Optional[str] = None,
    section: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generates and downloads a CSV report (Admin and Teacher only)."""
    if current_user.role == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Students cannot export institutional attendance registers."
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if report_type == "detailed":
        query = (
            db.query(Attendance, Student)
            .join(Student, Attendance.student_id == Student.id)
        )
        if date_val:
            query = query.filter(Attendance.date == date_val)
        if subject:
            query = query.filter(Attendance.subject.ilike(f"%{subject}%"))
        if section:
            query = query.filter(Student.section == section)

        records_raw = query.order_by(Attendance.date.desc(), Attendance.time.desc()).all()
        records_list = [
            {
                "roll_number": std.roll_number,
                "student_name": std.name,
                "section": std.section,
                "subject": att.subject,
                "date": str(att.date),
                "time": str(att.time)[:8],
                "status": att.status,
                "confidence_score": att.confidence_score,
                "session_id": att.session_id
            }
            for att, std in records_raw
        ]
        df = export_service.generate_attendance_dataframe(records_list)
        filename = f"attendance_records_{timestamp}.csv"
    elif report_type == "student_summary":
        stats = stats_service.get_student_attendance_stats(db, subject=subject, section=section)
        df = export_service.generate_student_summary_dataframe(stats)
        filename = f"student_attendance_summary_{timestamp}.csv"
    else:
        comp = stats_service.get_comprehensive_stats(db, start_date=date_val, end_date=date_val, subject=subject, section=section)
        # Flatten overall for CSV
        df = export_service.generate_student_summary_dataframe(stats_service.get_student_attendance_stats(db, subject=subject, section=section))
        filename = f"comprehensive_summary_{timestamp}.csv"

    csv_data = export_service.export_to_csv(df)

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/export/excel")
def export_excel_report(
    report_type: str = Query("detailed", pattern="^(detailed|student_summary|comprehensive)$"),
    date_val: Optional[date] = Query(None, alias="date"),
    subject: Optional[str] = None,
    section: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generates and downloads an Excel (.xlsx) report (Admin and Teacher only)."""
    if current_user.role == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Students cannot export institutional attendance registers."
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if report_type == "detailed":
        query = (
            db.query(Attendance, Student)
            .join(Student, Attendance.student_id == Student.id)
        )
        if date_val:
            query = query.filter(Attendance.date == date_val)
        if subject:
            query = query.filter(Attendance.subject.ilike(f"%{subject}%"))
        if section:
            query = query.filter(Student.section == section)

        records_raw = query.order_by(Attendance.date.desc(), Attendance.time.desc()).all()
        records_list = [
            {
                "roll_number": std.roll_number,
                "student_name": std.name,
                "section": std.section,
                "subject": att.subject,
                "date": str(att.date),
                "time": str(att.time)[:8],
                "status": att.status,
                "confidence_score": att.confidence_score,
                "session_id": att.session_id
            }
            for att, std in records_raw
        ]
        df = export_service.generate_attendance_dataframe(records_list)
        excel_bytes = export_service.export_to_excel_bytes(
            df,
            sheet_name="Detailed Attendance",
            title="Classroom Facial Attendance Register"
        )
        filename = f"attendance_records_{timestamp}.xlsx"
    elif report_type == "student_summary":
        stats = stats_service.get_student_attendance_stats(db, subject=subject, section=section)
        df = export_service.generate_student_summary_dataframe(stats)
        excel_bytes = export_service.export_to_excel_bytes(
            df,
            sheet_name="Student Summary",
            title="Student Attendance Percentage Report"
        )
        filename = f"student_attendance_summary_{timestamp}.xlsx"
    else:
        # Phase 7 Comprehensive Multi-Sheet Excel Workbook
        comp = stats_service.get_comprehensive_stats(
            db,
            start_date=date_val,
            end_date=date_val,
            subject=subject,
            section=section
        )
        excel_bytes = export_service.export_comprehensive_excel_bytes(
            comp,
            title="Institutional Comprehensive Attendance Report"
        )
        filename = f"comprehensive_attendance_report_{timestamp}.xlsx"

    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
