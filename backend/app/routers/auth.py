from datetime import timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app.models.user import User
from app.models.student import Student
from app.models.face_enrollment import FaceEnrollment
from app.models.face_sample import FaceSample
from app.models.timetable import TimetableEntry
from app.schemas.user import (
    UserLogin,
    UserCreate,
    UserUpdate,
    UserOut,
    FacultyOut,
    FacultyCreate,
    FacultyUpdate,
    UserListResponse,
    Token,
    PasswordChange,
    SetupAdminRequest,
)
from app.auth.jwt_handler import verify_password, get_password_hash, create_access_token
from app.auth.deps import get_current_user, get_current_admin
from app.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication & Access Control"])


@router.post("/login", response_model=Token)
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticate an Admin, Teacher, or Student.
    Supports login via username, email, or student roll number (for student users).
    """
    identifier = login_data.username.strip()

    # 1. Direct username or email match
    user = db.query(User).filter(
        or_(User.username == identifier, User.email == identifier)
    ).first()

    # 2. If not found, check if identifier is a student roll number linked to a user account
    if not user:
        student = db.query(Student).filter(Student.roll_number == identifier).first()
        if student and student.user_account:
            # student.user_account is list or single user depending on backref
            if isinstance(student.user_account, list) and len(student.user_account) > 0:
                user = student.user_account[0]
            elif isinstance(student.user_account, User):
                user = student.user_account

    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is deactivated. Please contact an administrator."
        )

    # Validate selected role against actual user role in database
    if login_data.role:
        req_role = login_data.role.strip().lower()
        if req_role in ("faculty", "teacher"):
            allowed_roles = {"faculty", "teacher"}
            display_req = "Faculty"
        elif req_role == "admin":
            allowed_roles = {"admin"}
            display_req = "Admin"
        elif req_role == "student":
            allowed_roles = {"student"}
            display_req = "Student"
        else:
            allowed_roles = {req_role}
            display_req = req_role.capitalize()

        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: This account is registered as '{user.role}', which does not match the selected '{display_req}' role."
            )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user.username,
            "role": user.role,
            "id": user.id,
            "student_id": user.student_id,
        },
        expires_delta=access_token_expires,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user,
    }


@router.post("/setup-admin", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def setup_initial_admin(admin_data: SetupAdminRequest, db: Session = Depends(get_db)):
    """
    Secure one-time bootstrap endpoint to initialize the first Administrator.
    Locked once an administrator already exists in the system.
    """
    admin_count = db.query(User).filter(User.role == "admin").count()
    if admin_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrator account is already set up. Initial setup is locked.",
        )

    if len(admin_data.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long for security.",
        )

    username = admin_data.username.strip()
    if not username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username cannot be empty.",
        )

    # Check collision
    existing = db.query(User).filter(
        or_(User.username == username, User.email == admin_data.email)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already in use.",
        )

    admin_user = User(
        username=username,
        password_hash=get_password_hash(admin_data.password),
        full_name=admin_data.full_name or "System Administrator",
        email=admin_data.email,
        role="admin",
        is_active=True,
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)
    return admin_user


@router.get("/me", response_model=UserOut)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Fetch the authenticated user's profile."""
    return current_user


