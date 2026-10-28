from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, EmailStr

class StudentBase(BaseModel):
    roll_number: str
    name: str
    section: str
    email: Optional[str] = None

class StudentCreate(StudentBase):
    pass

class StudentUpdate(BaseModel):
    name: Optional[str] = None
    section: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = None

class FaceSampleSimple(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_name: str
    created_at: datetime

class StudentOut(StudentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime
    samples_count: int = 0
    face_samples: List[FaceSampleSimple] = []

class StudentListResponse(BaseModel):
    total: int
    students: List[StudentOut]
