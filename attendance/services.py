"""
BunkWise — Services Layer
All attendance business logic lives here. Views only handle HTTP; services handle math.
"""

import math
from datetime import date, timedelta
from django.db.models import Q
from django.utils import timezone


# ─────────────────────────────────────────────────────────────────────────────
# Session Generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_sessions(semester):
    """
    Generate ClassSession records for the entire semester based on TimetableEntry rows.
    Skips dates already having a session for that timetable entry.
    Returns (created_count, skipped_count).
    """
    from attendance.models import ClassSession

    entries = semester.timetable_entries.select_related('subject').all()
    created = 0
    skipped = 0

    current = semester.start_date
    end     = semester.end_date

    while current <= end:
        dow = current.weekday()  # 0=Monday … 6=Sunday
        day_entries = entries.filter(day_of_week=dow)

        for entry in day_entries:
            from datetime import datetime
            start_dt = datetime.combine(date.today(), entry.start_time)
            end_dt   = datetime.combine(date.today(), entry.end_time)
            duration = int((end_dt - start_dt).total_seconds() // 60)

            weight = entry.attendance_weight

            obj, was_created = ClassSession.objects.get_or_create(
                semester=semester,
                subject=entry.subject,
                timetable_entry=entry,
                date=current,
                defaults={
                    'session_type':      entry.session_type,
                    'start_time':        entry.start_time,
                    'end_time':          entry.end_time,
                    'duration_minutes':  duration,
                    'status':            'scheduled',
                    'attendance_weight': weight,
                }
            )
            if was_created:
                created += 1
            else:
                skipped += 1

        current += timedelta(days=1)

    return created, skipped


def regenerate_sessions(semester):
    """Delete all scheduled sessions and regenerate. Preserves attended/absent records."""
    from attendance.models import ClassSession
    ClassSession.objects.filter(semester=semester, status='scheduled').delete()
    return generate_sessions(semester)


# ─────────────────────────────────────────────────────────────────────────────
# Attendance Calculation
# ─────────────────────────────────────────────────────────────────────────────

def calculate_attendance(subject):
    """
    Returns a dict with raw counts and percentages for a subject.
    Unifies all session types (lectures, labs, tutorials) into the subject's overall total attendance,
    and provides a detailed breakdown per session type (lecture, lab, tutorial).
    Uses attendance_weight for period-based policy.
    """
    from attendance.models import ClassSession

    sessions = ClassSession.objects.filter(
        subject=subject,
        status__in=['present', 'absent']
    )

    conducted_w = sum(s.attendance_weight for s in sessions)
    attended_w  = sum(s.attendance_weight for s in sessions if s.status == 'present')
    absent_w    = sum(s.attendance_weight for s in sessions if s.status == 'absent')

    raw_conducted = sessions.count()
    raw_attended  = sessions.filter(status='present').count()
    raw_absent    = sessions.filter(status='absent').count()

    percentage = (attended_w / conducted_w * 100) if conducted_w > 0 else 0.0

    # Lecture breakdown
    lecture_sessions = sessions.filter(session_type='lecture')
    lec_conducted = lecture_sessions.count()
    lec_attended  = lecture_sessions.filter(status='present').count()
    lec_absent    = lecture_sessions.filter(status='absent').count()
    lec_pct       = round((lec_attended / lec_conducted * 100), 2) if lec_conducted > 0 else 0.0

    # Lab breakdown
    lab_sessions  = sessions.filter(session_type='lab')
    lab_conducted = lab_sessions.count()
    lab_attended  = lab_sessions.filter(status='present').count()
    lab_absent    = lab_sessions.filter(status='absent').count()
    lab_pct       = round((lab_attended / lab_conducted * 100), 2) if lab_conducted > 0 else 0.0

    # Tutorial breakdown
    tut_sessions  = sessions.filter(session_type='tutorial')
    tut_conducted = tut_sessions.count()
    tut_attended  = tut_sessions.filter(status='present').count()
    tut_absent    = tut_sessions.filter(status='absent').count()
    tut_pct       = round((tut_attended / tut_conducted * 100), 2) if tut_conducted > 0 else 0.0

    return {
        'conducted':        round(conducted_w, 2),
        'attended':         round(attended_w, 2),
        'absent':           round(absent_w, 2),
        'percentage':       round(percentage, 2),
        'min_required':     subject.get_min_attendance(),
        'effective_target': subject.get_effective_target(),
        'raw_conducted':    raw_conducted,
        'raw_attended':     raw_attended,
        'raw_absent':       raw_absent,
        'has_lab':          subject.has_lab,
        'lec_conducted':    lec_conducted,
        'lec_attended':     lec_attended,
        'lec_absent':       lec_absent,
        'lec_pct':          lec_pct,
        'lab_conducted':    lab_conducted,
        'lab_attended':     lab_attended,
        'lab_absent':       lab_absent,
        'lab_pct':          lab_pct,
        'tut_conducted':    tut_conducted,
        'tut_attended':     tut_attended,
        'tut_absent':       tut_absent,
        'tut_pct':          tut_pct,
    }


def calculate_attendance_all(semester):
    """Returns attendance dict for every subject in the semester."""
    return {
        subject: calculate_attendance(subject)
        for subject in semester.subjects.all()
    }


# ─────────────────────────────────────────────────────────────────────────────
# Risk Classification
# ─────────────────────────────────────────────────────────────────────────────

def classify_risk(att_data):
    """
    Returns 'SAFE', 'CAUTION', or 'CRITICAL'.
    Uses the effective target (min + buffer) as the safe zone.
    """
    pct    = att_data['percentage']
    target = att_data['effective_target']
    minreq = att_data['min_required']

    if pct >= target:
        return 'SAFE'
    elif pct >= minreq:
        return 'CAUTION'
    else:
        return 'CRITICAL'


# ─────────────────────────────────────────────────────────────────────────────
# Bunk Budget
# ─────────────────────────────────────────────────────────────────────────────

def calculate_bunk_budget(subject, att_data=None):
    """
    Maximum additional absences the student can afford while staying above
    the minimum required attendance.

    Formula:
        safe = floor((attended - threshold × conducted) / threshold)
    where threshold = min_required / 100

    Returns 0 if the student is already at or below the required threshold.
    Never returns negative.
    """
    if att_data is None:
        att_data = calculate_attendance(subject)

    attended  = att_data['attended']
    conducted = att_data['conducted']
    threshold = att_data['min_required'] / 100.0

    if conducted == 0:
        return 0

    if threshold == 0:
        return 999  # No minimum — unlimited

    safe = (attended - threshold * conducted) / threshold
    return max(0, math.floor(safe))


# ─────────────────────────────────────────────────────────────────────────────
# Recovery Calculation
# ─────────────────────────────────────────────────────────────────────────────

def recovery_sessions_needed(subject, att_data=None):
    """
    How many consecutive sessions must the student attend (without any absence)
    to reach the minimum required attendance?

    Formula:
        needed = ceil((threshold × conducted - attended) / (1 - threshold))

    Returns 0 if already above the target.
    Returns None if threshold is 100% and impossible to recover through attendance.
    """
    if att_data is None:
        att_data = calculate_attendance(subject)

    attended  = att_data['attended']
    conducted = att_data['conducted']
    threshold = att_data['min_required'] / 100.0

    if threshold >= 1.0:
        return None  # 100% required — impossible to recover once absent

    shortfall = threshold * conducted - attended
    if shortfall <= 0:
        return 0

    needed = shortfall / (1 - threshold)
    return math.ceil(needed)


# ─────────────────────────────────────────────────────────────────────────────
# Future Sessions
# ─────────────────────────────────────────────────────────────────────────────

def get_future_sessions(subject, from_date=None):
    """Returns scheduled (not yet conducted) sessions for a subject from today onward."""
    from attendance.models import ClassSession
    if from_date is None:
        from_date = timezone.localdate()
    return ClassSession.objects.filter(
        subject=subject,
        date__gte=from_date,
        status='scheduled'
    ).order_by('date', 'start_time')


def get_remaining_sessions_count(semester, from_date=None):
    """Total scheduled (future) sessions across all subjects in the semester."""
    from attendance.models import ClassSession
    if from_date is None:
        from_date = timezone.localdate()
    return ClassSession.objects.filter(
        semester=semester,
        date__gte=from_date,
        status='scheduled'
    ).count()


# ─────────────────────────────────────────────────────────────────────────────
# Simulation Engine (What-if — does NOT modify real data)
# ─────────────────────────────────────────────────────────────────────────────

def simulate_absences(session_ids):
    """
    Given a list of ClassSession IDs to simulate as absent, return projected
    attendance per subject.

    Returns:
        {
            subject_id: {
                'subject_name':   str,
                'current_pct':    float,
                'projected_pct':  float,
                'current_risk':   str,
                'projected_risk': str,
                'weight_lost':    float,
                'safe_after':     int,
            },
            ...
        }

    IMPORTANT: This function reads data but NEVER writes to the database.
    """
    from attendance.models import ClassSession, Subject

    sessions = ClassSession.objects.filter(id__in=session_ids).select_related('subject')

    # Group weight lost per subject
    weight_lost_per_subject = {}
    for s in sessions:
        sid = s.subject_id
        weight_lost_per_subject[sid] = weight_lost_per_subject.get(sid, 0) + s.attendance_weight

    result = {}
    # Collect all affected subjects
    subject_ids = set(weight_lost_per_subject.keys())

    for subject in Subject.objects.filter(id__in=subject_ids):
        att = calculate_attendance(subject)
        weight_lost = weight_lost_per_subject.get(subject.id, 0)

        proj_conducted = att['conducted'] + weight_lost
        proj_attended  = att['attended']
        proj_pct = (proj_attended / proj_conducted * 100) if proj_conducted > 0 else 0.0

        proj_att = {
            'conducted':        proj_conducted,
            'attended':         proj_attended,
            'absent':           att['absent'] + weight_lost,
            'percentage':       round(proj_pct, 2),
            'min_required':     att['min_required'],
            'effective_target': att['effective_target'],
        }

        result[subject.id] = {
            'subject_name':   str(subject),
            'current_pct':    att['percentage'],
            'projected_pct':  round(proj_pct, 2),
            'current_risk':   classify_risk(att),
            'projected_risk': classify_risk(proj_att),
            'weight_lost':    round(weight_lost, 2),
            'safe_after':     calculate_bunk_budget(subject, proj_att),
            'min_required':   att['min_required'],
        }

    return result


def simulate_date_range(semester, start_date, end_date):
    """
    Simulate being absent for ALL scheduled sessions between start_date and end_date.
    Returns same structure as simulate_absences().
    """
    from attendance.models import ClassSession
    sessions = ClassSession.objects.filter(
        semester=semester,
        date__range=(start_date, end_date),
        status='scheduled'
    )
    return simulate_absences(list(sessions.values_list('id', flat=True)))


# ─────────────────────────────────────────────────────────────────────────────
# Bridge Day Detector
# ─────────────────────────────────────────────────────────────────────────────

def find_bridge_days(semester):
    """
    Find working days sandwiched between two holidays/weekends.
    Returns list of dicts with date, sessions, and impact analysis.
    """
    from attendance.models import SpecialDay, ClassSession

    special_day_dates = set(
        SpecialDay.objects.filter(
            semester=semester,
            day_type__in=['holiday', 'event']
        ).values_list('date', flat=True)
    )

    bridges = []
    current = semester.start_date
    end     = semester.end_date

    while current <= end:
        dow = current.weekday()

        def is_off(d):
            return d.weekday() >= 5 or d in special_day_dates

        prev_day = current - timedelta(days=1)
        next_day = current + timedelta(days=1)

        if not is_off(current) and is_off(prev_day) and is_off(next_day):
            # current is a working day sandwiched between two off days
            day_sessions = ClassSession.objects.filter(
                semester=semester,
                date=current,
                status='scheduled'
            ).select_related('subject')

            if day_sessions.exists():
                session_ids = list(day_sessions.values_list('id', flat=True))
                impact = simulate_absences(session_ids)
                bridges.append({
                    'date':     current,
                    'sessions': list(day_sessions),
                    'impact':   impact,
                })

        current += timedelta(days=1)

    return bridges


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard Data Aggregator
# ─────────────────────────────────────────────────────────────────────────────

def get_dashboard_data(user):
    """
    Returns all data needed to render the dashboard for a user's active semester.
    """
    from attendance.models import Semester, ClassSession

    try:
        semester = Semester.objects.filter(user=user, is_active=True).latest('start_date')
    except Semester.DoesNotExist:
        return None

    subjects  = semester.subjects.all()
    today     = timezone.localdate()

    subject_data = []
    total_conducted_w = 0
    total_attended_w  = 0
    at_risk_count     = 0
    total_bunk_budget = 0

    for subj in subjects:
        att  = calculate_attendance(subj)
        risk = classify_risk(att)
        bunk = calculate_bunk_budget(subj, att)
        recov = recovery_sessions_needed(subj, att)

        if risk in ('CAUTION', 'CRITICAL'):
            at_risk_count += 1

        total_conducted_w += att['conducted']
        total_attended_w  += att['attended']
        total_bunk_budget += bunk

        subject_data.append({
            'subject':  subj,
            'att':      att,
            'risk':     risk,
            'bunk':     bunk,
            'recovery': recov,
        })

    overall_pct = (
        round(total_attended_w / total_conducted_w * 100, 2)
        if total_conducted_w > 0 else 0.0
    )

    # Upcoming sessions (today + next 7 days)
    upcoming = ClassSession.objects.filter(
        semester=semester,
        date__range=(today, today + timedelta(days=7)),
        status='scheduled'
    ).select_related('subject').order_by('date', 'start_time')[:10]

    remaining_sessions = get_remaining_sessions_count(semester, from_date=today)

    return {
        'semester':          semester,
        'subject_data':      subject_data,
        'overall_pct':       overall_pct,
        'at_risk_count':     at_risk_count,
        'total_bunk_budget': total_bunk_budget,
        'upcoming_sessions': upcoming,
        'remaining_sessions': remaining_sessions,
        'progress':          semester.progress_percent,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Calendar Data
# ─────────────────────────────────────────────────────────────────────────────

def get_calendar_data(semester, year, month):
    """
    Returns sessions and special days for a given month as JSON-serialisable lists.
    """
    from attendance.models import ClassSession, SpecialDay
    import calendar

    _, days_in_month = calendar.monthrange(year, month)
    start = date(year, month, 1)
    end   = date(year, month, days_in_month)

    sessions = ClassSession.objects.filter(
        semester=semester,
        date__range=(start, end)
    ).select_related('subject').order_by('date', 'start_time')

    special_days = SpecialDay.objects.filter(
        semester=semester,
        date__range=(start, end)
    )

    events_dict = {}
    for s in sessions:
        key = s.date.isoformat()
        events_dict.setdefault(key, {'sessions': [], 'special': None})
        events_dict[key]['sessions'].append({
            'id':                   s.id,
            'subject':              s.subject.name,
            'color':                s.subject.color,
            'icon':                 s.subject.icon,
            'session_type':         s.session_type,
            'session_type_display': s.get_session_type_display(),
            'start':                s.start_time.strftime('%H:%M'),
            'end':                  s.end_time.strftime('%H:%M'),
            'status':               s.status,
            'duration':             s.duration_minutes,
        })

    for sp in special_days:
        key = sp.date.isoformat()
        events_dict.setdefault(key, {'sessions': [], 'special': None})
        events_dict[key]['special'] = {
            'id':          sp.id,
            'name':        sp.name,
            'type':        sp.day_type,
            'description': sp.description,
            'affects_all': sp.affects_all_sessions,
        }

    return events_dict


# ─────────────────────────────────────────────────────────────────────────────
# Special Day Application & Removal
# ─────────────────────────────────────────────────────────────────────────────

def apply_special_day(special_day):
    """
    When a SpecialDay is created or updated, update the status of relevant ClassSessions.
    - If affects_all_sessions=True → mark all sessions on that date as 'holiday'/'event'/'exam'.
    - If False → only sessions with a SpecialDaySessionOverride are updated.
    """
    from attendance.models import ClassSession

    day_sessions = ClassSession.objects.filter(
        semester=special_day.semester,
        date=special_day.date
    )

    if special_day.affects_all_sessions:
        status_map = {
            'holiday': 'holiday',
            'exam':    'exam',
            'event':   'event',
            'partial': 'modified',
            'custom':  'modified',
        }
        new_status = status_map.get(special_day.day_type, 'cancelled')
        day_sessions.update(status=new_status)
    else:
        for override in special_day.session_overrides.select_related('session').all():
            override.session.status = override.override_status
            override.session.save(update_fields=['status'])


def remove_special_day(special_day):
    """When a SpecialDay is deleted, restore affected sessions on that date back to scheduled."""
    from attendance.models import ClassSession
    ClassSession.objects.filter(
        semester=special_day.semester,
        date=special_day.date,
        status__in=['holiday', 'event', 'exam', 'modified', 'cancelled']
    ).update(status='scheduled')


def populate_official_holidays(semester):
    """
    Auto-populates standard official gazetted Indian holidays falling within the semester range.
    Returns (created_count, skipped_count).
    """
    from attendance.models import SpecialDay
    official_list = [
        # 2026
        (date(2026, 1, 26), "Republic Day"),
        (date(2026, 3, 4),  "Holi"),
        (date(2026, 3, 21), "Id-ul-Fitr (Ramzan Eid)"),
        (date(2026, 4, 3),  "Good Friday"),
        (date(2026, 4, 14), "Dr. Ambedkar Jayanti"),
        (date(2026, 5, 1),  "May Day / Maharashtra Day"),
        (date(2026, 5, 27), "Bakrid / Eid al-Adha"),
        (date(2026, 6, 26), "Muharram"),
        (date(2026, 8, 15), "Independence Day"),
        (date(2026, 8, 28), "Raksha Bandhan"),
        (date(2026, 9, 4),  "Janmashtami"),
        (date(2026, 9, 15), "Milad-un-Nabi (Id-e-Milad)"),
        (date(2026, 10, 2), "Mahatma Gandhi Jayanti"),
        (date(2026, 10, 20), "Dussehra (Vijayadashami)"),
        (date(2026, 11, 8), "Diwali (Deepavali)"),
        (date(2026, 11, 9), "Govardhan Puja"),
        (date(2026, 11, 10), "Bhai Dooj"),
        (date(2026, 11, 24), "Guru Nanak Jayanti"),
        (date(2026, 12, 25), "Christmas Day"),
        # 2027
        (date(2027, 1, 26), "Republic Day"),
        (date(2027, 3, 23), "Holi"),
        (date(2027, 4, 14), "Dr. Ambedkar Jayanti"),
        (date(2027, 8, 15), "Independence Day"),
        (date(2027, 10, 2), "Mahatma Gandhi Jayanti"),
        (date(2027, 10, 28), "Diwali"),
        (date(2027, 12, 25), "Christmas Day"),
    ]

    created_count = 0
    skipped_count = 0
    for h_date, h_name in official_list:
        if semester.start_date <= h_date <= semester.end_date:
            sp, was_created = SpecialDay.objects.get_or_create(
                semester=semester,
                date=h_date,
                defaults={
                    'name': h_name,
                    'day_type': 'holiday',
                    'description': f'Official Holiday — {h_name}',
                    'affects_all_sessions': True,
                }
            )
            if was_created:
                apply_special_day(sp)
                created_count += 1
            else:
                skipped_count += 1

    return created_count, skipped_count


def batch_set_days_status(semester, date_strs, status, user, holiday_name="Holiday"):
    """
    Batch update multiple dates at once (e.g. from multi-day selection):
    - If status == 'holiday': creates or updates SpecialDay as holiday for each date.
    - If status in ('present', 'absent', 'cancelled'): updates all sessions on each date.
    - If status == 'reset': removes SpecialDay if any, and resets sessions to 'scheduled'.
    """
    from attendance.models import SpecialDay, ClassSession
    updated_dates = 0
    for d_str in date_strs:
        try:
            d = date.fromisoformat(d_str)
        except ValueError:
            continue

        if status == 'holiday':
            sp, _ = SpecialDay.objects.get_or_create(
                semester=semester,
                date=d,
                defaults={'name': holiday_name, 'day_type': 'holiday', 'affects_all_sessions': True}
            )
            sp.name = holiday_name
            sp.day_type = 'holiday'
            sp.affects_all_sessions = True
            sp.save()
            apply_special_day(sp)
            updated_dates += 1
        elif status == 'reset':
            sp = SpecialDay.objects.filter(semester=semester, date=d).first()
            if sp:
                remove_special_day(sp)
                sp.delete()
            ClassSession.objects.filter(semester=semester, date=d).update(status='scheduled')
            updated_dates += 1
        else:
            mark_day_sessions(semester, d, status, user)
            updated_dates += 1

    return updated_dates


# ─────────────────────────────────────────────────────────────────────────────
# Attendance Marking Helpers
# ─────────────────────────────────────────────────────────────────────────────

def mark_session_status(session, status, user, notes=''):
    """Mark a single session's status and update the AttendanceRecord."""
    from attendance.models import AttendanceRecord
    session.status = status
    if notes:
        session.notes = notes
    session.save(update_fields=['status', 'notes'] if notes else ['status'])
    AttendanceRecord.objects.update_or_create(
        session=session,
        defaults={'student': user, 'status': status, 'notes': notes}
    )
    return session


def mark_day_sessions(semester, target_date, status, user, session_ids=None):
    """
    Mark all (or specified subset of) sessions on a date with the given status.
    Skips cancelled or holiday sessions unless explicitly overridden.
    """
    from attendance.models import ClassSession
    qs = ClassSession.objects.filter(semester=semester, date=target_date)
    if session_ids is not None:
        qs = qs.filter(id__in=session_ids)
    else:
        # Exclude non-conducted special day statuses when mass marking
        qs = qs.exclude(status__in=['holiday', 'event', 'exam'])

    updated_count = 0
    for session in qs:
        mark_session_status(session, status, user)
        updated_count += 1
    return updated_count


def mark_all_past_as_present(semester, user):
    """
    Convenience helper: Defaults all past and today's scheduled sessions to 'present'.
    """
    from attendance.models import ClassSession
    today = timezone.localdate()
    scheduled_past = ClassSession.objects.filter(
        semester=semester,
        date__lte=today,
        status='scheduled'
    )
    count = 0
    for session in scheduled_past:
        mark_session_status(session, 'present', user)
        count += 1
    return count
