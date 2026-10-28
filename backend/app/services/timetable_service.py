import io
import csv
import datetime
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.timetable import TimetableEntry, get_section_variants
from app.models.subject import Subject
from app.models.semester import Semester
from app.models.user import User
from app.models.academic_year import AcademicYear
from app.models.holiday import Holiday
from app.models.substitute_auth import SubstituteAuthorization
from app.schemas.academic import (
    DAY_NAMES,
    TimetableImportPreviewResponse,
    TimetableImportPreviewRow,
    TimetableImportRowResolved
)

DAY_MAP = {
    "monday": 0, "mon": 0, "m": 0, "0": 0,
    "tuesday": 1, "tue": 1, "t": 1, "1": 1,
    "wednesday": 2, "wed": 2, "w": 2, "2": 2,
    "thursday": 3, "thu": 3, "th": 3, "3": 3,
    "friday": 4, "fri": 4, "f": 4, "4": 4,
    "saturday": 5, "sat": 5, "s": 5, "5": 5,
    "sunday": 6, "sun": 6, "su": 6, "6": 6,
}


def parse_time_value(time_input: Any) -> datetime.time:
    """Parses various time representations into datetime.time."""
    if isinstance(time_input, datetime.time):
        return time_input
    if isinstance(time_input, datetime.datetime):
        return time_input.time()
    
    val_str = str(time_input).strip()
    # Try various standard formats
    for fmt in ("%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M:%S %p", "%I %p"):
        try:
            return datetime.datetime.strptime(val_str, fmt).time()
        except ValueError:
            pass
    raise ValueError(f"Invalid time format '{val_str}'. Use HH:MM or HH:MM:SS.")


def times_overlap(s1: datetime.time, e1: datetime.time, s2: datetime.time, e2: datetime.time) -> bool:
    """Checks whether two time intervals overlap (open intervals)."""
    return max(s1, s2) < min(e1, e2)


def detect_timetable_conflicts(
    db: Session,
    semester_id: int,
    section: str,
    day_of_week: int,
    period_number: int,
    start_time: datetime.time,
    end_time: datetime.time,
    teacher_id: Optional[int],
    exclude_entry_id: Optional[int] = None
) -> List[str]:
    """
    Detects:
    1. Conflicting Section Periods (Section cannot have two classes at same period or overlapping time).
    2. Conflicting Teacher Assignments (Teacher cannot be double-booked at same day/period or overlapping time).
    Only active timetable entries are considered.
    """
    conflicts: List[str] = []
    clean_section = section.strip().upper()
    sec_vars = get_section_variants(clean_section)
    day_name = DAY_NAMES[day_of_week] if 0 <= day_of_week <= 6 else f"Day {day_of_week}"

    # 1. Section conflict check (same semester, section variants, day)
    sec_query = db.query(TimetableEntry).filter(
        TimetableEntry.semester_id == semester_id,
        TimetableEntry.section.in_(sec_vars),
        TimetableEntry.day_of_week == day_of_week,
        TimetableEntry.is_active == True
    )
    if exclude_entry_id:
        sec_query = sec_query.filter(TimetableEntry.id != exclude_entry_id)

    for entry in sec_query.all():
        sub_desc = entry.subject.name if entry.subject else f"Subject #{entry.subject_id}"
        if entry.period_number == period_number:
            conflicts.append(
                f"Section {clean_section} already has Period {period_number} assigned to '{sub_desc}' on {day_name}."
            )
        elif times_overlap(start_time, end_time, entry.start_time, entry.end_time):
            conflicts.append(
                f"Section {clean_section} has overlapping class '{sub_desc}' from {entry.start_time.strftime('%H:%M')} to {entry.end_time.strftime('%H:%M')} on {day_name}."
            )

    # 2. Teacher conflict check (across ALL semesters & sections)
    if teacher_id:
        t_query = db.query(TimetableEntry).filter(
            TimetableEntry.teacher_id == teacher_id,
            TimetableEntry.day_of_week == day_of_week,
            TimetableEntry.is_active == True
        )

        if exclude_entry_id:
            t_query = t_query.filter(TimetableEntry.id != exclude_entry_id)

        for entry in t_query.all():
            t_name = entry.teacher.full_name or entry.teacher.username if entry.teacher else f"Teacher #{teacher_id}"
            sub_desc = entry.subject.name if entry.subject else f"Subject #{entry.subject_id}"
            if entry.period_number == period_number:
                conflicts.append(
                    f"Teacher {t_name} is already assigned to Period {period_number} in Section {entry.section} ('{sub_desc}') on {day_name}."
                )
            elif times_overlap(start_time, end_time, entry.start_time, entry.end_time):
                conflicts.append(
                    f"Teacher {t_name} is already teaching '{sub_desc}' in Section {entry.section} from {entry.start_time.strftime('%H:%M')} to {entry.end_time.strftime('%H:%M')} on {day_name}."
                )

    return conflicts


