import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)  # e.g. "LOGIN", "ENROLL_FACE", "START_SESSION", etc.
    entity_type = Column(String(50), nullable=True, index=True)  # e.g. "user", "student", "session", "enrollment"
    entity_id = Column(Integer, nullable=True)  # ID of the affected entity
    details = Column(Text, nullable=True)  # JSON string with extra context (NEVER include passwords/biometric data)
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False, index=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="audit_logs")
