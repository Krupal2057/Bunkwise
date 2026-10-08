"""
BunkWise — Database Models
All 10 normalized models for the complete attendance management system.
"""

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


# ─────────────────────────────────────────────────────────────────────────────
# 1. Semester
# ─────────────────────────────────────────────────────────────────────────────
class Semester(models.Model):
    POLICY_CHOICES = [
        ('session', 'Session-based (each class = 1 unit regardless of duration)'),
        ('period',  'Period-based (each hour = 1 unit)'),
    ]

    user             = models.ForeignKey(User, on_delete=models.CASCADE, related_name='semesters')
    name             = models.CharField(max_length=100)                    # e.g. "5th Semester"
    start_date       = models.DateField()
    end_date         = models.DateField()
    min_attendance   = models.FloatField(
                           default=75.0,
                           validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
                           help_text="Minimum required attendance percentage"
                       )
    safety_buffer    = models.FloatField(
                           default=5.0,
                           validators=[MinValueValidator(0.0), MaxValueValidator(50.0)],
                           help_text="Extra buffer above minimum (effective target = min + buffer)"
                       )
    attendance_policy = models.CharField(max_length=10, choices=POLICY_CHOICES, default='session')
    is_active        = models.BooleanField(default=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.name} ({self.user.username})"

    @property
    def effective_target(self):
        """The operational target including the safety buffer."""
        return min(self.min_attendance + self.safety_buffer, 100.0)

    @property
    def total_days(self):
        return (self.end_date - self.start_date).days + 1

    @property
    def elapsed_days(self):
        today = timezone.localdate()
        if today < self.start_date:
            return 0
        if today > self.end_date:
            return self.total_days
        return (today - self.start_date).days + 1

    @property
    def progress_percent(self):
        if self.total_days == 0:
            return 0
        return round((self.elapsed_days / self.total_days) * 100, 1)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Subject
# ─────────────────────────────────────────────────────────────────────────────
class Subject(models.Model):
    TYPE_CHOICES = [
        ('lecture',  'Lecture'),
        ('lab',      'Lab / Practical'),
        ('tutorial', 'Tutorial'),
        ('other',    'Other'),
    ]

    semester        = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='subjects')
    name            = models.CharField(max_length=150)
    code            = models.CharField(max_length=20, blank=True)
    subject_type    = models.CharField(max_length=10, choices=TYPE_CHOICES, default='lecture')
    min_attendance  = models.FloatField(
                          null=True, blank=True,
                          validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
                          help_text="Leave blank to use semester default"
                      )
    color           = models.CharField(max_length=7, default='#4f46e5', help_text="Hex color for UI")
    icon            = models.CharField(max_length=10, default='📚', help_text="Emoji icon")
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        unique_together = [['semester', 'code']]

    def __str__(self):
        return f"{self.name} ({self.code})" if self.code else self.name

    def get_min_attendance(self):
        """Returns subject-specific or falls back to semester minimum."""
        return self.min_attendance if self.min_attendance is not None else self.semester.min_attendance

    def get_effective_target(self):
        return min(self.get_min_attendance() + self.semester.safety_buffer, 100.0)


# ─────────────────────────────────────────────────────────────────────────────
# 3. TimetableEntry  (weekly repeating schedule)
# ─────────────────────────────────────────────────────────────────────────────
class TimetableEntry(models.Model):
    DAY_CHOICES = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]

    semester    = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='timetable_entries')
    subject     = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='timetable_entries')
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    start_time  = models.TimeField()
    end_time    = models.TimeField()
    room        = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ['day_of_week', 'start_time']

    def __str__(self):
        return f"{self.get_day_of_week_display()} {self.start_time}–{self.end_time}: {self.subject.name}"

    @property
    def duration_minutes(self):
        from datetime import datetime, date
        start = datetime.combine(date.today(), self.start_time)
        end   = datetime.combine(date.today(), self.end_time)
        return int((end - start).total_seconds() // 60)

    @property
    def duration_hours(self):
        return self.duration_minutes / 60.0

    @property
    def attendance_weight(self):
        """
        Weight used in attendance calculation based on semester policy:
        - session: always 1 (regardless of duration)
        - period : number of hours (e.g. 2-hr lab = 2)
        """
        if self.semester.attendance_policy == 'period':
            return self.duration_hours
        return 1.0


# ─────────────────────────────────────────────────────────────────────────────
# 4. ClassSession  (generated date-specific session records)
# ─────────────────────────────────────────────────────────────────────────────
class ClassSession(models.Model):
    STATUS_CHOICES = [
        ('scheduled',  'Scheduled'),
        ('present',    'Present'),
        ('absent',     'Absent'),
        ('cancelled',  'Cancelled'),
        ('holiday',    'Holiday'),
        ('exam',       'Exam'),
        ('event',      'College Event'),
        ('modified',   'Modified'),
    ]

    semester         = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='sessions')
    subject          = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='sessions')
    timetable_entry  = models.ForeignKey(
                           TimetableEntry, on_delete=models.SET_NULL,
                           null=True, blank=True, related_name='sessions'
                       )
    date             = models.DateField()
    start_time       = models.TimeField()
    end_time         = models.TimeField()
    duration_minutes = models.IntegerField()
    status           = models.CharField(max_length=12, choices=STATUS_CHOICES, default='scheduled')
    attendance_weight = models.FloatField(default=1.0,
                            help_text="1 for session-based; hours for period-based")
    notes            = models.TextField(blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['date', 'start_time']
        unique_together = [['semester', 'subject', 'timetable_entry', 'date']]

    def __str__(self):
        return f"{self.date} {self.start_time}: {self.subject.name} [{self.status}]"

    @property
    def is_countable(self):
        """Returns True if this session counts towards attendance denominator."""
        return self.status not in ('cancelled', 'holiday', 'event', 'scheduled')

    @property
    def is_conducted(self):
        """Session was actually held (present or absent recorded)."""
        return self.status in ('present', 'absent')

    @property
    def is_attended(self):
        return self.status == 'present'


# ─────────────────────────────────────────────────────────────────────────────
# 5. AttendanceRecord  (one-to-one with ClassSession)
# ─────────────────────────────────────────────────────────────────────────────
class AttendanceRecord(models.Model):
    STATUS_CHOICES = [
        ('present',   'Present'),
        ('absent',    'Absent'),
        ('cancelled', 'Cancelled'),
    ]

    session   = models.OneToOneField(ClassSession, on_delete=models.CASCADE, related_name='attendance_record')
    student   = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendance_records')
    status    = models.CharField(max_length=10, choices=STATUS_CHOICES)
    marked_at = models.DateTimeField(auto_now=True)
    notes     = models.TextField(blank=True)

    def __str__(self):
        return f"{self.student.username} – {self.session} – {self.status}"


# ─────────────────────────────────────────────────────────────────────────────
# 6. SpecialDay  (holidays, exams, events, partial days)
# ─────────────────────────────────────────────────────────────────────────────
class SpecialDay(models.Model):
    TYPE_CHOICES = [
        ('holiday', 'Holiday'),
        ('exam',    'Exam Day'),
        ('event',   'College Event'),
        ('partial', 'Partial Day'),
        ('custom',  'Custom'),
    ]

    semester             = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='special_days')
    date                 = models.DateField()
    day_type             = models.CharField(max_length=10, choices=TYPE_CHOICES)
    name                 = models.CharField(max_length=150)
    description          = models.TextField(blank=True)
    affects_all_sessions = models.BooleanField(
                               default=True,
                               help_text="True = all sessions cancelled. False = use per-session overrides."
                           )

    class Meta:
        ordering = ['date']
        unique_together = [['semester', 'date']]

    def __str__(self):
        return f"{self.date}: {self.name} ({self.day_type})"


