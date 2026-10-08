"""BunkWise — URL patterns for the attendance app."""

from django.urls import path
from . import views

urlpatterns = [

    # ── Root redirect ─────────────────────────────────────────────────────
    path('', views.dashboard, name='home'),

    # ── Authentication ─────────────────────────────────────────────────────
    path('register/', views.register_view, name='register'),
    path('login/',    views.login_view,    name='login'),
    path('logout/',   views.logout_view,   name='logout'),

    # ── Dashboard ──────────────────────────────────────────────────────────
    path('dashboard/', views.dashboard, name='dashboard'),

    # ── Semester ───────────────────────────────────────────────────────────
    path('semester/setup/',                  views.semester_setup,    name='semester_setup'),
    path('semester/<int:semester_id>/edit/', views.semester_edit,     name='semester_edit'),
    path('semester/<int:semester_id>/activate/', views.semester_activate, name='semester_activate'),

    # ── Subjects ───────────────────────────────────────────────────────────
    path('semester/<int:semester_id>/subjects/',            views.subject_list,   name='subject_list'),
    path('subject/<int:subject_id>/edit/',                  views.subject_edit,   name='subject_edit'),
    path('subject/<int:subject_id>/delete/',                views.subject_delete, name='subject_delete'),

    # ── Timetable ──────────────────────────────────────────────────────────
    path('semester/<int:semester_id>/timetable/',           views.timetable_view,           name='timetable'),
    path('timetable/entry/<int:entry_id>/delete/',          views.timetable_entry_delete,   name='timetable_entry_delete'),
    path('semester/<int:semester_id>/generate-sessions/',   views.generate_sessions_view,   name='generate_sessions'),

    # ── Calendar ───────────────────────────────────────────────────────────
    path('semester/<int:semester_id>/calendar/',            views.calendar_view, name='calendar_view'),
    path('semester/<int:semester_id>/day/<str:date_str>/',  views.day_detail,    name='day_detail'),

    # ── Special days ───────────────────────────────────────────────────────
    path('semester/<int:semester_id>/special-days/',        views.special_days,        name='special_days'),
    path('special-day/<int:day_id>/delete/',                views.special_day_delete,  name='special_day_delete'),

    # ── Attendance ─────────────────────────────────────────────────────────
    path('semester/<int:semester_id>/attendance/',          views.attendance_overview, name='attendance_overview'),

    # ── Bunk budget ────────────────────────────────────────────────────────
    path('semester/<int:semester_id>/bunk-budget/',         views.bunk_budget,   name='bunk_budget'),

    # ── Simulator / Optimizer ──────────────────────────────────────────────
    path('semester/<int:semester_id>/simulator/',           views.simulator,           name='simulator'),
    path('semester/<int:semester_id>/simulate-range/',      views.simulate_date_range_view, name='simulate_range'),
    path('semester/<int:semester_id>/optimizer/',           views.bunk_optimizer,      name='optimizer'),
    path('semester/<int:semester_id>/bridge-days/',         views.bridge_days,         name='bridge_days'),

    # ── Event planner ──────────────────────────────────────────────────────
    path('semester/<int:semester_id>/events/',              views.event_planner, name='event_planner'),
    path('event/<int:event_id>/delete/',                    views.event_delete,  name='event_delete'),

    # ── Analytics ──────────────────────────────────────────────────────────
    path('semester/<int:semester_id>/analytics/',           views.analytics,     name='analytics'),

    # ── AJAX ───────────────────────────────────────────────────────────────
    path('api/session/<int:session_id>/status/',            views.api_session_status, name='api_session_status'),
]
