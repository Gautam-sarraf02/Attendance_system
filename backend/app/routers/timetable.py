import datetime
from datetime import date, time
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Response, Body
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models.academic_year import AcademicYear
from app.models.semester import Semester
from app.models.subject import Subject
from app.models.timetable import TimetableEntry, get_section_variants
from app.models.user import User
from app.models.holiday import Holiday
from app.models.substitute_auth import SubstituteAuthorization
from app.schemas.academic import (
    DAY_NAMES,
    AcademicYearCreate, AcademicYearUpdate, AcademicYearOut,
    SemesterCreate, SemesterUpdate, SemesterOut,
    SubjectCreate, SubjectUpdate, SubjectOut,
    TimetableEntryCreate, TimetableEntryUpdate, TimetableEntryOut,
    TimetableEntryDetailOut,
    TimetableImportPreviewResponse, TimetableImportCommitRequest,
    HolidayCreate, HolidayOut,
    ScheduledClassLookupResponse, ScheduledClassLookupEntry
)
from app.services.timetable_service import (
    detect_timetable_conflicts,
    parse_raw_file_to_rows,
    preview_timetable_import,
    commit_timetable_import,
    parse_time_value
)
from app.auth.deps import get_current_user, get_current_admin, get_current_teacher, require_roles

router = APIRouter(prefix="/timetable", tags=["Academic Calendar & Timetable"])


# ─── Academic Years ──────────────────────────────────────────────────────────