@router.post("/change-password")
def change_password(
    pwd_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Allow any authenticated user to securely change their own password."""
    if not verify_password(pwd_data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password verification failed.",
        )

    if len(pwd_data.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters long.",
        )

    current_user.password_hash = get_password_hash(pwd_data.new_password)
    db.commit()
    return {"success": True, "message": "Password changed successfully."}


# ─── Admin-Only User Management Endpoints ──────────────────────────────

@router.post("/register-user", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    user_data: UserCreate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Only Administrator can create users and assign roles (admin, teacher, faculty, student).
    """
    username = user_data.username.strip()
    if not username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username cannot be empty."
        )

    if len(user_data.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long."
        )

    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username is already registered."
        )

    if user_data.email:
        email_existing = db.query(User).filter(User.email == user_data.email).first()
        if email_existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address is already in use."
            )

    # Validate student_id if provided
    student_id = user_data.student_id
    if user_data.role == "student":
        if not student_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A valid student_id is required when creating a student user account."
            )
        student_obj = db.query(Student).filter(Student.id == student_id).first()
        if not student_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Student record with ID {student_id} not found."
            )
        # Check if student already has a user account
        existing_student_user = db.query(User).filter(User.student_id == student_id).first()
        if existing_student_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Student ID {student_id} is already linked to user '{existing_student_user.username}'."
            )
    else:
        # Non-student roles should not have student_id
        student_id = None

    new_user = User(
        username=username,
        password_hash=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        email=user_data.email,
        role=user_data.role or "teacher",
        student_id=student_id,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.get("/users", response_model=UserListResponse)
def list_users(
    role: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Only Administrator can list all system users."""
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    if search:
        search_pat = f"%{search}%"
        query = query.filter(
            or_(
                User.username.ilike(search_pat),
                User.full_name.ilike(search_pat),
                User.email.ilike(search_pat),
            )
        )

    total = query.count()
    users = query.order_by(User.id).offset(skip).limit(limit).all()
    return {"total": total, "users": users}


@router.get("/users/{user_id}", response_model=UserOut)
def get_user_by_id(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Administrator can view any user; other users can only view their own user account."""
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted: You may only view your own user account."
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return user


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Only Administrator can update users, change roles, deactivate accounts, or reset passwords."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    # Guard against admin locking themselves out
    if user.id == current_admin.id:
        if user_update.is_active is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot deactivate your own administrator account."
            )
        if user_update.role and user_update.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot remove administrator role from your own account."
            )

    if user_update.full_name is not None:
        user.full_name = user_update.full_name.strip()

    if user_update.email is not None:
        email_clean = str(user_update.email).strip()
        existing = db.query(User).filter(User.email == email_clean, User.id != user_id).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address is already in use by another user."
            )
        user.email = email_clean

    if user_update.role is not None:
        user.role = user_update.role

    if user_update.is_active is not None:
        user.is_active = user_update.is_active

    if user_update.student_id is not None:
        if user.role != "student":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot link student_id to a non-student user."
            )
        student_obj = db.query(Student).filter(Student.id == user_update.student_id).first()
        if not student_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Student with ID {user_update.student_id} not found."
            )
        user.student_id = user_update.student_id

    if user_update.password is not None:
        if len(user_update.password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long."
            )
        user.password_hash = get_password_hash(user_update.password)

    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Only Administrator can delete users. Prevents deleting self."""
    if user_id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own administrator account."
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    username = user.username
    db.delete(user)
    db.commit()
    return {"success": True, "message": f"User '{username}' deleted successfully."}


# ─── Faculty Management (Admin-Only) ─────────────────────────────────────────

def _format_faculty_out(user: User, db: Session) -> FacultyOut:
    """Format a User into a FacultyOut with face enrollment status and timetable assignments."""
    enrollment = (
        db.query(FaceEnrollment)
        .filter(FaceEnrollment.user_id == user.id)
        .order_by(FaceEnrollment.id.desc())
        .first()
    )
    has_face_enrollment = False
    enrollment_status = "Not Enrolled"
    enrollment_valid_until = None
    if enrollment:
        has_face_enrollment = (enrollment.status == "active")
        enrollment_status = enrollment.status.capitalize()
        enrollment_valid_until = str(enrollment.valid_until) if enrollment.valid_until else None

    sample_count = db.query(FaceSample).filter(FaceSample.user_id == user.id).count()

    timetable_entries = (
        db.query(TimetableEntry)
        .filter(TimetableEntry.teacher_id == user.id, TimetableEntry.is_active == True)
        .all()
    )
    assigned_subjects = sorted(list({entry.subject.name for entry in timetable_entries if entry.subject}))
    assigned_sections = sorted(list({entry.section for entry in timetable_entries if entry.section}))

    return FacultyOut(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        student_id=user.student_id,
        faculty_id=user.faculty_id,
        has_face_enrollment=has_face_enrollment,
        enrollment_status=enrollment_status,
        enrollment_valid_until=enrollment_valid_until,
        sample_count=sample_count,
        assigned_subjects=assigned_subjects,
        assigned_sections=assigned_sections,
    )


@router.get("/faculty", response_model=List[FacultyOut])
def list_faculty(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Admin-only: List all faculty and teachers with face enrollment status and assigned sections/subjects."""
    faculty_users = (
        db.query(User)
        .filter(User.role.in_(["faculty", "teacher"]))
        .order_by(User.full_name.asc(), User.username.asc())
        .all()
    )
    return [_format_faculty_out(u, db) for u in faculty_users]


