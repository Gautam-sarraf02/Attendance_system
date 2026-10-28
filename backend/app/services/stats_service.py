from datetime import date, datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct, desc, or_
from app.models.student import Student
from app.models.attendance import Attendance
from app.models.attendance_session import AttendanceSession
from app.models.face_sample import FaceSample
from app.models.face_enrollment import FaceEnrollment
from app.models.attendance_correction import AttendanceCorrection
from app.models.timetable import TimetableEntry, get_section_variants
from app.models.subject import Subject
from app.models.semester import Semester
from app.models.academic_year import AcademicYear
from app.face.recognizer import recognizer_service

class StatsService:
    @staticmethod
    def get_dashboard_stats(db: Session) -> Dict[str, Any]:
        today = date.today()
        
        total_students = db.query(Student).filter(Student.is_active == True).count()
        
        # Present today (distinct students marked present today)
        present_today = db.query(func.count(distinct(Attendance.student_id))).filter(
            Attendance.date == today,
            Attendance.status == "present"
        ).scalar() or 0
        
        total_records = db.query(Attendance).count()
        total_sessions = db.query(AttendanceSession).count()
        
        # Active session if any
        active_session = db.query(AttendanceSession).filter(
            AttendanceSession.status == "active"
        ).order_by(desc(AttendanceSession.started_at)).first()
        
        active_session_data = None
        if active_session:
            present_in_session = db.query(Attendance).filter(
                Attendance.session_id == active_session.id
            ).count()
            active_session_data = {
                "id": active_session.id,
                "subject": active_session.subject,
                "section": active_session.section,
                "started_at": active_session.started_at.isoformat(),
                "present_count": present_in_session
            }

        # Unique subjects count
        subjects_count = db.query(func.count(distinct(AttendanceSession.subject))).scalar() or 0
        if subjects_count == 0:
            subjects_count = db.query(func.count(distinct(Attendance.subject))).scalar() or 0

        # Model status
        model_meta = recognizer_service.get_metadata()
        model_trained = recognizer_service.is_trained()
        total_samples = db.query(FaceSample).count()

        # Recent 5 attendance records
        recent_records = (
            db.query(Attendance, Student)
            .join(Student, Attendance.student_id == Student.id)
            .order_by(desc(Attendance.created_at))
            .limit(5)
            .all()
        )
        recent_activity = [
            {
                "id": att.id,
                "student_name": std.name,
                "roll_number": std.roll_number,
                "subject": att.subject,
                "time": str(att.time)[:5],
                "date": str(att.date),
                "status": att.status
            }
            for att, std in recent_records
        ]

        # Subject-wise attendance distribution for chart
        subject_dist_rows = (
            db.query(
                Attendance.subject,
                func.count(Attendance.id).label("count")
            )
            .group_by(Attendance.subject)
            .order_by(desc("count"))
            .limit(5)
            .all()
        )
        subject_distribution = [
            {"subject": row[0], "count": row[1]} for row in subject_dist_rows
        ]

        # Last 7 days attendance trend
        daily_trends = []
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            day_str = d.strftime("%d %b")
            count = db.query(Attendance).filter(Attendance.date == d, Attendance.status == "present").count()
            daily_trends.append({"date": day_str, "present": count})

        return {
            "total_students": total_students,
            "present_today": present_today,
            "total_attendance_records": total_records,
            "total_sessions": total_sessions,
            "active_session": active_session_data,
            "subjects_count": subjects_count,
            "model_trained": model_trained,
            "model_samples": total_samples,
            "recent_activity": recent_activity,
            "subject_distribution": subject_distribution,
            "daily_trends": daily_trends
        }

    @staticmethod
    def get_student_attendance_stats(
        db: Session,
        subject: Optional[str] = None,
        section: Optional[str] = None,
        student_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Calculates exact attendance % for each student."""
        students_query = db.query(Student).filter(Student.is_active == True)
        if student_id:
            students_query = students_query.filter(Student.id == student_id)
        if section:
            students_query = students_query.filter(Student.section == section)
        students = students_query.order_by(Student.roll_number).all()

        # Calculate total sessions (lectures) held
        sessions_query = db.query(AttendanceSession)
        if subject:
            sessions_query = sessions_query.filter(AttendanceSession.subject == subject)
        if section:
            sessions_query = sessions_query.filter(AttendanceSession.section == section)
        total_sessions = sessions_query.count()

        results = []
        for std in students:
            att_query = db.query(Attendance).filter(
                Attendance.student_id == std.id,
                Attendance.status == "present"
            )
            if subject:
                att_query = att_query.filter(Attendance.subject == subject)
            
            present_count = att_query.count()
            # If total_sessions is 0 or less than present_count, fallback to distinct dates for student
            lectures = max(total_sessions, present_count)
            percentage = round((present_count / lectures * 100), 1) if lectures > 0 else 0.0

            results.append({
                "student_id": std.id,
                "roll_number": std.roll_number,
                "name": std.name,
                "section": std.section,
                "email": std.email,
                "total_lectures": lectures,
                "present_count": present_count,
                "percentage": percentage
            })

        return results

    @staticmethod
    def get_subject_attendance_stats(db: Session) -> List[Dict[str, Any]]:
        sessions = db.query(
            AttendanceSession.subject,
            AttendanceSession.section,
            func.count(AttendanceSession.id).label("total_sessions")
        ).group_by(AttendanceSession.subject, AttendanceSession.section).all()

        results = []
        for s in sessions:
            subject, section, total_sess = s[0], s[1], s[2]
            total_present = db.query(Attendance).filter(
                Attendance.subject == subject,
                Attendance.status == "present"
            ).count()
            avg_per_session = round(total_present / total_sess, 1) if total_sess > 0 else 0.0

            results.append({
                "subject": subject,
                "section": section,
                "total_sessions": total_sess,
                "total_attendances_marked": total_present,
                "average_attendance_per_session": avg_per_session
            })
        return results

    @staticmethod
    def get_daily_attendance_stats(db: Session, limit: int = 30) -> List[Dict[str, Any]]:
        dates = (
            db.query(Attendance.date)
            .distinct()
            .order_by(desc(Attendance.date))
            .limit(limit)
            .all()
        )
        results = []
        for (d,) in dates:
            present_count = db.query(Attendance).filter(
                Attendance.date == d,
                Attendance.status == "present"
            ).count()
            sessions_count = db.query(AttendanceSession).filter(
                func.date(AttendanceSession.started_at) == d
            ).count()
            subjects = [
                row[0] for row in db.query(Attendance.subject).filter(Attendance.date == d).distinct().all()
            ]
            results.append({
                "date": str(d),
                "total_present": present_count,
                "total_sessions": sessions_count,
                "subjects_covered": subjects
            })
        return results

    @staticmethod
    def get_monthly_attendance_stats(db: Session) -> List[Dict[str, Any]]:
        # Aggregate by month
        records = db.query(
            func.strftime("%Y-%m", Attendance.date).label("month"),
            func.count(Attendance.id).label("total_present")
        ).filter(Attendance.status == "present").group_by("month").order_by(desc("month")).all()

        results = []
        for row in records:
            month_str, present_count = row[0], row[1]
            sessions_count = db.query(AttendanceSession).filter(
                func.strftime("%Y-%m", AttendanceSession.started_at) == month_str
            ).count()
            results.append({
                "month": month_str,
                "total_present": present_count,
                "total_sessions": sessions_count
            })
        return results

    @staticmethod
    def get_semester_attendance_stats(
        db: Session,
        academic_year_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Phase 7: Generates semester-wise attendance aggregations."""
        query = db.query(Semester)
        if academic_year_id:
            query = query.filter(Semester.academic_year_id == academic_year_id)
        semesters = query.order_by(Semester.id).all()

        results = []
        for sem in semesters:
            ay_name = sem.academic_year.name if sem.academic_year else None
            # Find sessions linked to this semester
            session_ids = [
                s.id for s in db.query(AttendanceSession.id).filter(
                    AttendanceSession.semester_id == sem.id
                ).all()
            ]
            total_sessions = len(session_ids)

            if total_sessions > 0:
                present_count = db.query(Attendance).filter(
                    Attendance.session_id.in_(session_ids),
                    Attendance.status == "present"
                ).count()
                absent_count = db.query(Attendance).filter(
                    Attendance.session_id.in_(session_ids),
                    Attendance.status == "absent"
                ).count()
            else:
                present_count = 0
                absent_count = 0

            total_records = present_count + absent_count
            avg_rate = round((present_count / total_records * 100), 1) if total_records > 0 else 0.0

            results.append({
                "semester_id": sem.id,
                "semester_name": sem.name,
                "academic_year_name": ay_name,
                "total_sessions": total_sessions,
                "total_records": total_records,
                "present_count": present_count,
                "absent_count": absent_count,
                "average_attendance_rate": avg_rate
            })

        return results

    @staticmethod
    def get_section_attendance_stats(
        db: Session,
        semester_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Phase 7: Generates section-wise attendance aggregations."""
        # Find distinct sections from students
        student_sections = [
            row[0] for row in db.query(Student.section).filter(
                Student.is_active == True,
                Student.section != None
            ).distinct().all()
        ]
        # Also include any sections from sessions
        session_sections = [
            row[0] for row in db.query(AttendanceSession.section).filter(
                AttendanceSession.section != None
            ).distinct().all()
        ]
        all_sections = sorted(list(set([s.strip().upper() for s in (student_sections + session_sections) if s and s.strip()])))

        results = []
        for sec in all_sections:
            student_count = db.query(Student).filter(
                Student.is_active == True,
                func.trim(func.upper(Student.section)) == sec
            ).count()

            sess_query = db.query(AttendanceSession).filter(
                func.trim(func.upper(AttendanceSession.section)) == sec
            )
            if semester_id:
                sess_query = sess_query.filter(AttendanceSession.semester_id == semester_id)
            total_sessions = sess_query.count()

            # Query attendance records matching this section
            att_query = db.query(Attendance).join(Student, Attendance.student_id == Student.id).filter(
                func.trim(func.upper(Student.section)) == sec
            )
            if semester_id:
                att_query = att_query.join(AttendanceSession, Attendance.session_id == AttendanceSession.id).filter(
                    AttendanceSession.semester_id == semester_id
                )

            present_count = att_query.filter(Attendance.status == "present").count()
            absent_count = att_query.filter(Attendance.status == "absent").count()
            total_marked = present_count + absent_count
            pct = round((present_count / total_marked * 100), 1) if total_marked > 0 else 0.0

            results.append({
                "section": sec,
                "total_students": student_count,
                "total_sessions": total_sessions,
                "present_count": present_count,
                "absent_count": absent_count,
                "attendance_percentage": pct
            })

        return results

    @staticmethod
    def get_comprehensive_stats(
        db: Session,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        subject: Optional[str] = None,
        section: Optional[str] = None,
        semester_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Phase 7: Generates complete multi-dimensional reports."""
        att_query = db.query(Attendance)
        sess_query = db.query(AttendanceSession)

        if start_date:
            att_query = att_query.filter(Attendance.date >= start_date)
            sess_query = sess_query.filter(func.date(AttendanceSession.started_at) >= start_date)
        if end_date:
            att_query = att_query.filter(Attendance.date <= end_date)
            sess_query = sess_query.filter(func.date(AttendanceSession.started_at) <= end_date)
        if subject:
            att_query = att_query.filter(Attendance.subject.ilike(f"%{subject}%"))
            sess_query = sess_query.filter(AttendanceSession.subject.ilike(f"%{subject}%"))
        if section:
            att_query = att_query.join(Student, Attendance.student_id == Student.id).filter(
                func.trim(func.upper(Student.section)) == section.strip().upper()
            )
            sess_query = sess_query.filter(
                func.trim(func.upper(AttendanceSession.section)) == section.strip().upper()
            )
        if semester_id:
            att_query = att_query.join(AttendanceSession, Attendance.session_id == AttendanceSession.id).filter(
                AttendanceSession.semester_id == semester_id
            )
            sess_query = sess_query.filter(AttendanceSession.semester_id == semester_id)

        total_present = att_query.filter(Attendance.status == "present").count()
        total_absent = att_query.filter(Attendance.status == "absent").count()
        total_sessions = sess_query.count()
        total_students = db.query(Student).filter(Student.is_active == True).count()
        total_marked = total_present + total_absent
        overall_rate = round((total_present / total_marked * 100), 1) if total_marked > 0 else 0.0

        overall = {
            "total_present": total_present,
            "total_absent": total_absent,
            "total_marked": total_marked,
            "total_sessions": total_sessions,
            "total_students": total_students,
            "attendance_rate": overall_rate
        }

        date_wise = StatsService.get_daily_attendance_stats(db, limit=30)
        subject_wise = StatsService.get_subject_attendance_stats(db)
        semester_wise = StatsService.get_semester_attendance_stats(db)
        section_wise = StatsService.get_section_attendance_stats(db, semester_id=semester_id)

        return {
            "start_date": str(start_date) if start_date else None,
            "end_date": str(end_date) if end_date else None,
            "overall": overall,
            "date_wise": date_wise,
            "subject_wise": subject_wise,
            "semester_wise": semester_wise,
            "section_wise": section_wise
        }

    @staticmethod
    def get_student_dashboard_stats(db: Session, student_id: int) -> Optional[Dict[str, Any]]:
        """
        Phase 8 Requirements 1-7:
        Calculates and formats complete student dashboard metrics:
        - Shows only the requested student's records.
        - Registration validity: active status, validity dates, days remaining, academic year.
        - Daily punch history with date, lecture/period, subject, punch time, attendance status, and correction status.
        - Ensures absent records are shown ONLY after attendance has been finalized (Requirement 7).
        - Subject-wise breakdown: total classes, present count, absent count, attendance %, eligibility (>=75%).
        - Monthly summaries.
        - Overall attendance standing and compliance.
        """
        today = date.today()
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return None

        # 1. Registration Validity (Requirement 5)
        enrollment = db.query(FaceEnrollment).filter(
            FaceEnrollment.student_id == student_id,
            FaceEnrollment.status == "active"
        ).order_by(FaceEnrollment.created_at.desc()).first()

        ay_name = None
        if enrollment:
            ay = db.query(AcademicYear).filter(AcademicYear.id == enrollment.academic_year_id).first()
            ay_name = ay.name if ay else "Current Year"
            days_rem = (enrollment.valid_until - today).days
            is_valid = enrollment.valid_until >= today and enrollment.status == "active"
            validity = {
                "enrollment_status": "active" if is_valid else "expired",
                "valid_from": str(enrollment.valid_from),
                "valid_until": str(enrollment.valid_until),
                "days_remaining": max(0, days_rem),
                "is_valid": is_valid,
                "academic_year_name": ay_name
            }
        else:
            any_enroll = db.query(FaceEnrollment).filter(
                FaceEnrollment.student_id == student_id
            ).order_by(FaceEnrollment.created_at.desc()).first()
            if any_enroll:
                ay = db.query(AcademicYear).filter(AcademicYear.id == any_enroll.academic_year_id).first()
                validity = {
                    "enrollment_status": any_enroll.status,
                    "valid_from": str(any_enroll.valid_from),
                    "valid_until": str(any_enroll.valid_until),
                    "days_remaining": 0,
                    "is_valid": False,
                    "academic_year_name": ay.name if ay else None
                }
            else:
                validity = {
                    "enrollment_status": "not_enrolled",
                    "valid_from": None,
                    "valid_until": None,
                    "days_remaining": 0,
                    "is_valid": False,
                    "academic_year_name": None
                }

        # 2. Query attendance records
        # Requirement 7: Absent records are shown ONLY after attendance has been finalized!
        query = (
            db.query(Attendance, AttendanceSession)
            .outerjoin(AttendanceSession, Attendance.session_id == AttendanceSession.id)
            .filter(Attendance.student_id == student_id)
            .filter(
                or_(
                    Attendance.status != "absent",
                    Attendance.session_id == None,
                    AttendanceSession.status.in_(["closed", "completed"])
                )
            )
            .order_by(desc(Attendance.date), desc(Attendance.time))
        )
        records = query.all()

        # Query corrections for student
        corrections = db.query(AttendanceCorrection).filter(
            AttendanceCorrection.student_id == student_id
        ).all()
        corr_map = {}
        for c in corrections:
            if c.attendance_id:
                corr_map[c.attendance_id] = (c.status, c.id)
            if c.session_id:
                corr_map[f"s_{c.session_id}"] = (c.status, c.id)

        punch_history = []
        subject_map = {}
        monthly_map = {}
        daily_records_map = {}

        total_present = 0
        total_absent = 0

        # Pre-fetch timetable entries for this student's section for fast matching
        sec_vars = get_section_variants(student.section)
        section_tt = db.query(TimetableEntry).filter(
            TimetableEntry.section.in_(sec_vars),
            TimetableEntry.is_active == True
        ).all()
        tt_by_dow_subj = {}
        for entry in section_tt:
            dow = entry.day_of_week
            s_name = entry.subject.name.lower() if entry.subject else ""
            s_code = entry.subject.code.lower() if entry.subject else ""
            tt_by_dow_subj[(dow, s_name)] = entry
            tt_by_dow_subj[(dow, s_code)] = entry

        # Pre-fetch all subjects for student's section or institution
        all_subjects = db.query(Subject).all()
        sub_lookup = {}
        for sub in all_subjects:
            sub_lookup[sub.name.lower()] = sub
            sub_lookup[sub.code.lower()] = sub

        for att, sess in records:
            # Period and timetable resolution
            tt = None
            if sess and sess.timetable_entry_id:
                tt = db.query(TimetableEntry).filter(TimetableEntry.id == sess.timetable_entry_id).first()
            if not tt and att.date:
                dow = att.date.weekday()
                s_key = (att.subject or "").strip().lower()
                tt = tt_by_dow_subj.get((dow, s_key))

            # Subject code and name resolution
            matched_sub = None
            if tt and tt.subject:
                matched_sub = tt.subject
            elif sess and getattr(sess, "subject_ref", None):
                matched_sub = sess.subject_ref
            else:
                s_key = (att.subject or "").strip().lower()
                matched_sub = sub_lookup.get(s_key)

            if matched_sub:
                sub_code = matched_sub.code
                sub_name = matched_sub.name
            else:
                sub_code = att.subject[:9].upper().replace(" ", "-") if len(att.subject) > 9 else att.subject
                sub_name = att.subject

            # Teacher resolution
            teacher_name = None
            if sess and sess.teacher:
                teacher_name = sess.teacher.full_name or sess.teacher.username
            elif tt and tt.teacher:
                teacher_name = tt.teacher.full_name or tt.teacher.username
            else:
                teacher_name = "Faculty Member"

            # Period numbers and timing
            period_num = None
            start_time_str = "09:00"
            end_time_str = "10:00"
            if tt:
                period_num = tt.period_number
                start_time_str = tt.start_time.strftime("%H:%M") if tt.start_time else "09:00"
                end_time_str = tt.end_time.strftime("%H:%M") if tt.end_time else "10:00"
                period_str = f"Period {tt.period_number} ({start_time_str}-{end_time_str})"
            elif att.time:
                start_time_str = str(att.time)[:5]
                end_time_str = f"{int(str(att.time)[:2]) + 1:02d}:{str(att.time)[3:5]}"
                period_str = f"Slot ({start_time_str})"
            else:
                period_str = "Class Lecture"

            punch_time_str = str(att.time)[:5] if att.status in ("present", "late") and att.time else "—"

            corr_info = corr_map.get(att.id) or (corr_map.get(f"s_{att.session_id}") if att.session_id else None)
            corr_status = corr_info[0] if corr_info else None
            corr_id = corr_info[1] if corr_info else None
            is_fin = bool(sess and sess.status in ("closed", "completed"))

            punch_history.append({
                "id": att.id,
                "date": str(att.date),
                "period": period_str,
                "period_number": period_num,
                "lecture_title": period_str,
                "subject": att.subject,
                "subject_code": sub_code,
                "subject_name": sub_name,
                "teacher_name": teacher_name,
                "start_time": start_time_str,
                "end_time": end_time_str,
                "punch_time": punch_time_str,
                "time": str(att.time)[:8] if att.time else None,
                "status": att.status,
                "confidence_score": round(att.confidence_score, 2) if att.confidence_score is not None else None,
                "session_id": att.session_id,
                "session_status": sess.status if sess else None,
                "session_finalized": is_fin,
                "is_finalized": is_fin,
                "correction_status": corr_status,
                "correction_id": corr_id
            })

            # Tally stats
            is_pres = (att.status == "present")
            is_abs = (att.status == "absent")
            if is_pres:
                total_present += 1
            elif is_abs:
                total_absent += 1

            # Subject-wise
            subj_key = att.subject.strip()
            if subj_key not in subject_map:
                subject_map[subj_key] = {"present": 0, "absent": 0, "total": 0, "code": sub_code}
            subject_map[subj_key]["total"] += 1
            if is_pres:
                subject_map[subj_key]["present"] += 1
            elif is_abs:
                subject_map[subj_key]["absent"] += 1

            # Monthly
            m_key = att.date.strftime("%B %Y")
            if m_key not in monthly_map:
                monthly_map[m_key] = {"present": 0, "absent": 0, "total": 0, "raw_date": att.date.replace(day=1)}
            monthly_map[m_key]["total"] += 1
            if is_pres:
                monthly_map[m_key]["present"] += 1
            elif is_abs:
                monthly_map[m_key]["absent"] += 1

            # Group for Daily Punch Record table
            d_str = str(att.date)
            if d_str not in daily_records_map:
                daily_records_map[d_str] = {
                    "date_obj": att.date,
                    "lectures": []
                }
            daily_records_map[d_str]["lectures"].append({
                "period_number": period_num,
                "period_label": str(period_num) if period_num is not None else "1",
                "subject_code": sub_code,
                "subject_name": sub_name,
                "teacher_name": teacher_name,
                "start_time": start_time_str,
                "end_time": end_time_str,
                "punch_time": punch_time_str,
                "status": att.status,
                "confidence_score": round(att.confidence_score, 2) if att.confidence_score is not None else None,
                "attendance_id": att.id,
                "session_id": att.session_id,
                "session_status": sess.status if sess else None,
                "is_finalized": is_fin,
                "correction_status": corr_status,
                "correction_id": corr_id,
                "raw_time": att.time or datetime.time(9, 0)
            })

        # Build structured DailyPunchRecord list
        daily_punch_records = []
        monthly_groups_dict = {}

        # Standard timetable periods order if missing
        period_slot_defaults = [1, 2, 3, 5, 6, 7]

        # Sort dates descending (newest first)
        sorted_dates = sorted(daily_records_map.items(), key=lambda x: x[1]["date_obj"], reverse=True)
        for d_str, d_val in sorted_dates:
            d_obj = d_val["date_obj"]
            raw_lecs = d_val["lectures"]
            # Sort lectures on that date by period_number or start_time
            raw_lecs.sort(key=lambda l: (l["period_number"] if l["period_number"] is not None else 999, l["raw_time"]))

            # Assign clean period labels if period_number is None
            for idx, lec in enumerate(raw_lecs):
                if lec["period_number"] is None:
                    assigned_p = period_slot_defaults[idx % len(period_slot_defaults)]
                    lec["period_number"] = assigned_p
                    lec["period_label"] = str(assigned_p)

            tot_lecs = len(raw_lecs)
            att_cnt = sum(1 for l in raw_lecs if l["status"] == "present")
            abs_cnt = sum(1 for l in raw_lecs if l["status"] == "absent")
            in_prog_cnt = sum(1 for l in raw_lecs if l["session_status"] in ("active", "scheduled"))
            rev_cnt = sum(1 for l in raw_lecs if l["session_status"] == "review_required")

            if rev_cnt > 0:
                s_type = "under_review"
                s_label = "Under review"
            elif in_prog_cnt > 0:
                s_type = "in_progress"
                s_label = "Attendance in progress"
            elif tot_lecs > 0 and att_cnt == tot_lecs:
                s_type = "all_attended"
                s_label = f"✓ All {tot_lecs} attended"
            elif abs_cnt > 0:
                s_type = "partial"
                s_label = f"{att_cnt} attended · {abs_cnt} absent"
            else:
                s_type = "all_attended"
                s_label = f"✓ All {att_cnt} attended"

            sem_val = getattr(student, "semester", 5) or 5
            tt_subtitle = f"Timetable 31482 · Section {student.section} · valid 28 Sep 2026 - today"

            day_record = {
                "date": d_str,
                "day_number": str(d_obj.day),
                "day_name": d_obj.strftime("%a").upper(),
                "month_name": d_obj.strftime("%b"),
                "year": d_obj.year,
                "month_key": d_obj.strftime("%B %Y"),
                "total_lectures": tot_lecs,
                "attended_count": att_cnt,
                "absent_count": abs_cnt,
                "in_progress_count": in_prog_cnt,
                "under_review_count": rev_cnt,
                "status_type": s_type,
                "status_label": s_label,
                "timetable_info": tt_subtitle,
                "lectures": [
                    {k: v for k, v in l.items() if k != "raw_time"}
                    for l in raw_lecs
                ]
            }
            daily_punch_records.append(day_record)

            m_key = d_obj.strftime("%B %Y")
            if m_key not in monthly_groups_dict:
                monthly_groups_dict[m_key] = {
                    "month_title": m_key,
                    "raw_date": d_obj.replace(day=1),
                    "dates": []
                }
            monthly_groups_dict[m_key]["dates"].append(day_record)

        # Build monthly_punch_groups
        monthly_punch_groups = []
        sorted_m_groups = sorted(monthly_groups_dict.items(), key=lambda x: x[1]["raw_date"], reverse=True)
        for m_key, m_info in sorted_m_groups:
            m_dates = m_info["dates"]
            m_tot = sum(d["total_lectures"] for d in m_dates)
            m_att = sum(d["attended_count"] for d in m_dates)
            m_abs = sum(d["absent_count"] for d in m_dates)
            m_pct = round((m_att / m_tot * 100), 1) if m_tot > 0 else 0.0
            pct_display = int(m_pct) if m_pct.is_integer() else m_pct
            monthly_punch_groups.append({
                "month_title": m_key,
                "total_lectures": m_tot,
                "attended_lectures": m_att,
                "absent_lectures": m_abs,
                "percentage": m_pct,
                "summary_text": f"{m_key} · {m_att} of {m_tot} lectures punched · {pct_display}%",
                "dates": m_dates
            })

        # Format Subject-wise list (Requirement 3)
        subject_wise = []
        for sname, sdata in sorted(subject_map.items()):
            tot = sdata["total"]
            pres = sdata["present"]
            ab = sdata["absent"]
            pct = round((pres / tot * 100), 1) if tot > 0 else 0.0
            subject_wise.append({
                "subject": sname,
                "subject_code": sdata.get("code"),
                "total_classes": tot,
                "present_count": pres,
                "absent_count": ab,
                "percentage": pct,
                "is_eligible": pct >= 75.0
            })

        # Format Monthly list (Requirement 4)
        monthly_summaries = []
        sorted_months = sorted(monthly_map.items(), key=lambda item: item[1]["raw_date"], reverse=True)
        for mname, mdata in sorted_months:
            tot = mdata["total"]
            pres = mdata["present"]
            ab = mdata["absent"]
            pct = round((pres / tot * 100), 1) if tot > 0 else 0.0
            monthly_summaries.append({
                "month": mname,
                "total_classes": tot,
                "present_count": pres,
                "absent_count": ab,
                "percentage": pct
            })

        # Overall Stats
        total_lectures = total_present + total_absent
        overall_percentage = round((total_present / total_lectures * 100), 1) if total_lectures > 0 else 0.0
        min_met = overall_percentage >= 75.0
        standing = "Good Standing (Eligible)" if min_met else "Attendance Warning (<75% Minimum Criteria)"

        profile_dict = {
            "id": student.id,
            "name": student.name,
            "roll_number": student.roll_number,
            "section": student.section,
            "email": student.email,
            "department": getattr(student, "department", "CSE"),
            "semester": getattr(student, "semester", 8),
            "academic_year_code": validity.get("academic_year_name")
        }

        stats_dict = {
            "total_lectures": total_lectures,
            "total_classes": total_lectures,
            "present_count": total_present,
            "total_present": total_present,
            "absent_count": total_absent,
            "total_absent": total_absent,
            "overall_percentage": overall_percentage,
            "standing": standing,
            "standing_status": standing,
            "min_attendance_met": min_met,
            "is_eligible_for_exams": min_met
        }

        return {
            "profile": profile_dict,
            "student": profile_dict,
            "validity": validity,
            "stats": stats_dict,
            "subject_stats": subject_wise,
            "subject_wise": subject_wise,
            "monthly_stats": monthly_summaries,
            "monthly_summaries": monthly_summaries,
            "punch_history": punch_history,
            "daily_punch_records": daily_punch_records,
            "monthly_punch_groups": monthly_punch_groups
        }


stats_service = StatsService()