@router.get("/academic-years", response_model=List[AcademicYearOut])
def list_academic_years(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """All authenticated users (Admin, Teacher, Student) can view academic years."""
    return db.query(AcademicYear).order_by(AcademicYear.start_date.desc()).all()


@router.post("/academic-years", response_model=AcademicYearOut, status_code=status.HTTP_201_CREATED)
def create_academic_year(
    year_in: AcademicYearCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Only Administrator can create an academic year."""
    existing = db.query(AcademicYear).filter(AcademicYear.name == year_in.name.strip()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Academic year '{year_in.name}' already exists."
        )

    # If is_current is set, reset other current years
    if year_in.is_current:
        db.query(AcademicYear).filter(AcademicYear.is_current == True).update({"is_current": False})

    year = AcademicYear(
        name=year_in.name.strip(),
        start_date=year_in.start_date,
        end_date=year_in.end_date,
        is_current=year_in.is_current
    )
    db.add(year)
    db.commit()
    db.refresh(year)
    return year


@router.put("/academic-years/{year_id}", response_model=AcademicYearOut)
def update_academic_year(
    year_id: int,
    year_in: AcademicYearUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Only Administrator can update an academic year."""
    year = db.query(AcademicYear).filter(AcademicYear.id == year_id).first()
    if not year:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic year not found.")

    if year_in.name is not None:
        year.name = year_in.name.strip()
    if year_in.start_date is not None:
        year.start_date = year_in.start_date
    if year_in.end_date is not None:
        year.end_date = year_in.end_date
    if year_in.is_current is not None:
        if year_in.is_current:
            db.query(AcademicYear).filter(AcademicYear.id != year_id, AcademicYear.is_current == True).update({"is_current": False})
        year.is_current = year_in.is_current

    db.commit()
    db.refresh(year)
    return year


@router.delete("/academic-years/{year_id}")
def delete_academic_year(
    year_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Only Administrator can delete an academic year."""
    year = db.query(AcademicYear).filter(AcademicYear.id == year_id).first()
    if not year:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic year not found.")

    name = year.name
    db.delete(year)
    db.commit()
    return {"success": True, "message": f"Academic year '{name}' deleted successfully."}


# ─── Semesters ───────────────────────────────────────────────────────────────

@router.get("/semesters", response_model=List[SemesterOut])
def list_semesters(
    academic_year_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """All authenticated users can view semesters."""
    query = db.query(Semester)
    if academic_year_id:
        query = query.filter(Semester.academic_year_id == academic_year_id)
    return query.order_by(Semester.start_date.desc()).all()


@router.post("/semesters", response_model=SemesterOut, status_code=status.HTTP_201_CREATED)
def create_semester(
    sem_in: SemesterCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Only Administrator can create a semester."""
    year = db.query(AcademicYear).filter(AcademicYear.id == sem_in.academic_year_id).first()
    if not year:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referenced academic year not found.")

    semester = Semester(
        name=sem_in.name.strip(),
        academic_year_id=sem_in.academic_year_id,
        start_date=sem_in.start_date,
        end_date=sem_in.end_date,
        is_active=sem_in.is_active
    )
    db.add(semester)
    db.commit()
    db.refresh(semester)
    return semester


@router.put("/semesters/{sem_id}", response_model=SemesterOut)
def update_semester(
    sem_id: int,
    sem_in: SemesterUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Only Administrator can update a semester."""
    semester = db.query(Semester).filter(Semester.id == sem_id).first()
    if not semester:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Semester not found.")

    if sem_in.name is not None:
        semester.name = sem_in.name.strip()
    if sem_in.start_date is not None:
        semester.start_date = sem_in.start_date
    if sem_in.end_date is not None:
        semester.end_date = sem_in.end_date
    if sem_in.is_active is not None:
        semester.is_active = sem_in.is_active

    db.commit()
    db.refresh(semester)
    return semester


@router.delete("/semesters/{sem_id}")
def delete_semester(
    sem_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Only Administrator can delete a semester."""
    semester = db.query(Semester).filter(Semester.id == sem_id).first()
    if not semester:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Semester not found.")

    name = semester.name
    db.delete(semester)
    db.commit()
    return {"success": True, "message": f"Semester '{name}' deleted successfully."}


# ─── Subjects ────────────────────────────────────────────────────────────────

@router.get("/subjects", response_model=List[SubjectOut])
def list_subjects(
    semester_id: Optional[int] = None,
    section: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """All authenticated users can view subjects."""
    query = db.query(Subject)
    if semester_id:
        query = query.filter(Subject.semester_id == semester_id)
    if section:
        query = query.filter(Subject.section == section.strip().upper())
    return query.order_by(Subject.code).all()


@router.post("/subjects", response_model=SubjectOut, status_code=status.HTTP_201_CREATED)
def create_subject(
    sub_in: SubjectCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Only Administrator can create subjects."""
    semester = db.query(Semester).filter(Semester.id == sub_in.semester_id).first()
    if not semester:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referenced semester not found.")

    code_clean = sub_in.code.strip().upper()
    section_clean = sub_in.section.strip().upper()
    existing = db.query(Subject).filter(
        Subject.code == code_clean,
        Subject.section == section_clean,
        Subject.semester_id == sub_in.semester_id
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Subject with code '{code_clean}' already exists for section '{section_clean}' in this semester."
        )

    subject = Subject(
        code=code_clean,
        name=sub_in.name.strip(),
        semester_id=sub_in.semester_id,
        section=section_clean,
        is_active=sub_in.is_active
    )
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return subject


@router.put("/subjects/{subject_id}", response_model=SubjectOut)
def update_subject(
    subject_id: int,
    sub_in: SubjectUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Only Administrator can update subjects."""
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found.")

    if sub_in.code is not None:
        subject.code = sub_in.code.strip().upper()
    if sub_in.name is not None:
        subject.name = sub_in.name.strip()
    if sub_in.section is not None:
        subject.section = sub_in.section.strip().upper()
    if sub_in.is_active is not None:
        subject.is_active = sub_in.is_active

    db.commit()
    db.refresh(subject)
    return subject


@router.delete("/subjects/{subject_id}")
def delete_subject(
    subject_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Only Administrator can delete subjects."""
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found.")

    name = subject.name
    db.delete(subject)
    db.commit()
    return {"success": True, "message": f"Subject '{name}' deleted successfully."}


# ─── Timetable Entries ───────────────────────────────────────────────────────

def _format_timetable_detail(entry: TimetableEntry) -> TimetableEntryDetailOut:
    subject_name = entry.subject.name if entry.subject else None
    subject_code = entry.subject.code if entry.subject else None
    teacher_name = None
    teacher_username = None
    if entry.teacher:
        teacher_name = entry.teacher.full_name or entry.teacher.username
        teacher_username = entry.teacher.username
    semester_name = entry.semester.name if entry.semester else None
    ay_id = entry.semester.academic_year_id if entry.semester else None
    ay_name = entry.semester.academic_year.name if entry.semester and entry.semester.academic_year else None
    day_name = DAY_NAMES[entry.day_of_week] if 0 <= entry.day_of_week <= 6 else f"Day {entry.day_of_week}"

    return TimetableEntryDetailOut(
        id=entry.id,
        subject_id=entry.subject_id,
        subject_name=subject_name,
        subject_code=subject_code,
        teacher_id=entry.teacher_id,
        teacher_name=teacher_name,
        teacher_username=teacher_username,
        section=entry.section,
        semester_id=entry.semester_id,
        semester_name=semester_name,
        academic_year_id=ay_id,
        academic_year_name=ay_name,
        day_of_week=entry.day_of_week,
        day_name=day_name,
        period_number=entry.period_number,
        start_time=entry.start_time,
        end_time=entry.end_time,
        is_active=getattr(entry, 'is_active', True),
        created_at=entry.created_at
    )


@router.get("/entries", response_model=List[TimetableEntryDetailOut])
def list_timetable_entries(
    semester_id: Optional[int] = None,
    section: Optional[str] = None,
    day_of_week: Optional[int] = None,
    teacher_id: Optional[int] = None,
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List timetable entries with role-based scoping:
    - Admin: can view all or filter freely.
    - Teacher: if no filters specified, defaults to their assigned entries.
    - Student: if student record has section, can view their section's timetable.
    """
    query = db.query(TimetableEntry)

    # Role scoping
    if current_user.role in ("teacher", "faculty") and not teacher_id and not section:
        query = query.filter(TimetableEntry.teacher_id == current_user.id)
    elif current_user.role == "student" and not section:
        if current_user.student and current_user.student.section:
            sec_vars = get_section_variants(current_user.student.section)
            query = query.filter(TimetableEntry.section.in_(sec_vars))

    if is_active is not None:
        query = query.filter(TimetableEntry.is_active == is_active)
    if semester_id:
        query = query.filter(TimetableEntry.semester_id == semester_id)
    if section:
        sec_vars = get_section_variants(section)
        query = query.filter(TimetableEntry.section.in_(sec_vars))
    if day_of_week is not None:
        query = query.filter(TimetableEntry.day_of_week == day_of_week)
    if teacher_id:
        query = query.filter(TimetableEntry.teacher_id == teacher_id)

    entries = query.order_by(TimetableEntry.day_of_week, TimetableEntry.period_number).all()
    return [_format_timetable_detail(e) for e in entries]


@router.post("/entries", response_model=TimetableEntryDetailOut, status_code=status.HTTP_201_CREATED)
def create_timetable_entry(
    entry_in: TimetableEntryCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Only Administrator can create timetable entries."""
    # 1. Verify Semester exists
    semester = db.query(Semester).filter(Semester.id == entry_in.semester_id).first()
    if not semester:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Semester not found.")

    # 2. Verify Subject exists and belongs to Semester
    subject = db.query(Subject).filter(Subject.id == entry_in.subject_id).first()
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found.")
    if subject.semester_id != semester.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Subject '{subject.code}' belongs to semester #{subject.semester_id}, not semester '{semester.name}'."
        )

    # 3. Verify Teacher
    section_clean = entry_in.section.strip().upper()
    if entry_in.teacher_id:
        teacher = db.query(User).filter(User.id == entry_in.teacher_id).first()
        if not teacher:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher user not found.")
        if teacher.role not in ("teacher", "faculty", "admin"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User '{teacher.username}' cannot be assigned as teacher (role is '{teacher.role}')."
            )
        if not teacher.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Teacher account '{teacher.username}' is inactive."
            )

    # 4. Comprehensive Conflict Detection (Section period/time & Teacher double-booking)
    conflicts = detect_timetable_conflicts(
        db=db,
        semester_id=entry_in.semester_id,
        section=section_clean,
        day_of_week=entry_in.day_of_week,
        period_number=entry_in.period_number,
        start_time=entry_in.start_time,
        end_time=entry_in.end_time,
        teacher_id=entry_in.teacher_id
    )
    if conflicts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Timetable conflict detected: {'; '.join(conflicts)}"
        )

    entry = TimetableEntry(
        subject_id=entry_in.subject_id,
        teacher_id=entry_in.teacher_id,
        section=section_clean,
        semester_id=entry_in.semester_id,
        day_of_week=entry_in.day_of_week,
        period_number=entry_in.period_number,
        start_time=entry_in.start_time,
        end_time=entry_in.end_time
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return _format_timetable_detail(entry)


@router.put("/entries/{entry_id}", response_model=TimetableEntryDetailOut)
def update_timetable_entry(
    entry_id: int,
    entry_in: TimetableEntryUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Only Administrator can update timetable entries."""
    entry = db.query(TimetableEntry).filter(TimetableEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timetable entry not found.")

    new_sub_id = entry_in.subject_id if entry_in.subject_id is not None else entry.subject_id
    new_teacher_id = entry_in.teacher_id if entry_in.teacher_id is not None else entry.teacher_id
    new_section = entry_in.section.strip().upper() if entry_in.section is not None else entry.section
    new_day = entry_in.day_of_week if entry_in.day_of_week is not None else entry.day_of_week
    new_period = entry_in.period_number if entry_in.period_number is not None else entry.period_number
    new_start = entry_in.start_time if entry_in.start_time is not None else entry.start_time
    new_end = entry_in.end_time if entry_in.end_time is not None else entry.end_time

    # Validate end > start
    if new_end <= new_start:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="End time must be after start time.")

    # Validate Subject
    sub = db.query(Subject).filter(Subject.id == new_sub_id).first()
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found.")

    # Validate Teacher
    if new_teacher_id:
        t = db.query(User).filter(User.id == new_teacher_id).first()
        if not t:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher user not found.")
        if t.role not in ("teacher", "faculty", "admin"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"User '{t.username}' is not a teacher.")
        if not t.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Teacher '{t.username}' is inactive.")

    # Validate Conflicts
    conflicts = detect_timetable_conflicts(
        db=db,
        semester_id=entry.semester_id,
        section=new_section,
        day_of_week=new_day,
        period_number=new_period,
        start_time=new_start,
        end_time=new_end,
        teacher_id=new_teacher_id,
        exclude_entry_id=entry.id
    )
    if conflicts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Timetable conflict detected: {'; '.join(conflicts)}"
        )

    entry.subject_id = new_sub_id
    entry.teacher_id = new_teacher_id
    entry.section = new_section
    entry.day_of_week = new_day
    entry.period_number = new_period
    entry.start_time = new_start
    entry.end_time = new_end

    db.commit()
    db.refresh(entry)
    return _format_timetable_detail(entry)


@router.delete("/entries/{entry_id}")
def delete_timetable_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Only Administrator can delete timetable entries."""
    entry = db.query(TimetableEntry).filter(TimetableEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timetable entry not found.")

    db.delete(entry)
    db.commit()
    return {"success": True, "message": "Timetable entry deleted successfully."}


# ─── Timetable Import (Preview & Commit) ──────────────────────────────────────

@router.post("/import/preview", response_model=TimetableImportPreviewResponse)
async def preview_timetable_import_endpoint(
    file: Optional[UploadFile] = File(None),
    payload: Optional[Dict[str, Any]] = Body(None),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """
    Validates uploaded CSV/Excel timetable file or raw JSON rows.
    Returns detailed preview with row statuses (valid, conflict, error) and resolved IDs.
    """
    raw_rows: List[Dict[str, Any]] = []

    if file:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")
        try:
            raw_rows = parse_raw_file_to_rows(content, file.filename or "upload.csv")
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"File parsing error: {str(e)}")
    elif payload:
        if "rows" in payload and isinstance(payload["rows"], list):
            raw_rows = payload["rows"]
        elif "csv_text" in payload and isinstance(payload["csv_text"], str):
            raw_rows = parse_raw_file_to_rows(payload["csv_text"].encode("utf-8"), "upload.csv")
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid payload: Provide either a file upload, 'rows' array, or 'csv_text'."
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No timetable data provided. Upload a file or send JSON rows."
        )

    if not raw_rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No data rows found in the provided timetable."
        )

    return preview_timetable_import(db, raw_rows)


@router.post("/import/commit")
def commit_timetable_import_endpoint(
    payload: TimetableImportCommitRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """
    Saves confirmed/corrected timetable rows from preview into the database inside a transaction.
    """
    if not payload.rows:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No rows provided for import.")

    result = commit_timetable_import(db, payload.rows, payload.replace_conflicts)
    return result


@router.get("/template/csv")
def download_timetable_template():
    """Returns a standardized CSV template for timetable import."""
    csv_content = (
        "day,period,start_time,end_time,semester,section,subject,teacher\n"
        "Monday,1,09:00,10:00,Semester 5,CSE-A,CS501,teacher_username\n"
        "Monday,2,10:00,11:00,Semester 5,CSE-A,CS502,teacher_username\n"
        "Tuesday,1,09:00,10:00,Semester 5,CSE-A,CS503,teacher_username\n"
    )
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=timetable_template.csv"}
    )


# ─── Scheduled Class Lookup API ──────────────────────────────────────────────

@router.get("/lookup", response_model=ScheduledClassLookupResponse)
def lookup_scheduled_classes(
    section: Optional[str] = None,
    semester_id: Optional[int] = None,
    teacher_id: Optional[int] = None,
    day_of_week: Optional[int] = None,
    time_val: Optional[str] = Query(None, alias="time"),
    date_val: Optional[date] = Query(None, alias="date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves the scheduled class(es) for a specific day and time.
    - If date is supplied, evaluates holidays, Sunday/weekends, semester bounds, and active substitute authorizations.
    - If time is supplied, filters for the class matching the time window.
    """
    target_date: Optional[date] = date_val
    computed_day = day_of_week

    is_holiday = False
    holiday_name: Optional[str] = None
    is_outside_semester = False
    status_msg: Optional[str] = None

    if target_date:
        computed_day = target_date.weekday()

        # 1. Holiday Check
        hol = db.query(Holiday).filter(Holiday.date == target_date).first()
        if hol:
            is_holiday = True
            holiday_name = hol.name
            status_msg = f"Holiday: {hol.name}"

        # 2. Weekend Check (Sunday is day 6)
        if computed_day == 6 and not is_holiday:
            is_holiday = True
            holiday_name = "Sunday (Weekend)"
            status_msg = "Non-working day (Sunday)"

        # 3. Semester boundary check
        if semester_id:
            sem = db.query(Semester).filter(Semester.id == semester_id).first()
            if sem:
                if target_date < sem.start_date or target_date > sem.end_date:
                    is_outside_semester = True
                    status_msg = f"Date {target_date} is outside semester active duration ({sem.start_date} to {sem.end_date})"

    if computed_day is None:
        computed_day = datetime.date.today().weekday()

    day_name = DAY_NAMES[computed_day] if 0 <= computed_day <= 6 else f"Day {computed_day}"

    # Query active timetable entries
    query = db.query(TimetableEntry).filter(
        TimetableEntry.day_of_week == computed_day,
        TimetableEntry.is_active == True
    )

    if semester_id:
        query = query.filter(TimetableEntry.semester_id == semester_id)
    if section:
        norm_sec = section.strip().upper()
        exact_exists = db.query(TimetableEntry.id).filter(
            TimetableEntry.day_of_week == computed_day,
            TimetableEntry.is_active == True,
            TimetableEntry.section == norm_sec
        ).first() is not None
        if exact_exists:
            query = query.filter(TimetableEntry.section == norm_sec)
        else:
            sec_vars = get_section_variants(norm_sec)
            query = query.filter(TimetableEntry.section.in_(sec_vars))

    # Time filter
    parsed_time: Optional[time] = None
    if time_val:
        try:
            parsed_time = parse_time_value(time_val)
        except Exception:
            pass

    entries = query.order_by(TimetableEntry.period_number).all()
    results: List[ScheduledClassLookupEntry] = []

    for e in entries:
        if parsed_time:
            if not (e.start_time <= parsed_time <= e.end_time):
                continue

        # Check substitute authorization for this entry on target_date
        is_sub = False
        eff_teacher_id = e.teacher_id
        eff_teacher_name = (e.teacher.full_name or e.teacher.username) if e.teacher else None
        orig_teacher_name = eff_teacher_name
        sub_reason = None

        if target_date:
            sub_auth = db.query(SubstituteAuthorization).filter(
                SubstituteAuthorization.timetable_entry_id == e.id,
                SubstituteAuthorization.date == target_date,
                SubstituteAuthorization.status == "authorized"
            ).first()
            if sub_auth and sub_auth.substitute_teacher:
                is_sub = True
                eff_teacher_id = sub_auth.substitute_teacher_id
                eff_teacher_name = sub_auth.substitute_teacher.full_name or sub_auth.substitute_teacher.username
                sub_reason = sub_auth.reason

        # Teacher filter (filter against effective teacher)
        if teacher_id and eff_teacher_id != teacher_id and e.teacher_id != teacher_id:
            continue

        results.append(
            ScheduledClassLookupEntry(
                id=e.id,
                subject_id=e.subject_id,
                subject_name=e.subject.name if e.subject else f"Subject #{e.subject_id}",
                subject_code=e.subject.code if e.subject else "",
                section=e.section,
                semester_id=e.semester_id,
                semester_name=e.semester.name if e.semester else f"Semester #{e.semester_id}",
                day_of_week=e.day_of_week,
                day_name=DAY_NAMES[e.day_of_week],
                period_number=e.period_number,
                start_time=e.start_time.strftime("%H:%M:%S"),
                end_time=e.end_time.strftime("%H:%M:%S"),
                teacher_id=e.teacher_id,
                teacher_name=orig_teacher_name,
                is_substituted=is_sub,
                effective_teacher_id=eff_teacher_id,
                effective_teacher_name=eff_teacher_name,
                substitution_reason=sub_reason
            )
        )

    return ScheduledClassLookupResponse(
        date=str(target_date) if target_date else None,
        day_of_week=computed_day,
        day_name=day_name,
        is_holiday=is_holiday,
        holiday_name=holiday_name,
        is_outside_semester=is_outside_semester,
        status_message=status_msg,
        total_entries=len(results),
        entries=results
    )


# ─── Holidays Management ──────────────────────────────────────────────────────

@router.get("/holidays", response_model=List[HolidayOut])
def list_holidays(
    academic_year_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """View calendar holidays."""
    q = db.query(Holiday)
    if academic_year_id:
        q = q.filter(Holiday.academic_year_id == academic_year_id)
    return q.order_by(Holiday.date.asc()).all()


@router.post("/holidays", response_model=HolidayOut, status_code=status.HTTP_201_CREATED)
def create_holiday(
    holiday_in: HolidayCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Only Administrator can add holidays."""
    existing = db.query(Holiday).filter(Holiday.date == holiday_in.date).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A holiday '{existing.name}' is already registered for date {holiday_in.date}."
        )

    hol = Holiday(
        name=holiday_in.name.strip(),
        date=holiday_in.date,
        academic_year_id=holiday_in.academic_year_id,
        description=holiday_in.description.strip() if holiday_in.description else None
    )
    db.add(hol)
    db.commit()
    db.refresh(hol)
    return hol


@router.delete("/holidays/{holiday_id}")
def delete_holiday(
    holiday_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Only Administrator can remove holidays."""
    hol = db.query(Holiday).filter(Holiday.id == holiday_id).first()
    if not hol:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holiday not found.")

    db.delete(hol)
    db.commit()
    return {"success": True, "message": "Holiday deleted successfully."}
