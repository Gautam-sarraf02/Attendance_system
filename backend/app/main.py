import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base, SessionLocal
from app.models.user import User
from app.auth.jwt_handler import get_password_hash
from app.face.recognizer import recognizer_service

# Import all models so SQLAlchemy create_all() creates Phase 1 tables
import app.models  # noqa: F401 — registers AcademicYear, Semester, Subject, TimetableEntry, etc.
from app.routers import (
    auth_router,
    students_router,
    model_router,
    sessions_router,
    attendance_router,
    reports_router,
    dashboard_router,
    timetable_router,
    enrollments_router,
    corrections_router,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Ensure tables exist at module load time (for test clients and CLI runners)
Base.metadata.create_all(bind=engine)

def ensure_schema_upgrades():
    """Ensures newly added columns in SQLite database exist without requiring manual migration."""
    try:
        with engine.connect() as conn:
            existing_cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(attendance_sessions)").fetchall()]
            if existing_cols:
                if "academic_year_id" not in existing_cols:
                    conn.exec_driver_sql("ALTER TABLE attendance_sessions ADD COLUMN academic_year_id INTEGER REFERENCES academic_years(id) ON DELETE SET NULL")
                if "subject_id" not in existing_cols:
                    conn.exec_driver_sql("ALTER TABLE attendance_sessions ADD COLUMN subject_id INTEGER REFERENCES subjects(id) ON DELETE SET NULL")
                if "review_reason" not in existing_cols:
                    conn.exec_driver_sql("ALTER TABLE attendance_sessions ADD COLUMN review_reason VARCHAR(255)")
                conn.commit()
    except Exception as e:
        logger.warning(f"Schema upgrade check note: {e}")

ensure_schema_upgrades()


def seed_default_admin():
    db = SessionLocal()
    try:
        admin_exists = db.query(User).filter(User.role == "admin").first()
        if not admin_exists:
            # Check if environment provides initial admin credentials
            if settings.INITIAL_ADMIN_USERNAME and settings.INITIAL_ADMIN_PASSWORD:
                logger.info(f"Creating initial admin account ({settings.INITIAL_ADMIN_USERNAME}) from environment configuration...")
                new_admin = User(
                    username=settings.INITIAL_ADMIN_USERNAME,
                    password_hash=get_password_hash(settings.INITIAL_ADMIN_PASSWORD),
                    full_name="System Administrator",
                    email=settings.INITIAL_ADMIN_EMAIL or "admin@college.edu",
                    role="admin",
                    is_active=True
                )
                db.add(new_admin)
                db.commit()
                logger.info("Configured initial admin account created successfully.")
            elif settings.ENVIRONMENT != "production":
                logger.info(f"Development mode: creating default development admin account ({settings.DEFAULT_ADMIN_USERNAME})...")
                new_admin = User(
                    username=settings.DEFAULT_ADMIN_USERNAME,
                    password_hash=get_password_hash(settings.DEFAULT_ADMIN_PASSWORD),
                    full_name="System Administrator",
                    email=settings.DEFAULT_ADMIN_EMAIL,
                    role="admin",
                    is_active=True
                )
                db.add(new_admin)
                db.commit()
                logger.info("Development default admin account created successfully.")
            else:
                logger.warning(
                    "PRODUCTION ENVIRONMENT: No administrator account exists! "
                    "Please run 'python backend/create_admin.py' or call 'POST /api/auth/setup-admin' "
                    "to securely provision the initial administrator account."
                )
    except Exception as e:
        logger.error(f"Error checking/seeding initial admin: {e}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize DB schema
    logger.info("Creating database tables if not present...")
    Base.metadata.create_all(bind=engine)
    
    # 2. Seed default admin
    seed_default_admin()

    # 3. Check / load trained LBPH model if available
    recognizer_service.load_model_if_exists()
    if recognizer_service.is_trained():
        logger.info("LBPH Face Recognition model is loaded and ready.")
    else:
        logger.info("LBPH Face Recognition model is not yet trained.")

    yield
    logger.info("Classroom Attendance System backend shutting down.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Automated Classroom Attendance System using OpenCV Haar Cascades and LBPH Face Recognizer with FastAPI and React.",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Routers
app.include_router(auth_router, prefix="/api")
app.include_router(students_router, prefix="/api")
app.include_router(model_router, prefix="/api")
app.include_router(sessions_router, prefix="/api")
app.include_router(attendance_router, prefix="/api")
app.include_router(reports_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(timetable_router, prefix="/api")
app.include_router(enrollments_router, prefix="/api")
app.include_router(corrections_router, prefix="/api")

@app.get("/")
def root():
    return {
        "status": "online",
        "system": settings.PROJECT_NAME,
        "docs_url": "/docs",
        "model_trained": recognizer_service.is_trained(),
        "algorithm": "Haar Cascade + LBPH Face Recognizer"
    }

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "model_loaded": recognizer_service.is_trained(),
        "database": "connected"
    }
