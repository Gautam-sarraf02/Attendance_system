from app.routers.auth import router as auth_router
from app.routers.students import router as students_router
from app.routers.model import router as model_router
from app.routers.sessions import router as sessions_router
from app.routers.attendance import router as attendance_router
from app.routers.reports import router as reports_router
from app.routers.dashboard import router as dashboard_router
from app.routers.timetable import router as timetable_router
from app.routers.enrollments import router as enrollments_router
from app.routers.corrections import router as corrections_router

__all__ = [
    "auth_router",
    "students_router",
    "model_router",
    "sessions_router",
    "attendance_router",
    "reports_router",
    "dashboard_router",
    "timetable_router",
    "enrollments_router",
    "corrections_router",
]
