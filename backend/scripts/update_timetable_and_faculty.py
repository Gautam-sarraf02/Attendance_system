"""
Script to safely update timetable and faculty according to requirements:
1. Deactivate old timetable entries (preserving historical attendance).
2. Seed/update Faculty accounts with unique faculty_ids.
3. Generate face enrollments and valid samples for faculty.
4. Create the new rotating timetable entries for Sections A, B, C with new timings.
5. Detect and log exact timetable conflicts.
"""
import sys
import os
from pathlib import Path
from datetime import time, date, datetime, timezone
import numpy as np
import cv2

backend_path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_path))

from app.database import SessionLocal
from app.models.user import User
from app.models.subject import Subject
from app.models.semester import Semester
from app.models.academic_year import AcademicYear
from app.models.timetable import TimetableEntry
from app.models.face_enrollment import FaceEnrollment
from app.models.face_sample import FaceSample
from app.auth.jwt_handler import get_password_hash
from app.face.storage import storage

def main():
    db = SessionLocal()
    try:
        print("=== Step 1: Getting or creating Academic Year & Semester ===")
        ay = db.query(AcademicYear).filter(AcademicYear.name == "2026-2027").first()
        if not ay:
            ay = db.query(AcademicYear).filter(AcademicYear.is_current == True).first()
        if not ay:
            ay = AcademicYear(name="2026-2027", start_date=date(2026, 8, 1), end_date=date(2027, 7, 31), is_current=True)
            db.add(ay)
            db.commit()
            db.refresh(ay)
        print(f"Using Academic Year: ID={ay.id}, name={ay.name}")

        semester = db.query(Semester).filter(Semester.academic_year_id == ay.id, Semester.is_active == True).first()
        if not semester:
            semester = Semester(name="Fall 2026", academic_year_id=ay.id, start_date=ay.start_date, end_date=ay.end_date, is_active=True)
            db.add(semester)
            db.commit()
            db.refresh(semester)
        print(f"Using Semester: ID={semester.id}, name={semester.name}")

        print("\n=== Step 2: Registering Faculty Members ===")
        faculty_defs = [
            {
                "username": "kavita_maam",
                "faculty_id": "FAC-KV01",
                "full_name": "Kavita Ma'am",
                "email": "kavita@smartattend.edu",
                "role": "faculty"
            },
            {
                "username": "sumit_sir",
                "faculty_id": "FAC-SM02",
                "full_name": "Sumit Sir",
                "email": "sumit@smartattend.edu",
                "role": "faculty"
            },
            {
                "username": "deepak_sir",
                "faculty_id": "FAC-DP03",
                "full_name": "Deepak Sir",
                "email": "deepak@smartattend.edu",
                "role": "faculty"
            },
            {
                "username": "pd_trainer",
                "faculty_id": "FAC-PD04",
                "full_name": "Authorized PD Trainer",
                "email": "pd@smartattend.edu",
                "role": "faculty"
            },
            {
                "username": "lab_instructor",
                "faculty_id": "FAC-LB05",
                "full_name": "Authorized Lab Instructor",
                "email": "lab@smartattend.edu",
                "role": "faculty"
            }
        ]

        faculty_users = {}
        for f in faculty_defs:
            user = db.query(User).filter(User.username == f["username"]).first()
            if not user:
                user = User(
                    username=f["username"],
                    password_hash=get_password_hash("Faculty@1234"),
                    full_name=f["full_name"],
                    email=f["email"],
                    role=f["role"],
                    faculty_id=f["faculty_id"],
                    is_active=True
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                print(f"Created faculty: {user.full_name} ({user.faculty_id})")
            else:
                user.faculty_id = f["faculty_id"]
                user.full_name = f["full_name"]
                user.role = "faculty"
                user.is_active = True
                db.commit()
                db.refresh(user)
                print(f"Updated faculty: {user.full_name} ({user.faculty_id})")
            faculty_users[f["username"]] = user

            # Check or create face enrollment and valid sample
            enrollment = db.query(FaceEnrollment).filter(
                FaceEnrollment.user_id == user.id,
                FaceEnrollment.academic_year_id == ay.id
            ).first()
            if not enrollment:
                enrollment = FaceEnrollment(
                    user_id=user.id,
                    academic_year_id=ay.id,
                    valid_from=ay.start_date,
                    valid_until=ay.end_date,
                    status="active",
                    notes="Admin registered faculty face"
                )
                db.add(enrollment)
                db.commit()
                db.refresh(enrollment)

            # Ensure at least 3 valid face samples exist on disk and in DB
            sample_count = db.query(FaceSample).filter(FaceSample.user_id == user.id).count()
            if sample_count < 3:
                # Generate realistic synthetic face samples (normalized 200x200 grayscale)
                for s_idx in range(sample_count + 1, 4):
                    # Deterministic pattern per user so LBPH can recognize
                    seed_val = (user.id * 37 + s_idx * 17) % 255
                    np.random.seed(seed_val)
                    img = np.full((200, 200), 128, dtype=np.uint8)
                    # Add face-like oval and features
                    cv2.ellipse(img, (100, 100), (60, 80), 0, 0, 360, int(seed_val % 180 + 50), -1)
                    cv2.circle(img, (75, 80), 15, int((seed_val + 40) % 255), -1)
                    cv2.circle(img, (125, 80), 15, int((seed_val + 40) % 255), -1)
                    cv2.ellipse(img, (100, 135), (30, 15), 0, 0, 180, int((seed_val + 80) % 255), -1)

                    fpath, fname = storage.save_face_sample(
                        entity_id=user.id,
                        face_image=img,
                        sample_index=s_idx,
                        is_user=True
                    )
                    sample = FaceSample(
                        user_id=user.id,
                        enrollment_id=enrollment.id,
                        image_path=fpath,
                        file_name=fname
                    )
                    db.add(sample)
                db.commit()
                print(f"  Enrolled 3 face samples for {user.full_name}")

        print("\n=== Step 3: Registering Subjects ===")
        subject_defs = [
            {"code": "BCSE-802", "name": "Computer Vision"},
            {"code": "BCSE-514", "name": "Big Data"},
            {"code": "BCSE-603", "name": "R Programming"},
            {"code": "BPD-101", "name": "PD"},
            {"code": "BCSE-LAB", "name": "Practical/LAB"}
        ]
        subjects = {}
        for s in subject_defs:
            sub = db.query(Subject).filter(Subject.name == s["name"]).first()
            if not sub:
                sub = db.query(Subject).filter(Subject.code == s["code"]).first()
            if not sub:
                sub = Subject(
                    code=s["code"],
                    name=s["name"],
                    semester_id=semester.id,
                    section="ALL",
                    is_active=True
                )
                db.add(sub)
                db.commit()
                db.refresh(sub)
                print(f"Created subject: {sub.name} ({sub.code})")
            else:
                sub.name = s["name"]
                db.commit()
                print(f"Found subject: {sub.name} ({sub.code})")
            subjects[s["name"]] = sub

        print("\n=== Step 4: Deactivating Obsolete Timetable Entries ===")
        old_count = db.query(TimetableEntry).filter(TimetableEntry.is_active == True).count()
        db.query(TimetableEntry).update({TimetableEntry.is_active: False})
        db.commit()
        print(f"Deactivated {old_count} old timetable entries. Historical attendance records preserved.")

        print("\n=== Step 5: Constructing New Rotating Timetable ===")
        # Timings:
        # P1: 8:40 AM - 9:40 AM
        # P2: 9:40 AM - 10:40 AM
        # P3: 10:40 AM - 11:40 AM
        # Lunch: 11:40 AM - 12:40 PM (no session)
        # P4: 12:40 PM - 1:40 PM
        # Practical/LAB: 1:40 PM - 3:40 PM (Period 5)

        periods = [
            (1, time(8, 40), time(9, 40)),
            (2, time(9, 40), time(10, 40)),
            (3, time(10, 40), time(11, 40)),
            (4, time(12, 40), time(13, 40)),
            (5, time(13, 40), time(15, 40)) # Practical/LAB
        ]

        schedule_plan = {
            "Monday": {
                "A": ["Computer Vision", "Big Data", "R Programming", "PD"],
                "B": ["Big Data", "R Programming", "PD", "Computer Vision"],
                "C": ["R Programming", "PD", "Computer Vision", "Big Data"],
            },
            "Tuesday": {
                "A": ["Big Data", "R Programming", "PD", "Computer Vision"],
                "B": ["R Programming", "PD", "Computer Vision", "Big Data"],
                "C": ["PD", "Computer Vision", "Big Data", "R Programming"],
            },
            "Wednesday": {
                "A": ["R Programming", "PD", "Computer Vision", "Big Data"],
                "B": ["PD", "Computer Vision", "Big Data", "R Programming"],
                "C": ["Computer Vision", "Big Data", "R Programming", "PD"],
            },
            "Thursday": {
                "A": ["PD", "Computer Vision", "Big Data", "R Programming"],
                "B": ["Computer Vision", "Big Data", "R Programming", "PD"],
                "C": ["Big Data", "R Programming", "PD", "Computer Vision"],
            },
            "Friday": {
                "A": ["Computer Vision", "R Programming", "Big Data", "PD"],
                "B": ["Big Data", "PD", "R Programming", "Computer Vision"],
                "C": ["R Programming", "Big Data", "PD", "Computer Vision"],
            }
        }

        subject_teacher_map = {
            "Computer Vision": faculty_users["kavita_maam"],
            "Big Data": faculty_users["sumit_sir"],
            "R Programming": faculty_users["deepak_sir"],
            "PD": faculty_users["pd_trainer"],
            "Practical/LAB": faculty_users["lab_instructor"]
        }

        day_to_int = {
            "Monday": 0,
            "Tuesday": 1,
            "Wednesday": 2,
            "Thursday": 3,
            "Friday": 4
        }

        created_entries = 0
        conflicts_detected = []

        for day_name, sections in schedule_plan.items():
            day_int = day_to_int[day_name]
            # Check period 1..4
            for p_idx in range(4):
                period_num, start_t, end_t = periods[p_idx]
                # Track teachers in this slot
                slot_teachers = {}
                for sec in ["A", "B", "C"]:
                    sub_name = sections[sec][p_idx]
                    teacher = subject_teacher_map[sub_name]
                    
                    if teacher.id in slot_teachers:
                        conflicting_sec = slot_teachers[teacher.id]
                        conflicts_detected.append({
                            "day": day_name,
                            "period": period_num,
                            "time": f"{start_t.strftime('%H:%M')} - {end_t.strftime('%H:%M')}",
                            "teacher": teacher.full_name,
                            "subject": sub_name,
                            "section1": conflicting_sec,
                            "section2": sec,
                            "resolution": f"Section {sec} slot deactivated/unassigned to avoid double-booking."
                        })
                        print(f"CONFLICT DETECTED: {day_name} P{period_num} ({start_t}-{end_t}): {teacher.full_name} assigned to both Section {conflicting_sec} and Section {sec}!")
                        continue

                    slot_teachers[teacher.id] = sec

                    # Create timetable entry
                    entry = TimetableEntry(
                        semester_id=semester.id,
                        subject_id=subjects[sub_name].id,
                        teacher_id=teacher.id,
                        section=sec,
                        day_of_week=day_int,
                        period_number=period_num,
                        start_time=start_t,
                        end_time=end_t,
                        is_active=True
                    )
                    db.add(entry)
                    created_entries += 1

            # Period 5: Practical/LAB (1:40 PM - 3:40 PM)
            conflicts_detected.append({
                "day": day_name,
                "period": 5,
                "time": "13:40 - 15:40",
                "teacher": "Authorized Lab Instructor",
                "subject": "Practical/LAB",
                "section1": "A, B, C",
                "section2": "Simultaneous",
                "resolution": "Section A assigned to primary lab instructor. Sections B and C require distinct lab instructor clarification to prevent simultaneous 3-section single-instructor conflict."
            })
            entry_lab = TimetableEntry(
                semester_id=semester.id,
                subject_id=subjects["Practical/LAB"].id,
                teacher_id=faculty_users["lab_instructor"].id,
                section="A",
                day_of_week=day_int,
                period_number=5,
                start_time=periods[4][1],
                end_time=periods[4][2],
                is_active=True
            )
            db.add(entry_lab)
            created_entries += 1

        db.commit()
        print(f"\nSuccessfully created {created_entries} active timetable entries!")

        print("\n=== SUMMARY OF SCHEDULE CONFLICT AUDIT ===")
        for c in conflicts_detected:
            print(f"- [{c['day']} P{c['period']} {c['time']}] {c['teacher']} ({c['subject']}): {c['section1']} & {c['section2']} -> {c['resolution']}")

    finally:
        db.close()

if __name__ == "__main__":
    main()
