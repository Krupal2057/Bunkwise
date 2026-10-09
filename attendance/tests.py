import math
from datetime import date, time, timedelta
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from attendance.models import (
    Semester, Subject, TimetableEntry, ClassSession,
    AttendanceRecord, SpecialDay, Event
)
from attendance import services


class BunkWiseAttendanceLogicTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='teststudent', password='password123')
        self.today = date(2026, 10, 1)
        self.semester = Semester.objects.create(
            user=self.user,
            name="Test Semester",
            start_date=self.today - timedelta(days=30),
            end_date=self.today + timedelta(days=60),
            min_attendance=75.0,
            safety_buffer=5.0,
            attendance_policy='session'
        )
        self.subject = Subject.objects.create(
            semester=self.semester,
            name="Algorithms",
            code="CS301",
            min_attendance=75.0
        )

    def test_attendance_calculation_basic(self):
        # Create 10 conducted sessions: 8 present, 2 absent -> 80%
        for i in range(10):
            sess = ClassSession.objects.create(
                semester=self.semester,
                subject=self.subject,
                date=self.today - timedelta(days=i + 1),
                start_time=time(9, 0),
                end_time=time(10, 0),
                duration_minutes=60,
                status='present' if i < 8 else 'absent',
                attendance_weight=1.0
            )
            AttendanceRecord.objects.create(
                session=sess,
                student=self.user,
                status=sess.status
            )

        att = services.calculate_attendance(self.subject)
        self.assertEqual(att['conducted'], 10)
        self.assertEqual(att['attended'], 8)
        self.assertEqual(att['absent'], 2)
        self.assertEqual(att['percentage'], 80.0)

    def test_bunk_budget_calculation(self):
        # 8 attended out of 10 conducted, threshold 75% (0.75)
        # formula: floor((8 - 0.75*10) / 0.75) = floor((8 - 7.5)/0.75) = floor(0.5/0.75) = 0
        att_data = {
            'conducted': 10,
            'attended': 8,
            'absent': 2,
            'percentage': 80.0,
            'min_required': 75.0,
            'effective_target': 80.0
        }
        budget = services.calculate_bunk_budget(self.subject, att_data)
        self.assertEqual(budget, 0)

        # 16 attended out of 16 conducted (100%), threshold 75%
        # formula: floor((16 - 12)/0.75) = floor(4/0.75) = floor(5.333) = 5 bunks
        att_data_high = {
            'conducted': 16,
            'attended': 16,
            'absent': 0,
            'percentage': 100.0,
            'min_required': 75.0,
            'effective_target': 80.0
        }
        budget_high = services.calculate_bunk_budget(self.subject, att_data_high)
        self.assertEqual(budget_high, 5)

    def test_recovery_sessions_needed(self):
        # 6 attended out of 10 conducted (60%), threshold 75%
        # shortfall = 0.75 * 10 - 6 = 7.5 - 6 = 1.5
        # needed = ceil(1.5 / (1 - 0.75)) = ceil(1.5 / 0.25) = 6 sessions
        att_data_low = {
            'conducted': 10,
            'attended': 6,
            'absent': 4,
            'percentage': 60.0,
            'min_required': 75.0,
            'effective_target': 80.0
        }
        recovery = services.recovery_sessions_needed(self.subject, att_data_low)
        self.assertEqual(recovery, 6)

        # If already at 80% with 75% target, recovery should be 0
        att_data_ok = {
            'conducted': 10,
            'attended': 8,
            'absent': 2,
            'percentage': 80.0,
            'min_required': 75.0,
            'effective_target': 80.0
        }
        self.assertEqual(services.recovery_sessions_needed(self.subject, att_data_ok), 0)

    def test_risk_classification(self):
        # Min required = 75%, Effective target = 80% (with 5% buffer)
        # >= 80% -> SAFE
        self.assertEqual(services.classify_risk({'percentage': 85.0, 'effective_target': 80.0, 'min_required': 75.0}), 'SAFE')
        # 75% to 79.99% -> CAUTION
        self.assertEqual(services.classify_risk({'percentage': 77.0, 'effective_target': 80.0, 'min_required': 75.0}), 'CAUTION')
        # < 75% -> CRITICAL
        self.assertEqual(services.classify_risk({'percentage': 72.0, 'effective_target': 80.0, 'min_required': 75.0}), 'CRITICAL')


class BunkWiseViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='teststudent', password='password123')
        self.today = date.today()
        self.semester = Semester.objects.create(
            user=self.user,
            name="Fall 2026",
            start_date=self.today - timedelta(days=20),
            end_date=self.today + timedelta(days=40),
            min_attendance=75.0,
            safety_buffer=5.0,
            attendance_policy='session'
        )
        self.subject = Subject.objects.create(
            semester=self.semester,
            name="Database Systems",
            code="CS401",
            min_attendance=75.0
        )

    def test_unauthenticated_redirects(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_authenticated_dashboard(self):
        self.client.login(username='teststudent', password='password123')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fall 2026")
        self.assertContains(response, "Database Systems")

    def test_subject_list_view(self):
        self.client.login(username='teststudent', password='password123')
        response = self.client.get(reverse('subject_list', args=[self.semester.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CS401")

    def test_timetable_view(self):
        self.client.login(username='teststudent', password='password123')
        # Create a timetable entry to verify display
        TimetableEntry.objects.create(
            semester=self.semester,
            subject=self.subject,
            day_of_week=0,
            start_time=time(9, 0),
            end_time=time(10, 0),
        )
        response = self.client.get(reverse('timetable', args=[self.semester.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Weekly Schedule")
        self.assertContains(response, "Database Systems")

    def test_simulator_view(self):
        self.client.login(username='teststudent', password='password123')
        response = self.client.get(reverse('simulator', args=[self.semester.id]))
        self.assertEqual(response.status_code, 200)

    def test_optimizer_view(self):
        self.client.login(username='teststudent', password='password123')
        response = self.client.get(reverse('optimizer', args=[self.semester.id]))
        self.assertEqual(response.status_code, 200)

    def test_analytics_reports_view(self):
        self.client.login(username='teststudent', password='password123')
        response = self.client.get(reverse('analytics', args=[self.semester.id]))
        self.assertEqual(response.status_code, 200)

    def test_what_if_simulation_service(self):
        # 8 attended out of 10 conducted = 80%
        for i in range(10):
            ClassSession.objects.create(
                semester=self.semester,
                subject=self.subject,
                date=self.today - timedelta(days=i + 1),
                start_time=time(9, 0),
                end_time=time(10, 0),
                duration_minutes=60,
                status='present' if i < 8 else 'absent'
            )
        # Create 2 future scheduled sessions
        fut1 = ClassSession.objects.create(
            semester=self.semester,
            subject=self.subject,
            date=self.today + timedelta(days=1),
            start_time=time(9, 0),
            end_time=time(10, 0),
            duration_minutes=60,
            status='scheduled'
        )
        fut2 = ClassSession.objects.create(
            semester=self.semester,
            subject=self.subject,
            date=self.today + timedelta(days=2),
            start_time=time(9, 0),
            end_time=time(10, 0),
            duration_minutes=60,
            status='scheduled'
        )

        # Simulating bunking 2 sessions -> conducted becomes 12, attended stays 8 -> 8/12 = 66.67%
        res = services.simulate_absences([fut1.id, fut2.id])
        self.assertIn(self.subject.id, res)
        subj_res = res[self.subject.id]
        self.assertEqual(subj_res['current_pct'], 80.0)
        self.assertAlmostEqual(subj_res['projected_pct'], 66.67, places=1)
        self.assertEqual(subj_res['projected_risk'], 'CRITICAL')

        # Real session statuses in DB must remain 'scheduled'
        fut1.refresh_from_db()
        fut2.refresh_from_db()
        self.assertEqual(fut1.status, 'scheduled')
        self.assertEqual(fut2.status, 'scheduled')

    def test_special_day_affects_sessions(self):
        sess = ClassSession.objects.create(
            semester=self.semester,
            subject=self.subject,
            date=self.today + timedelta(days=5),
            start_time=time(9, 0),
            end_time=time(10, 0),
            duration_minutes=60,
            status='scheduled'
        )
        sp = SpecialDay.objects.create(
            semester=self.semester,
            date=self.today + timedelta(days=5),
            day_type='holiday',
            name='National Holiday',
            affects_all_sessions=True
        )
        services.apply_special_day(sp)
        sess.refresh_from_db()
        self.assertEqual(sess.status, 'holiday')

        # Test special day removal resets status
        services.remove_special_day(sp)
        sess.refresh_from_db()
        self.assertEqual(sess.status, 'scheduled')

    def test_full_crud_operations(self):
        self.client.login(username='teststudent', password='password123')

        # 1. Subject Edit & Delete
        edit_resp = self.client.post(reverse('subject_edit', args=[self.subject.id]), {
            'name': 'Advanced Algorithms',
            'code': 'CS301-A',
            'subject_type': 'lecture',
            'has_lab': True,
            'color': '#4f46e5',
            'icon': '💻'
        })
        self.assertEqual(edit_resp.status_code, 302)
        self.subject.refresh_from_db()
        self.assertEqual(self.subject.name, 'Advanced Algorithms')
        self.assertTrue(self.subject.has_lab)

        # 2. Timetable Entry Edit & Delete
        entry = TimetableEntry.objects.create(
            semester=self.semester,
            subject=self.subject,
            session_type='lecture',
            day_of_week=1,
            start_time=time(10, 0),
            end_time=time(11, 0),
            room='Room 101'
        )
        entry_edit = self.client.post(reverse('timetable_entry_edit', args=[entry.id]), {
            'subject': self.subject.id,
            'session_type': 'lab',
            'day_of_week': 2,
            'start_time': '11:00',
            'end_time': '13:00',
            'room': 'Lab 4'
        })
        self.assertEqual(entry_edit.status_code, 302)
        entry.refresh_from_db()
        self.assertEqual(entry.session_type, 'lab')
        self.assertEqual(entry.day_of_week, 2)
        self.assertEqual(entry.room, 'Lab 4')

        entry_del = self.client.post(reverse('timetable_entry_delete', args=[entry.id]))
        self.assertEqual(entry_del.status_code, 302)
        self.assertFalse(TimetableEntry.objects.filter(id=entry.id).exists())

        # 3. Special Day Edit & Delete
        sp = SpecialDay.objects.create(
            semester=self.semester,
            date=self.today + timedelta(days=10),
            day_type='event',
            name='Tech Fest',
            affects_all_sessions=True
        )
        sp_edit = self.client.post(reverse('special_day_edit', args=[sp.id]), {
            'date': (self.today + timedelta(days=10)).isoformat(),
            'day_type': 'holiday',
            'name': 'Tech Fest Holiday',
            'affects_all_sessions': True
        })
        self.assertEqual(sp_edit.status_code, 302)
        sp.refresh_from_db()
        self.assertEqual(sp.name, 'Tech Fest Holiday')

        sp_del = self.client.post(reverse('special_day_delete', args=[sp.id]))
        self.assertEqual(sp_del.status_code, 302)
        self.assertFalse(SpecialDay.objects.filter(id=sp.id).exists())

        # 4. Personal Event Edit & Delete
        event = Event.objects.create(
            user=self.user,
            semester=self.semester,
            name='Hackathon',
            event_type='personal',
            start_date=self.today + timedelta(days=15),
            end_date=self.today + timedelta(days=16)
        )
        ev_edit = self.client.post(reverse('event_edit', args=[event.id]), {
            'name': 'National Hackathon',
            'event_type': 'trip',
            'start_date': (self.today + timedelta(days=15)).isoformat(),
            'end_date': (self.today + timedelta(days=17)).isoformat()
        })
        self.assertEqual(ev_edit.status_code, 302)
        event.refresh_from_db()
        self.assertEqual(event.name, 'National Hackathon')

        ev_del = self.client.post(reverse('event_delete', args=[event.id]))
        self.assertEqual(ev_del.status_code, 302)
        self.assertFalse(Event.objects.filter(id=event.id).exists())

        # 5. Class Session Edit & Delete
        sess = ClassSession.objects.create(
            semester=self.semester,
            subject=self.subject,
            date=self.today + timedelta(days=3),
            start_time=time(9, 0),
            end_time=time(10, 0),
            duration_minutes=60,
            status='scheduled'
        )
        sess_edit = self.client.post(reverse('session_edit', args=[sess.id]), {
            'subject': self.subject.id,
            'session_type': 'lab',
            'start_time': '09:00',
            'end_time': '11:00',
            'status': 'present',
            'notes': 'Extra makeup lab'
        })
        self.assertEqual(sess_edit.status_code, 302)
        sess.refresh_from_db()
        self.assertEqual(sess.session_type, 'lab')
        self.assertEqual(sess.duration_minutes, 120)
        self.assertEqual(sess.notes, 'Extra makeup lab')

        sess_del = self.client.post(reverse('session_delete', args=[sess.id]))
        self.assertEqual(sess_del.status_code, 302)
        self.assertFalse(ClassSession.objects.filter(id=sess.id).exists())

        # 6. Extra Session Add via Day Detail
        target_date_str = (self.today + timedelta(days=4)).isoformat()
        add_extra = self.client.post(reverse('day_detail', args=[self.semester.id, target_date_str]), {
            'action': 'add_extra',
            'subject': self.subject.id,
            'session_type': 'lecture',
            'start_time': '14:00',
            'end_time': '15:00',
            'status': 'present',
            'notes': 'Ad-hoc session'
        })
        self.assertEqual(add_extra.status_code, 302)
        created_extra = ClassSession.objects.filter(semester=self.semester, date=self.today + timedelta(days=4)).first()
        self.assertIsNotNone(created_extra)
        self.assertEqual(created_extra.notes, 'Ad-hoc session')
        self.assertEqual(created_extra.status, 'present')

        # 7. Semester Delete
        sem_del = self.client.post(reverse('semester_delete', args=[self.semester.id]))
        self.assertEqual(sem_del.status_code, 302)
        self.assertFalse(Semester.objects.filter(id=self.semester.id).exists())