@router.post("/faculty", response_model=FacultyOut, status_code=status.HTTP_201_CREATED)
def create_faculty(
    faculty_in: FacultyCreate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Admin-only: Register a new faculty/teacher with unique faculty_id and credentials.
    """
    faculty_id = faculty_in.faculty_id.strip()
    if not faculty_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Faculty ID is required.",
        )

    # Check duplicate faculty_id
    existing_fid = db.query(User).filter(User.faculty_id == faculty_id).first()
    if existing_fid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Faculty ID '{faculty_id}' is already registered to user '{existing_fid.username}'.",
        )

    username = faculty_in.username.strip()
    if not username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username cannot be empty.",
        )

    existing_username = db.query(User).filter(User.username == username).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{username}' is already registered.",
        )

    if faculty_in.email:
        existing_email = db.query(User).filter(User.email == faculty_in.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address is already registered.",
            )

    if len(faculty_in.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long.",
        )

    new_faculty = User(
        username=username,
        password_hash=get_password_hash(faculty_in.password),
        full_name=faculty_in.full_name.strip(),
        email=faculty_in.email,
        role=faculty_in.role or "faculty",
        faculty_id=faculty_id,
        is_active=faculty_in.is_active if faculty_in.is_active is not None else True,
    )
    db.add(new_faculty)
    db.commit()
    db.refresh(new_faculty)

    # Assign timetable slots if specified
    if faculty_in.assigned_subject_ids:
        query = db.query(TimetableEntry).filter(
            TimetableEntry.subject_id.in_(faculty_in.assigned_subject_ids)
        )
        if faculty_in.assigned_sections:
            query = query.filter(TimetableEntry.section.in_(faculty_in.assigned_sections))
        query.update({TimetableEntry.teacher_id: new_faculty.id}, synchronize_session=False)
        db.commit()

    return _format_faculty_out(new_faculty, db)


@router.put("/faculty/{user_id}", response_model=FacultyOut)
def update_faculty(
    user_id: int,
    faculty_update: FacultyUpdate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Admin-only: Update faculty details, activate/deactivate, or reset password.
    """
    faculty = db.query(User).filter(User.id == user_id).first()
    if not faculty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Faculty user not found.",
        )

    if faculty.role not in ("faculty", "teacher"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not a faculty member.",
        )

    if faculty_update.faculty_id is not None:
        fid = faculty_update.faculty_id.strip()
        if not fid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Faculty ID cannot be empty.",
            )
        existing = db.query(User).filter(User.faculty_id == fid, User.id != user_id).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Faculty ID '{fid}' is already in use by '{existing.username}'.",
            )
        faculty.faculty_id = fid

    if faculty_update.full_name is not None:
        faculty.full_name = faculty_update.full_name.strip()

    if faculty_update.email is not None:
        existing_email = db.query(User).filter(User.email == faculty_update.email, User.id != user_id).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address is already in use.",
            )
        faculty.email = faculty_update.email

    if faculty_update.is_active is not None:
        faculty.is_active = faculty_update.is_active

    if faculty_update.password is not None and faculty_update.password != "":
        if len(faculty_update.password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long.",
            )
        faculty.password_hash = get_password_hash(faculty_update.password)

    db.commit()
    db.refresh(faculty)
    return _format_faculty_out(faculty, db)
