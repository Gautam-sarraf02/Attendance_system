from typing import Optional, List, Callable, Type
from functools import wraps

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.auth.jwt_handler import decode_access_token

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    token = credentials.credentials
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username: str = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account"
        )

    return user


def get_current_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required"
        )
    return current_user


# ─── Phase 1: New role-based dependency guards ──────────────────

def get_current_teacher(
    current_user: User = Depends(get_current_user)
) -> User:
    """Require the current user to have 'teacher' or 'faculty' role."""
    if current_user.role not in ("teacher", "faculty"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Teacher access required"
        )
    return current_user


def get_current_student(
    current_user: User = Depends(get_current_user)
) -> User:
    """Require the current user to have 'student' role with a linked student_id."""
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student access required"
        )
    if not current_user.student_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student account is not linked to any student profile"
        )
    return current_user


def require_roles(*allowed_roles: str):
    """
    Factory that returns a FastAPI dependency restricting access to specific roles.

    Usage:
        @router.get("/admin-or-teacher", dependencies=[Depends(require_roles("admin", "teacher"))])
        def protected_endpoint(): ...
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access restricted to roles: {', '.join(allowed_roles)}"
            )
        return current_user
    return role_checker


def verify_student_access(current_user: User, target_student_id: int) -> None:
    """
    Ensure students cannot access other students' private records.
    Admins and teachers are unrestricted.
    """
    if current_user.role == "student":
        if current_user.student_id != target_student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Students may only access their own records"
            )


def get_teacher_assigned_classes(teacher: User, db: Session) -> set[tuple[str, str]]:
    """
    Returns set of uppercase (subject_name/code, section) tuples assigned to the teacher
    either via direct timetable entries or active substitute authorizations for today.
    """
    import datetime
    from app.models.timetable import TimetableEntry, get_section_variants
    from app.models.subject import Subject
    from app.models.substitute_auth import SubstituteAuthorization

    today = datetime.date.today()
    assigned = set()

    # 1. Direct timetable entries
    direct_entries = (
        db.query(Subject.name, Subject.code, TimetableEntry.section)
        .select_from(TimetableEntry)
        .join(Subject, TimetableEntry.subject_id == Subject.id)
        .filter(TimetableEntry.teacher_id == teacher.id)
        .all()
    )
    for name, code, section in direct_entries:
        sec_vars = get_section_variants(section)
        for s_var in sec_vars:
            if name:
                assigned.add((name.strip().upper(), s_var))
            if code:
                assigned.add((code.strip().upper(), s_var))

    # 2. Substitute authorizations for today
    substitutions = (
        db.query(Subject.name, Subject.code, TimetableEntry.section)
        .select_from(SubstituteAuthorization)
        .join(TimetableEntry, SubstituteAuthorization.timetable_entry_id == TimetableEntry.id)
        .join(Subject, TimetableEntry.subject_id == Subject.id)
        .filter(
            SubstituteAuthorization.substitute_teacher_id == teacher.id,
            SubstituteAuthorization.status.in_(["authorized", "active"]),
            SubstituteAuthorization.date == today,
            TimetableEntry.is_active == True
        )
        .all()
    )
    for name, code, section in substitutions:
        sec_vars = get_section_variants(section)
        for s_var in sec_vars:
            if name:
                assigned.add((name.strip().upper(), s_var))
            if code:
                assigned.add((code.strip().upper(), s_var))

    return assigned


def verify_teacher_class_access(
    current_user: User,
    db: Session,
    subject: Optional[str] = None,
    section: Optional[str] = None,
    session_id: Optional[int] = None
) -> None:
    """
    Enforces that teachers can only access their assigned classes.
    Admins always pass.
    """
    if current_user.role == "admin":
        return

    if current_user.role not in ("teacher", "faculty"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Teacher or administrator access required"
        )

    from app.models.timetable import TimetableEntry
    from app.models.attendance_session import AttendanceSession

    # If session_id is provided, check session ownership
    if session_id:
        sess = db.query(AttendanceSession).filter(AttendanceSession.id == session_id).first()
        if sess and (sess.created_by == current_user.id or sess.teacher_id == current_user.id):
            return

    # If no timetable entries exist in the system yet, allow initial adoption
    total_timetable_entries = db.query(TimetableEntry).count()
    if total_timetable_entries == 0:
        return

    # If subject and section are provided, check against assigned classes
    if subject and section:
        from app.models.timetable import get_section_variants
        assigned = get_teacher_assigned_classes(current_user, db)
        subj_norm = subject.strip().upper()
        sec_vars = get_section_variants(section)
        is_assigned = any((subj_norm, s_var) in assigned for s_var in sec_vars)
        if not is_assigned:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: You are not assigned to '{subject}' ({section})"
            )