# ─────────────────────────────────────────────────────────────────────────────
# 7. SpecialDaySessionOverride  (for partial days — per-session control)
# ─────────────────────────────────────────────────────────────────────────────
class SpecialDaySessionOverride(models.Model):
    OVERRIDE_CHOICES = [
        ('cancelled',  'Cancelled'),
        ('conducted',  'Conducted as usual'),
        ('exam',       'Exam replaces session'),
        ('event',      'Event replaces session'),
    ]

    special_day     = models.ForeignKey(SpecialDay, on_delete=models.CASCADE, related_name='session_overrides')
    session         = models.ForeignKey(ClassSession, on_delete=models.CASCADE, related_name='overrides')
    override_status = models.CharField(max_length=10, choices=OVERRIDE_CHOICES)

    def __str__(self):
        return f"{self.special_day.name} → {self.session.subject.name}: {self.override_status}"


# ─────────────────────────────────────────────────────────────────────────────
# 8. Event  (student personal events — trips, medical, etc.)
# ─────────────────────────────────────────────────────────────────────────────
class Event(models.Model):
    TYPE_CHOICES = [
        ('trip',     'Trip / Travel'),
        ('medical',  'Medical Appointment'),
        ('family',   'Family Function'),
        ('personal', 'Personal'),
        ('other',    'Other'),
    ]

    user        = models.ForeignKey(User, on_delete=models.CASCADE, related_name='events')
    semester    = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='events')
    name        = models.CharField(max_length=150)
    event_type  = models.CharField(max_length=10, choices=TYPE_CHOICES, default='personal')
    start_date  = models.DateField()
    end_date    = models.DateField()
    description = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['start_date']

    def __str__(self):
        return f"{self.name} ({self.start_date} → {self.end_date})"

    @property
    def duration_days(self):
        return (self.end_date - self.start_date).days + 1


# ─────────────────────────────────────────────────────────────────────────────
# 9. PlannedAbsence  (optimizer / what-if / confirmed plans)
# ─────────────────────────────────────────────────────────────────────────────
class PlannedAbsence(models.Model):
    user         = models.ForeignKey(User, on_delete=models.CASCADE, related_name='planned_absences')
    session      = models.ForeignKey(ClassSession, on_delete=models.CASCADE, related_name='planned_absences')
    reason       = models.CharField(max_length=200, blank=True)
    is_confirmed = models.BooleanField(
                       default=False,
                       help_text="False = simulation/what-if. True = student has confirmed this absence."
                   )
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['user', 'session']]

    def __str__(self):
        state = "Confirmed" if self.is_confirmed else "Simulated"
        return f"{state} absence: {self.session}"


# ─────────────────────────────────────────────────────────────────────────────
# 10. SimulationSnapshot  (stores what-if results for display — never affects real data)
# ─────────────────────────────────────────────────────────────────────────────
class SimulationSnapshot(models.Model):
    user        = models.ForeignKey(User, on_delete=models.CASCADE, related_name='simulations')
    semester    = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='simulations')
    label       = models.CharField(max_length=200, help_text="e.g. 'What if I take Friday off?'")
    result_json = models.JSONField(help_text="Stores projected attendance per subject as JSON")
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username}: {self.label}"
