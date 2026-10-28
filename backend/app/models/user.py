import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(150), nullable=True)
    email = Column(String(150), nullable=True)
    role = Column(String(50), default="faculty", nullable=False)  # 'admin', 'faculty', 'teacher', 'student'
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)

    # For student-type users: links to the Student record
    student_id = Column(Integer, ForeignKey("students.id", ondelete="SET NULL"), nullable=True, unique=True, index=True)
    # For faculty/teacher users: unique faculty identifier (e.g. FAC001)
    faculty_id = Column(String(50), unique=True, index=True, nullable=True)

    # Relationships
    student = relationship("Student", foreign_keys=[student_id], backref="user_account")