def parse_raw_file_to_rows(file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
    """
    Parses uploaded CSV or Excel file bytes into a list of row dictionaries.
    """
    filename_lower = filename.lower()
    raw_rows: List[Dict[str, Any]] = []

    if filename_lower.endswith(".csv"):
        # Decode text with utf-8-sig to strip potential BOM
        text = file_bytes.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            raw_rows.append(dict(row))
    elif filename_lower.endswith((".xlsx", ".xls")):
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        sheet = wb.active
        rows_iter = sheet.iter_rows(values_only=True)
        header_row = next(rows_iter, None)
        if not header_row:
            return []
        headers = [str(h).strip() if h is not None else f"col_{idx}" for idx, h in enumerate(header_row)]
        for r in rows_iter:
            if not any(r):
                continue  # skip completely blank rows
            row_dict = {}
            for idx, val in enumerate(r):
                if idx < len(headers):
                    row_dict[headers[idx]] = val
            raw_rows.append(row_dict)
    else:
        raise ValueError(f"Unsupported file format '{filename}'. Please upload a CSV (.csv) or Excel (.xlsx) file.")

    return raw_rows


def normalize_header_key(k: str) -> str:
    cleaned = k.strip().lower().replace(" ", "_").replace("-", "_")
    if cleaned in ("day", "day_of_week", "dayofweek", "weekday"):
        return "day"
    if cleaned in ("period", "period_number", "period_no", "periodnum"):
        return "period"
    if cleaned in ("start", "start_time", "starttime"):
        return "start_time"
    if cleaned in ("end", "end_time", "endtime"):
        return "end_time"
    if cleaned in ("semester", "semester_name", "semester_id", "sem"):
        return "semester"
    if cleaned in ("section", "sec"):
        return "section"
    if cleaned in ("subject", "subject_code", "subject_name", "course"):
        return "subject"
    if cleaned in ("teacher", "teacher_username", "teacher_email", "faculty", "instructor", "professor"):
        return "teacher"
    return cleaned


def preview_timetable_import(db: Session, raw_rows: List[Dict[str, Any]]) -> TimetableImportPreviewResponse:
    """
    Validates imported rows against schema, business rules, and database records.
    Detects missing columns, unresolvable entities, internal batch conflicts, and DB overlaps.
    """
    preview_rows: List[TimetableImportPreviewRow] = []

    # Pre-fetch lookup caches
    all_semesters = db.query(Semester).all()
    sem_by_id = {s.id: s for s in all_semesters}
    sem_by_name = {s.name.strip().upper(): s for s in all_semesters}

    all_subjects = db.query(Subject).all()
    sub_by_id = {s.id: s for s in all_subjects}
    sub_by_code = {s.code.strip().upper(): s for s in all_subjects}
    sub_by_name = {s.name.strip().upper(): s for s in all_subjects}

    all_teachers = db.query(User).filter(User.role.in_(["teacher", "faculty", "admin"])).all()
    teacher_by_id = {t.id: t for t in all_teachers}
    teacher_by_username = {t.username.strip().lower(): t for t in all_teachers}
    teacher_by_email = {t.email.strip().lower(): t for t in all_teachers if t.email}

    # Tracking for internal batch conflict detection:
    # Key 1: (semester_id, section, day_of_week) -> list of (row_idx, period_number, start_time, end_time)
    section_batch_slots: Dict[Tuple[int, str, int], List[Tuple[int, int, datetime.time, datetime.time]]] = {}
    # Key 2: (teacher_id, day_of_week) -> list of (row_idx, period_number, start_time, end_time)
    teacher_batch_slots: Dict[Tuple[int, int], List[Tuple[int, int, datetime.time, datetime.time]]] = {}

    valid_count = 0
    conflict_count = 0
    error_count = 0

    for idx, row in enumerate(raw_rows, start=1):
        row_errors: List[str] = []
        normalized_row = {normalize_header_key(k): (str(v).strip() if v is not None else "") for k, v in row.items()}

        # 1. Check required fields
        required_keys = ["day", "period", "start_time", "end_time", "semester", "section", "subject", "teacher"]
        missing = [k for k in required_keys if not normalized_row.get(k)]
        if missing:
            row_errors.append(f"Missing required fields: {', '.join(missing)}")

        # 2. Parse Day of week
        day_raw = normalized_row.get("day", "").lower()
        day_of_week: Optional[int] = DAY_MAP.get(day_raw)
        if day_of_week is None:
            if day_raw.isdigit() and 0 <= int(day_raw) <= 6:
                day_of_week = int(day_raw)
            else:
                row_errors.append(f"Invalid day '{normalized_row.get('day')}'. Expected Monday-Sunday or 0-6.")
                day_of_week = 0

        # 3. Parse Period Number
        period_raw = normalized_row.get("period", "")
        period_number: Optional[int] = None
        try:
            period_number = int(float(period_raw))
            if period_number < 1:
                row_errors.append("Period number must be >= 1.")
        except Exception:
            row_errors.append(f"Invalid period number '{period_raw}'. Expected integer.")
            period_number = 1

        # 4. Parse Times
        start_t: Optional[datetime.time] = None
        end_t: Optional[datetime.time] = None
        try:
            start_t = parse_time_value(normalized_row.get("start_time"))
        except Exception as te:
            row_errors.append(str(te))
        try:
            end_t = parse_time_value(normalized_row.get("end_time"))
        except Exception as te:
            row_errors.append(str(te))

        if start_t and end_t and start_t >= end_t:
            row_errors.append(f"End time ({end_t.strftime('%H:%M')}) must be strictly after start time ({start_t.strftime('%H:%M')}).")

        # 5. Resolve Semester
        sem_raw = normalized_row.get("semester", "")
        resolved_semester: Optional[Semester] = None
        if sem_raw.isdigit() and int(sem_raw) in sem_by_id:
            resolved_semester = sem_by_id[int(sem_raw)]
        elif sem_raw.strip().upper() in sem_by_name:
            resolved_semester = sem_by_name[sem_raw.strip().upper()]
        else:
            row_errors.append(f"Semester '{sem_raw}' not found in database.")

        # 6. Resolve Subject
        sub_raw = normalized_row.get("subject", "")
        resolved_subject: Optional[Subject] = None
        if sub_raw.isdigit() and int(sub_raw) in sub_by_id:
            resolved_subject = sub_by_id[int(sub_raw)]
        elif sub_raw.strip().upper() in sub_by_code:
            resolved_subject = sub_by_code[sub_raw.strip().upper()]
        elif sub_raw.strip().upper() in sub_by_name:
            resolved_subject = sub_by_name[sub_raw.strip().upper()]
        else:
            row_errors.append(f"Subject '{sub_raw}' not found in database.")

        # If subject resolved, verify it matches the resolved semester
        if resolved_subject and resolved_semester and resolved_subject.semester_id != resolved_semester.id:
            row_errors.append(
                f"Subject '{resolved_subject.code}' belongs to semester #{resolved_subject.semester_id}, "
                f"not '{resolved_semester.name}'."
            )

        # 7. Resolve Section
        section_val = normalized_row.get("section", "").strip().upper()
        if not section_val:
            row_errors.append("Section cannot be blank.")

        # 8. Resolve Teacher
        teacher_raw = normalized_row.get("teacher", "").strip().lower()
        resolved_teacher: Optional[User] = None
        if teacher_raw.isdigit() and int(teacher_raw) in teacher_by_id:
            resolved_teacher = teacher_by_id[int(teacher_raw)]
        elif teacher_raw in teacher_by_username:
            resolved_teacher = teacher_by_username[teacher_raw]
        elif teacher_raw in teacher_by_email:
            resolved_teacher = teacher_by_email[teacher_raw]
        else:
            row_errors.append(f"Teacher '{normalized_row.get('teacher')}' not found or does not have teacher/faculty role.")

        if resolved_teacher and not resolved_teacher.is_active:
            row_errors.append(f"Teacher account '{resolved_teacher.username}' is inactive.")

        # Conflict checks if baseline validation passed so far
        is_conflict = False
        resolved_obj: Optional[TimetableImportRowResolved] = None

        if (
            not row_errors
            and resolved_semester
            and resolved_subject
            and resolved_teacher
            and start_t
            and end_t
            and period_number
            and day_of_week is not None
        ):
            # A. Internal Batch Conflicts
            sec_key = (resolved_semester.id, section_val, day_of_week)
            if sec_key in section_batch_slots:
                for (prev_row, prev_period, prev_s, prev_e) in section_batch_slots[sec_key]:
                    if prev_period == period_number:
                        row_errors.append(f"Internal conflict: Section {section_val} has Period {period_number} assigned multiple times in this file (matches row {prev_row}).")
                        is_conflict = True
                    elif times_overlap(start_t, end_t, prev_s, prev_e):
                        row_errors.append(f"Internal conflict: Section {section_val} time overlaps with row {prev_row} ({prev_s.strftime('%H:%M')}-{prev_e.strftime('%H:%M')}).")
                        is_conflict = True

            t_key = (resolved_teacher.id, day_of_week)
            if t_key in teacher_batch_slots:
                for (prev_row, prev_period, prev_s, prev_e) in teacher_batch_slots[t_key]:
                    if prev_period == period_number:
                        row_errors.append(f"Internal conflict: Teacher {resolved_teacher.username} is assigned to multiple classes in Period {period_number} (matches row {prev_row}).")
                        is_conflict = True
                    elif times_overlap(start_t, end_t, prev_s, prev_e):
                        row_errors.append(f"Internal conflict: Teacher {resolved_teacher.username} time overlaps with row {prev_row} ({prev_s.strftime('%H:%M')}-{prev_e.strftime('%H:%M')}).")
                        is_conflict = True

            # Record in batch tracker
            section_batch_slots.setdefault(sec_key, []).append((idx, period_number, start_t, end_t))
            teacher_batch_slots.setdefault(t_key, []).append((idx, period_number, start_t, end_t))

            # B. Database Conflicts
            db_conflicts = detect_timetable_conflicts(
                db=db,
                semester_id=resolved_semester.id,
                section=section_val,
                day_of_week=day_of_week,
                period_number=period_number,
                start_time=start_t,
                end_time=end_t,
                teacher_id=resolved_teacher.id
            )
            if db_conflicts:
                is_conflict = True
                row_errors.extend(db_conflicts)

            resolved_obj = TimetableImportRowResolved(
                semester_id=resolved_semester.id,
                semester_name=resolved_semester.name,
                subject_id=resolved_subject.id,
                subject_code=resolved_subject.code,
                subject_name=resolved_subject.name,
                teacher_id=resolved_teacher.id,
                teacher_name=resolved_teacher.full_name or resolved_teacher.username,
                section=section_val,
                day_of_week=day_of_week,
                day_name=DAY_NAMES[day_of_week],
                period_number=period_number,
                start_time=start_t.strftime("%H:%M:%S"),
                end_time=end_t.strftime("%H:%M:%S")
            )

        status_str = "valid"
        if row_errors:
            if is_conflict:
                status_str = "conflict"
                conflict_count += 1
            else:
                status_str = "error"
                error_count += 1
        else:
            valid_count += 1

        preview_rows.append(
            TimetableImportPreviewRow(
                row_index=idx,
                status=status_str,
                errors=row_errors,
                raw_data=dict(row),
                resolved=resolved_obj
            )
        )

    return TimetableImportPreviewResponse(
        total_rows=len(preview_rows),
        valid_count=valid_count,
        conflict_count=conflict_count,
        error_count=error_count,
        rows=preview_rows
    )


def commit_timetable_import(
    db: Session,
    rows: List[TimetableImportRowResolved],
    replace_conflicts: bool = False
) -> Dict[str, Any]:
    """
    Commits confirmed rows to the database inside a transaction.
    If replace_conflicts=True, removes conflicting entries before inserting.
    """
    imported_count = 0
    skipped_count = 0
    errors: List[str] = []

    for r in rows:
        start_t = parse_time_value(r.start_time)
        end_t = parse_time_value(r.end_time)

        conflicts = detect_timetable_conflicts(
            db=db,
            semester_id=r.semester_id,
            section=r.section,
            day_of_week=r.day_of_week,
            period_number=r.period_number,
            start_time=start_t,
            end_time=end_t,
            teacher_id=r.teacher_id
        )

        if conflicts:
            if replace_conflicts:
                # Remove section and teacher duplicate slot
                db.query(TimetableEntry).filter(
                    TimetableEntry.semester_id == r.semester_id,
                    TimetableEntry.section == r.section.strip().upper(),
                    TimetableEntry.day_of_week == r.day_of_week,
                    TimetableEntry.period_number == r.period_number
                ).delete()
            else:
                errors.append(f"Row {r.subject_code} ({r.day_name} P{r.period_number}) conflict: {'; '.join(conflicts)}")
                skipped_count += 1
                continue

        entry = TimetableEntry(
            subject_id=r.subject_id,
            teacher_id=r.teacher_id,
            section=r.section.strip().upper(),
            semester_id=r.semester_id,
            day_of_week=r.day_of_week,
            period_number=r.period_number,
            start_time=start_t,
            end_time=end_t
        )
        db.add(entry)
        imported_count += 1

    db.commit()
    return {
        "success": True,
        "imported_count": imported_count,
        "skipped_count": skipped_count,
        "errors": errors if errors else None,
        "message": f"Successfully imported {imported_count} timetable entries (skipped: {skipped_count})."
    }
