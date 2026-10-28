from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, EmailStr


VALID_ROLES = ("admin", "faculty", "teacher", "student")


class UserLogin(BaseModel):
    username: str
    password: str
    role: Optional[str] = None


class UserCreate(BaseModel):
    username: str
    password: str
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Literal["admin", "faculty", "teacher", "student"] = "faculty"
    student_id: Optional[int] = None  # Required when role == "student"
    faculty_id: Optional[str] = None  # Unique faculty ID for faculty/teachers


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[Literal["admin", "faculty", "teacher", "student"]] = None
    is_active: Optional[bool] = None
    student_id: Optional[int] = None
    faculty_id: Optional[str] = None
    password: Optional[str] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class SetupAdminRequest(BaseModel):
    username: str
    password: str
    email: EmailStr
    full_name: Optional[str] = "System Administrator"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime
    student_id: Optional[int] = None
    faculty_id: Optional[str] = None


class FacultyOut(UserOut):
    has_face_enrollment: bool = False
    enrollment_status: Optional[str] = None
    enrollment_valid_until: Optional[str] = None
    sample_count: int = 0
    assigned_subjects: list[str] = []
    assigned_sections: list[str] = []


class FacultyCreate(BaseModel):
    faculty_id: str
    username: str
    password: str
    full_name: str
    email: Optional[EmailStr] = None
    role: Optional[str] = "faculty"
    is_active: Optional[bool] = True
    assigned_subject_ids: Optional[list[int]] = None
    assigned_sections: Optional[list[str]] = None


class FacultyUpdate(BaseModel):
    faculty_id: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class UserListResponse(BaseModel):
    total: int
    users: list[UserOut]


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None
    user_id: Optional[int] = None
    student_id: Optional[int] = None

