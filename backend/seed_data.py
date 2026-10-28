import datetime
import random
from app.database import SessionLocal, engine, Base
from app.models.user import User
from app.models.student import Student
from app.models.attendance_session import AttendanceSession
from app.models.attendance import Attendance
from app.auth.jwt_handler import get_password_hash
from app.config import settings

def seed():
    print("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 1. Admin user
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                password_hash=get_password_hash("admin123"),
                full_name="Prof. Sharma (Admin)",
                email="admin@college.edu",
                role="admin",
                is_active=True
            )
            db.add(admin)
            print("Created admin user: admin / admin123")

        # 2. Sample Students from typical CSE batch
        demo_students = [
            {"roll_number": "11242211", "name": "Gurpreet Maan", "section": "CSE-A", "email": "gurpreet.m@college.edu"},
            {"roll_number": "11242202", "name": "Farheen Naaz", "section": "CSE-A", "email": "farheen.n@college.edu"},
            {"roll_number": "11242533", "name": "Gautam Kumar", "section": "CSE-A", "email": "gautam.k@college.edu"},
            {"roll_number": "11242104", "name": "Aarav Sharma", "section": "CSE-A", "email": "aarav.s@college.edu"},
            {"roll_number": "11242188", "name": "Ananya Roy", "section": "CSE-B", "email": "ananya.r@college.edu"},
            {"roll_number": "11242245", "name": "Rohan Verma", "section": "CSE-B", "email": "rohan.v@college.edu"},
        ]

        student_objs = []
        for item in demo_students:
            existing = db.query(Student).filter(Student.roll_number == item["roll_number"]).first()
            if not existing:
                s = Student(
                    roll_number=item["roll_number"],
                    name=item["name"],
                    section=item["section"],
                    email=item["email"],
                    is_active=True
                )
                db.add(s)
                student_objs.append(s)
            else:
                student_objs.append(existing)

        db.commit()
        for s in student_objs:
            db.refresh(s)

        print(f"Ensured {len(student_objs)} demo students exist.")

        # 3. Seed past attendance sessions and records if empty
        if db.query(AttendanceSession).count() == 0:
            print("Seeding past demo lecture attendance sessions...")
            subjects = ["Computer Vision", "Machine Learning", "Operating Systems", "Data Structures"]
            today = datetime.date.today()

            for days_ago in range(10, 0, -1):
                sess_date = today - datetime.timedelta(days=days_ago)
                # Skip Sundays
                if sess_date.weekday() == 6:
                    continue
                
                subject = random.choice(subjects)
                sess = AttendanceSession(
                    subject=subject,
                    section="CSE-A",
                    started_at=datetime.datetime.combine(sess_date, datetime.time(9, 30)),
                    ended_at=datetime.datetime.combine(sess_date, datetime.time(10, 30)),
                    created_by=admin.id if admin else 1,
                    status="completed"
                )
                db.add(sess)
                db.commit()
                db.refresh(sess)

                # Randomly mark 4 to 6 students present
                for student in student_objs:
                    if student.section == "CSE-A" and random.random() > 0.15:
                        att = Attendance(
                            student_id=student.id,
                            session_id=sess.id,
                            subject=subject,
                            date=sess_date,
                            time=datetime.time(9, 35, random.randint(10, 59)),
                            status="present",
                            confidence_score=round(random.uniform(35.0, 58.0), 2)
                        )
                        db.add(att)
            
            db.commit()
            print("Successfully seeded demo attendance sessions and records.")

    except Exception as e:
        print("Error during seed:", e)
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed()
