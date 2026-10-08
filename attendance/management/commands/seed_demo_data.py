from datetime import date, time, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from attendance.models import (
    Semester, Subject, TimetableEntry, ClassSession,
    AttendanceRecord, SpecialDay, Event
)
from attendance.services import generate_sessions


class Command(BaseCommand):
    help = "Seed demo user and realistic semester attendance data for BunkWise"

    def add_arguments(self, parser):
        parser.add_argument('--username', default='demo', help='Username for demo user')
        parser.add_argument('--password', default='demo1234', help='Password for demo user')

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']

        user, created = User.objects.get_or_create(
            username=username,
            defaults={'email': f'{username}@example.com', 'first_name': 'Demo', 'last_name': 'Student'}
        )
        user.set_password(password)
        user.save()

        self.stdout.write(self.style.SUCCESS(f"User '{username}' ready (password: '{password}')."))

        # Clear existing data for this user
        Semester.objects.filter(user=user).delete()

        # Create Semester (e.g. Current 5th Sem)
        today = date.today()
        # Set semester start 6 weeks ago, end in 8 weeks
        start_date = today - timedelta(days=42)
        end_date = today + timedelta(days=56)

        semester = Semester.objects.create(
            user=user,
            name="5th Semester (B.Tech CSE)",
            start_date=start_date,
            end_date=end_date,
            min_attendance=75.0,
            safety_buffer=5.0,
            attendance_policy='session',
            is_active=True,
        )

        self.stdout.write(f"Created semester: {semester.name}")

        # Create Subjects with different target risk zones
        subjects_data = [
            {
                "name": "Data Structures & Algorithms",
                "code": "CS301",
                "type": "lecture",
                "color": "#4f46e5",
                "icon": "⚡",
                "min_attendance": 75.0,
            },
            {
                "name": "Operating Systems",
                "code": "CS302",
                "type": "lecture",
                "color": "#0ea5e9",
                "icon": "💻",
                "min_attendance": 75.0,
            },
            {
                "name": "Computer Networks",
                "code": "CS303",
                "type": "lecture",
                "color": "#10b981",
                "icon": "🌐",
                "min_attendance": 75.0,
            },
            {
                "name": "Database Management Systems",
                "code": "CS304",
                "type": "lecture",
                "color": "#f59e0b",
                "icon": "🗄️",
                "min_attendance": 80.0,
            },
            {
                "name": "Web Technologies Lab",
                "code": "CS305P",
                "type": "lab",
                "color": "#ec4899",
                "icon": "🔬",
                "min_attendance": 85.0,
            },
        ]

        created_subjects = {}
        for s_data in subjects_data:
            subj = Subject.objects.create(
                semester=semester,
                name=s_data["name"],
                code=s_data["code"],
                subject_type=s_data["type"],
                color=s_data["color"],
                icon=s_data["icon"],
                min_attendance=s_data["min_attendance"]
            )
            created_subjects[s_data["code"]] = subj

        # Timetable Entries
        # Monday (0) to Friday (4)
        timetable_plan = [
            # Monday
            (0, "CS301", time(9, 0), time(10, 0), "LH-101"),
            (0, "CS302", time(10, 15), time(11, 15), "LH-101"),
            (0, "CS304", time(11, 30), time(12, 30), "LH-102"),
            (0, "CS305P", time(13, 30), time(15, 30), "Lab-3"),

            # Tuesday
            (1, "CS303", time(9, 0), time(10, 0), "LH-101"),
            (1, "CS301", time(10, 15), time(11, 15), "LH-101"),
            (1, "CS302", time(11, 30), time(12, 30), "LH-101"),

            # Wednesday
            (2, "CS304", time(9, 0), time(10, 0), "LH-102"),
            (2, "CS303", time(10, 15), time(11, 15), "LH-101"),
            (2, "CS301", time(11, 30), time(12, 30), "LH-101"),

            # Thursday
            (3, "CS302", time(9, 0), time(10, 0), "LH-101"),
            (3, "CS303", time(10, 15), time(11, 15), "LH-101"),
            (3, "CS304", time(11, 30), time(12, 30), "LH-102"),
            (3, "CS305P", time(13, 30), time(15, 30), "Lab-3"),

            # Friday
            (4, "CS301", time(9, 0), time(10, 0), "LH-101"),
            (4, "CS302", time(10, 15), time(11, 15), "LH-101"),
            (4, "CS303", time(11, 30), time(12, 30), "LH-101"),
        ]

        for dow, code, st, et, room in timetable_plan:
            TimetableEntry.objects.create(
                semester=semester,
                subject=created_subjects[code],
                day_of_week=dow,
                start_time=st,
                end_time=et,
                room=room
            )

        # Generate Sessions
        created_count, _ = generate_sessions(semester)
        self.stdout.write(f"Generated {created_count} class sessions across the semester.")

        # Add Special Days (Holidays, Mid-terms)
        holidays_plan = [
            (today - timedelta(days=20), "holiday", "Mid-Semester Break"),
            (today + timedelta(days=12), "holiday", "Festival Holiday"),
            (today + timedelta(days=30), "exam", "Mid-Term Examinations"),
        ]
        for h_date, h_type, h_name in holidays_plan:
            SpecialDay.objects.create(
                semester=semester,
                date=h_date,
                day_type=h_type,
                name=h_name,
                affects_all_sessions=True
            )
            # Update affected sessions
            ClassSession.objects.filter(semester=semester, date=h_date).update(status=h_type)

        # Add a sample planned event
        Event.objects.create(
            user=user,
            semester=semester,
            name="Hackathon Weekend Trip",
            event_type="trip",
            start_date=today + timedelta(days=18),
            end_date=today + timedelta(days=20),
            description="Attending national hackathon"
        )

        # Mark attendance for past sessions with realistic varied rates
        # CS301 (DSA) -> ~90% (Safe)
        # CS302 (OS)  -> ~78% (Caution)
        # CS303 (CN)  -> ~68% (Critical - under 75%)
        # CS304 (DBMS)-> ~88% (Safe)
        # CS305P (Lab)-> ~100% (Safe)
        past_sessions = ClassSession.objects.filter(
            semester=semester,
            date__lte=today,
            status='scheduled'
        ).order_by('date')

        subj_counters = {code: 0 for code in created_subjects}

        for sess in past_sessions:
            code = sess.subject.code
            subj_counters[code] += 1
            idx = subj_counters[code]

            # Determine present vs absent
            if code == "CS301":
                status = 'absent' if idx in [3, 8] else 'present'
            elif code == "CS302":
                status = 'absent' if idx in [2, 5, 8, 11] else 'present'
            elif code == "CS303":
                status = 'absent' if idx in [1, 3, 6, 8, 10] else 'present'
            elif code == "CS304":
                status = 'absent' if idx in [4] else 'present'
            elif code == "CS305P":
                status = 'present'
            sess.status = status
            sess.save(update_fields=['status'])
            AttendanceRecord.objects.update_or_create(
                session=sess,
                defaults={'student': user, 'status': status}
            )

        self.stdout.write(self.style.SUCCESS("Successfully seeded comprehensive demo data for BunkWise!"))
        self.stdout.write(self.style.SUCCESS(f"Login with user: '{username}' / '{password}'"))
