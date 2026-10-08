"""BunkWise admin configuration."""

from django.contrib import admin
from .models import (
    Semester, Subject, TimetableEntry, ClassSession,
    AttendanceRecord, SpecialDay, SpecialDaySessionOverride,
    Event, PlannedAbsence, SimulationSnapshot
)


@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display  = ['name', 'user', 'start_date', 'end_date', 'min_attendance', 'attendance_policy', 'is_active']
    list_filter   = ['is_active', 'attendance_policy']
    search_fields = ['name', 'user__username']


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display  = ['name', 'code', 'subject_type', 'semester', 'min_attendance']
    list_filter   = ['subject_type', 'semester']
    search_fields = ['name', 'code']


@admin.register(TimetableEntry)
class TimetableEntryAdmin(admin.ModelAdmin):
    list_display = ['semester', 'subject', 'day_of_week', 'start_time', 'end_time', 'room']
    list_filter  = ['day_of_week', 'semester']


@admin.register(ClassSession)
class ClassSessionAdmin(admin.ModelAdmin):
    list_display  = ['date', 'subject', 'start_time', 'end_time', 'status', 'attendance_weight']
    list_filter   = ['status', 'subject__semester']
    search_fields = ['subject__name']
    date_hierarchy = 'date'


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ['student', 'session', 'status', 'marked_at']
    list_filter  = ['status']


@admin.register(SpecialDay)
class SpecialDayAdmin(admin.ModelAdmin):
    list_display = ['date', 'name', 'day_type', 'semester', 'affects_all_sessions']
    list_filter  = ['day_type']
    date_hierarchy = 'date'


admin.site.register(SpecialDaySessionOverride)
admin.site.register(Event)
admin.site.register(PlannedAbsence)
admin.site.register(SimulationSnapshot)

admin.site.site_header = "BunkWise Admin"
admin.site.site_title  = "BunkWise"
admin.site.index_title = "Attendance Management"
