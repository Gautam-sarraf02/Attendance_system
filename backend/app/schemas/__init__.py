from app.schemas.user import UserLogin, UserCreate, UserUpdate, UserOut, Token, TokenData
from app.schemas.student import StudentCreate, StudentUpdate, StudentOut, StudentListResponse
from app.schemas.face import (
    FaceSampleOut,
    ModelStatusResponse,
    TrainModelResponse,
    BoundingBox,
    RecognitionDetection,
    RecognizeFrameRequest,
    RecognizeFrameResponse,
    UploadFaceSamplesRequest,
)
from app.schemas.session import SessionCreate, SessionOut
from app.schemas.attendance import (
    AttendanceSimple,
    AttendanceDetail,
    AttendanceHistoryResponse,
    ManualAttendanceCreate,
)
from app.schemas.report import (
    StudentAttendanceStats,
    SubjectAttendanceStats,
    DailyAttendanceStats,
    MonthlyTrendStats,
    DashboardStatsOut,
)

# Phase 1: new schemas
from app.schemas.academic import (
    AcademicYearCreate, AcademicYearUpdate, AcademicYearOut,
    SemesterCreate, SemesterUpdate, SemesterOut,
    SubjectCreate, SubjectUpdate, SubjectOut,
    TimetableEntryCreate, TimetableEntryUpdate, TimetableEntryOut,
)
from app.schemas.enrollment import (
    FaceEnrollmentCreate, FaceEnrollmentUpdate, FaceEnrollmentOut,
    SubstituteAuthCreate, SubstituteAuthUpdate, SubstituteAuthOut,
    AuditLogOut, AuditLogFilter,
)
from app.schemas.correction import (
    AttendanceCorrectionCreate,
    AttendanceCorrectionReview,
    AttendanceCorrectionOut,
    AttendanceCorrectionListResponse,
)
from app.schemas.session import (
    SessionFinalizeRequest,
    SessionFinalizeOut,
)

__all__ = [
    "UserLogin", "UserCreate", "UserUpdate", "UserOut", "Token", "TokenData",
    "StudentCreate", "StudentUpdate", "StudentOut", "StudentListResponse",
    "FaceSampleOut", "ModelStatusResponse", "TrainModelResponse",
    "BoundingBox", "RecognitionDetection", "RecognizeFrameRequest", "RecognizeFrameResponse",
    "UploadFaceSamplesRequest",
    "SessionCreate", "SessionOut", "SessionFinalizeRequest", "SessionFinalizeOut",
    "AttendanceSimple", "AttendanceDetail", "AttendanceHistoryResponse", "ManualAttendanceCreate",
    "StudentAttendanceStats", "SubjectAttendanceStats", "DailyAttendanceStats", "MonthlyTrendStats", "DashboardStatsOut",
    # Phase 1
    "AcademicYearCreate", "AcademicYearUpdate", "AcademicYearOut",
    "SemesterCreate", "SemesterUpdate", "SemesterOut",
    "SubjectCreate", "SubjectUpdate", "SubjectOut",
    "TimetableEntryCreate", "TimetableEntryUpdate", "TimetableEntryOut",
    "FaceEnrollmentCreate", "FaceEnrollmentUpdate", "FaceEnrollmentOut",
    "SubstituteAuthCreate", "SubstituteAuthUpdate", "SubstituteAuthOut",
    "AuditLogOut", "AuditLogFilter",
    # Phase 7
    "AttendanceCorrectionCreate", "AttendanceCorrectionReview", "AttendanceCorrectionOut", "AttendanceCorrectionListResponse",
]
