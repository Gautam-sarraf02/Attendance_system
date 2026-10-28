import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class FaceSample(Base):
    __tablename__ = "face_samples"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    image_path = Column(String(255), nullable=False)
    file_name = Column(String(150), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)

    # Link to enrollment for academic year expiry tracking
    enrollment_id = Column(Integer, ForeignKey("face_enrollments.id", ondelete="SET NULL"), nullable=True, index=True)

    # Relationships
    student = relationship("Student", back_populates="face_samples")
    user = relationship("User", foreign_keys=[user_id], backref="face_samples")
    enrollment = relationship("FaceEnrollment", back_populates="face_samples")

