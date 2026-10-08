"""
BunkWise — Views
Auth, Dashboard, Semester, Subject, Timetable, Calendar, Attendance, Bunk Optimizer, Reports.
"""

import json
import io
import base64
from datetime import date, timedelta

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend — required for server-side rendering
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone

from .models import (
    Semester, Subject, TimetableEntry, ClassSession,
    AttendanceRecord, SpecialDay, Event, PlannedAbsence, SimulationSnapshot
)
from .forms import (
    RegisterForm, LoginForm, SemesterForm, SubjectForm,
    TimetableEntryForm, AttendanceMarkForm, SpecialDayForm, EventForm
)
from . import services


# ═════════════════════════════════════════════════════════════════════════════
# Helper
# ═════════════════════════════════════════════════════════════════════════════

def _get_active_semester(user):
    """Return the active semester or None."""
    return Semester.objects.filter(user=user, is_active=True).order_by('-start_date').first()


# ═════════════════════════════════════════════════════════════════════════════
# Authentication
# ═════════════════════════════════════════════════════════════════════════════

def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f"Welcome to BunkWise, {user.first_name or user.username}! 🎓 Let's set up your semester.")
        return redirect('semester_setup')
    return render(request, 'attendance/auth/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        login(request, user)
        return redirect('dashboard')
    return render(request, 'attendance/auth/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, "You've been logged out. See you next class! 👋")
    return redirect('login')


# ═════════════════════════════════════════════════════════════════════════════
# Dashboard
# ═════════════════════════════════════════════════════════════════════════════

@login_required
def dashboard(request):
    data = services.get_dashboard_data(request.user)
    if data is None:
        messages.info(request, "Welcome! Start by setting up your semester.")
        return redirect('semester_setup')
    return render(request, 'attendance/dashboard.html', {'data': data})


# ═════════════════════════════════════════════════════════════════════════════
# Semester
# ═════════════════════════════════════════════════════════════════════════════

@login_required
def semester_setup(request):
    """Create a new semester or show existing semesters."""
    semesters = Semester.objects.filter(user=request.user)
    form = SemesterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        semester = form.save(commit=False)
        semester.user = request.user
        # Deactivate previous active semesters
        Semester.objects.filter(user=request.user, is_active=True).update(is_active=False)
        semester.is_active = True
        semester.save()
        messages.success(request, f"Semester '{semester.name}' created! Now add your subjects.")
        return redirect('subject_list', semester_id=semester.id)
    return render(request, 'attendance/semester/setup.html', {'form': form, 'semesters': semesters})


@login_required
def semester_activate(request, semester_id):
    semester = get_object_or_404(Semester, id=semester_id, user=request.user)
    Semester.objects.filter(user=request.user, is_active=True).update(is_active=False)
    semester.is_active = True
    semester.save()
    messages.success(request, f"'{semester.name}' is now your active semester.")
    return redirect('dashboard')


@login_required
def semester_edit(request, semester_id):
    semester = get_object_or_404(Semester, id=semester_id, user=request.user)
    form = SemesterForm(request.POST or None, instance=semester)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Semester updated.")
        return redirect('dashboard')
    return render(request, 'attendance/semester/edit.html', {'form': form, 'semester': semester})


# ═════════════════════════════════════════════════════════════════════════════
# Subjects
# ═════════════════════════════════════════════════════════════════════════════

@login_required
def subject_list(request, semester_id):
    semester = get_object_or_404(Semester, id=semester_id, user=request.user)
    subjects = semester.subjects.all()
    form = SubjectForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        subj = form.save(commit=False)
        subj.semester = semester
        subj.save()
        messages.success(request, f"Subject '{subj.name}' added! ✅")
        return redirect('subject_list', semester_id=semester.id)
    return render(request, 'attendance/subject/list.html', {
        'semester': semester, 'subjects': subjects, 'form': form
    })


@login_required
def subject_edit(request, subject_id):
    subject  = get_object_or_404(Subject, id=subject_id, semester__user=request.user)
    form = SubjectForm(request.POST or None, instance=subject)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f"'{subject.name}' updated.")
        return redirect('subject_list', semester_id=subject.semester.id)
    return render(request, 'attendance/subject/edit.html', {'form': form, 'subject': subject})


@login_required
def subject_delete(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id, semester__user=request.user)
    semester_id = subject.semester.id
    if request.method == 'POST':
        subject.delete()
        messages.warning(request, f"'{subject.name}' deleted.")
    return redirect('subject_list', semester_id=semester_id)


# ═════════════════════════════════════════════════════════════════════════════
# Timetable
# ═════════════════════════════════════════════════════════════════════════════

@login_required
def timetable_view(request, semester_id):
    semester = get_object_or_404(Semester, id=semester_id, user=request.user)
    entries  = semester.timetable_entries.select_related('subject').order_by('day_of_week', 'start_time')
    form = TimetableEntryForm(semester, request.POST or None)

    if request.method == 'POST' and form.is_valid():
        entry = form.save(commit=False)
        entry.semester = semester
        entry.save()
        messages.success(request, "Timetable entry added.")
        return redirect('timetable', semester_id=semester.id)

    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    day_schedule = [
        {'dow': i, 'name': day_names[i], 'entries': days[i]}
        for i in range(7)
    ]

    return render(request, 'attendance/timetable/timetable.html', {
        'semester': semester, 'days': days, 'form': form,
        'day_names': day_names, 'day_schedule': day_schedule
    })


@login_required
def timetable_entry_delete(request, entry_id):
    entry = get_object_or_404(TimetableEntry, id=entry_id, semester__user=request.user)
    semester_id = entry.semester.id
    if request.method == 'POST':
        entry.delete()
        messages.warning(request, "Timetable entry removed.")
    return redirect('timetable', semester_id=semester_id)


@login_required
def generate_sessions_view(request, semester_id):
    """Generate ClassSession records for the entire semester."""
    semester = get_object_or_404(Semester, id=semester_id, user=request.user)
    if request.method == 'POST':
        action = request.POST.get('action', 'generate')
        if action == 'regenerate':
            created, skipped = services.regenerate_sessions(semester)
            messages.success(request, f"Regenerated: {created} sessions created, {skipped} skipped.")
        else:
            created, skipped = services.generate_sessions(semester)
            messages.success(request, f"Generated: {created} new sessions, {skipped} already existed.")
        return redirect('calendar_view', semester_id=semester.id)
    return render(request, 'attendance/timetable/generate_confirm.html', {'semester': semester})


# ═════════════════════════════════════════════════════════════════════════════
# Calendar
# ═════════════════════════════════════════════════════════════════════════════

@login_required
def calendar_view(request, semester_id):
    semester = get_object_or_404(Semester, id=semester_id, user=request.user)
    today = timezone.localdate()

    # Month navigation
    try:
        year  = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
    except (ValueError, TypeError):
        year, month = today.year, today.month

    # Clamp to semester range
    sem_start = date(semester.start_date.year, semester.start_date.month, 1)
    sem_end   = date(semester.end_date.year, semester.end_date.month, 1)

    cal_date = date(year, month, 1)
    if cal_date < sem_start:
        cal_date = sem_start
    if cal_date > sem_end:
        cal_date = sem_end

    year, month = cal_date.year, cal_date.month

    import calendar as cal_mod
    cal_mod.setfirstweekday(0)  # Monday first
    month_matrix = cal_mod.monthcalendar(year, month)
    _, days_in_month = cal_mod.monthrange(year, month)

    calendar_data = services.get_calendar_data(semester, year, month)

    prev_month = cal_date - timedelta(days=1)
    next_month = date(year, month, days_in_month) + timedelta(days=1)

    special_form = SpecialDayForm(request.POST or None)
    if request.method == 'POST' and special_form.is_valid():
        sp = special_form.save(commit=False)
        sp.semester = semester
        sp.save()
        services.apply_special_day(sp)
        messages.success(request, f"'{sp.name}' added to calendar.")
        return redirect('calendar_view', semester_id=semester.id)

    return render(request, 'attendance/calendar/calendar.html', {
        'semester':      semester,
        'month_matrix':  json.dumps(month_matrix),
        'year':          year,
        'month':         month,
        'month_name':    cal_mod.month_name[month],
        'calendar_data': json.dumps(calendar_data),
        'cal_dict':      calendar_data,
        'today':         today.isoformat(),
        'prev_year':     prev_month.year,
        'prev_month':    prev_month.month,
        'next_year':     next_month.year,
        'next_month':    next_month.month,
        'special_form':  special_form,
    })


@login_required
def day_detail(request, semester_id, date_str):
    """Show and mark attendance for all sessions on a specific date."""
    semester = get_object_or_404(Semester, id=semester_id, user=request.user)
    try:
        target_date = date.fromisoformat(date_str)
    except ValueError:
        return redirect('calendar_view', semester_id=semester_id)

    sessions = ClassSession.objects.filter(
        semester=semester, date=target_date
    ).select_related('subject').order_by('start_time')

    special_day = SpecialDay.objects.filter(semester=semester, date=target_date).first()

    form = AttendanceMarkForm(sessions, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        for session in sessions:
            field = f'session_{session.id}'
            new_status = form.cleaned_data.get(field)
            if new_status:
                session.status = new_status
                session.save(update_fields=['status'])
                # Update or create attendance record
                AttendanceRecord.objects.update_or_create(
                    session=session,
                    defaults={'student': request.user, 'status': new_status}
                )
        messages.success(request, f"Attendance marked for {target_date.strftime('%d %B %Y')}. ✅")
        return redirect('day_detail', semester_id=semester_id, date_str=date_str)

    return render(request, 'attendance/calendar/day_detail.html', {
        'semester':    semester,
        'date':        target_date,
        'sessions':    sessions,
        'special_day': special_day,
        'form':        form,
    })


# ═════════════════════════════════════════════════════════════════════════════
# Attendance Overview
# ═════════════════════════════════════════════════════════════════════════════

@login_required
def attendance_overview(request, semester_id):
    semester = get_object_or_404(Semester, id=semester_id, user=request.user)
    subjects = semester.subjects.all()

    subject_data = []
    for subj in subjects:
        att   = services.calculate_attendance(subj)
        risk  = services.classify_risk(att)
        bunk  = services.calculate_bunk_budget(subj, att)
        recov = services.recovery_sessions_needed(subj, att)
        future = services.get_future_sessions(subj).count()
        subject_data.append({
            'subject': subj, 'att': att, 'risk': risk,
            'bunk': bunk, 'recovery': recov, 'future': future
        })

    return render(request, 'attendance/attendance/overview.html', {
        'semester': semester, 'subject_data': subject_data
    })


# ═════════════════════════════════════════════════════════════════════════════
# Bunk Budget & Risk
# ═════════════════════════════════════════════════════════════════════════════

@login_required
def bunk_budget(request, semester_id):
    semester = get_object_or_404(Semester, id=semester_id, user=request.user)
    subjects = semester.subjects.all()
    today    = timezone.localdate()

    subject_data = []
    for subj in subjects:
        att    = services.calculate_attendance(subj)
        risk   = services.classify_risk(att)
        bunk   = services.calculate_bunk_budget(subj, att)
        recov  = services.recovery_sessions_needed(subj, att)
        future = services.get_future_sessions(subj, from_date=today)
        subject_data.append({
            'subject': subj, 'att': att, 'risk': risk,
            'bunk': bunk, 'recovery': recov,
            'future_count': future.count(),
        })

    return render(request, 'attendance/bunk/budget.html', {
        'semester': semester, 'subject_data': subject_data
    })


# ═════════════════════════════════════════════════════════════════════════════
# What-if Simulator
# ═════════════════════════════════════════════════════════════════════════════

@login_required
def simulator(request, semester_id):
    semester = get_object_or_404(Semester, id=semester_id, user=request.user)
    today    = timezone.localdate()

    future_sessions = ClassSession.objects.filter(
        semester=semester,
        date__gte=today,
        status='scheduled'
    ).select_related('subject').order_by('date', 'start_time')

    simulation_result = None

    if request.method == 'POST':
        selected_ids = request.POST.getlist('session_ids')
        if selected_ids:
            simulation_result = services.simulate_absences([int(i) for i in selected_ids])
            # Save as a snapshot for reference
            label = request.POST.get('label', f"Simulation on {today}")
            SimulationSnapshot.objects.create(
                user=request.user,
                semester=semester,
                label=label,
                result_json=simulation_result
            )
        else:
            messages.warning(request, "Please select at least one session to simulate.")

    return render(request, 'attendance/simulator/simulator.html', {
        'semester':          semester,
        'future_sessions':   future_sessions,
        'simulation_result': simulation_result,
    })


@login_required
def simulate_date_range_view(request, semester_id):
    """AJAX endpoint: simulate absence for a date range."""
    semester = get_object_or_404(Semester, id=semester_id, user=request.user)
    if request.method == 'POST':
        data = json.loads(request.body)
        try:
            start = date.fromisoformat(data['start_date'])
            end   = date.fromisoformat(data['end_date'])
        except (KeyError, ValueError):
            return JsonResponse({'error': 'Invalid dates'}, status=400)

        result = services.simulate_date_range(semester, start, end)
        return JsonResponse({'result': result})
    return JsonResponse({'error': 'POST required'}, status=405)


# ═════════════════════════════════════════════════════════════════════════════
# Smart Bunk Optimizer
# ═════════════════════════════════════════════════════════════════════════════

@login_required
def bunk_optimizer(request, semester_id):
    semester = get_object_or_404(Semester, id=semester_id, user=request.user)
    today    = timezone.localdate()

    # Group future sessions by date
    future_sessions = ClassSession.objects.filter(
        semester=semester,
        date__gte=today,
        status='scheduled'
    ).select_related('subject').order_by('date', 'start_time')

    # Group by date
    days = {}
    for s in future_sessions:
        key = s.date
        if key not in days:
            days[key] = {'date': key, 'sessions': [], 'total_minutes': 0}
        days[key]['sessions'].append(s)
        days[key]['total_minutes'] += s.duration_minutes

    optimizer_result = None

    if request.method == 'POST':
        mode = request.POST.get('mode', 'sessions')
        if mode == 'sessions':
            selected_ids = [int(i) for i in request.POST.getlist('session_ids')]
        elif mode == 'day':
            target_date = date.fromisoformat(request.POST.get('date'))
            selected_ids = list(
                ClassSession.objects.filter(
                    semester=semester, date=target_date, status='scheduled'
                ).values_list('id', flat=True)
            )
        elif mode == 'range':
            start = date.fromisoformat(request.POST.get('start_date'))
            end   = date.fromisoformat(request.POST.get('end_date'))
            selected_ids = list(
                ClassSession.objects.filter(
                    semester=semester,
                    date__range=(start, end),
                    status='scheduled'
                ).values_list('id', flat=True)
            )
        else:
            selected_ids = []

        if selected_ids:
            sim = services.simulate_absences(selected_ids)
            selected_sessions = ClassSession.objects.filter(id__in=selected_ids).select_related('subject')
            free_minutes = sum(s.duration_minutes for s in selected_sessions)
            any_critical = any(v['projected_risk'] == 'CRITICAL' for v in sim.values())
            any_caution  = any(v['projected_risk'] == 'CAUTION'  for v in sim.values())
            overall_risk = 'HIGH' if any_critical else ('MEDIUM' if any_caution else 'LOW')

            optimizer_result = {
                'simulation':     sim,
                'selected':       list(selected_sessions),
                'free_hours':     round(free_minutes / 60, 1),
                'overall_risk':   overall_risk,
                'any_critical':   any_critical,
            }
        else:
            messages.warning(request, "No sessions found for the selected criteria.")

    return render(request, 'attendance/optimizer/optimizer.html', {
        'semester':         semester,
        'days':             list(days.values()),
        'optimizer_result': optimizer_result,
    })


# ═════════════════════════════════════════════════════════════════════════════
# Event Planner
# ═════════════════════════════════════════════════════════════════════════════

@login_required
def event_planner(request, semester_id):
    semester = get_object_or_404(Semester, id=semester_id, user=request.user)
    events   = semester.events.filter(user=request.user)
    form     = EventForm(request.POST or None)

    event_impacts = []
    if request.method == 'POST' and form.is_valid():
        event = form.save(commit=False)
        event.user     = request.user
        event.semester = semester
        event.save()

        impact = services.simulate_date_range(semester, event.start_date, event.end_date)
        free_minutes = ClassSession.objects.filter(
            semester=semester,
            date__range=(event.start_date, event.end_date),
            status='scheduled'
        ).values_list('duration_minutes', flat=True)

        messages.success(request, f"Event '{event.name}' added. Impact simulated below.")
        return render(request, 'attendance/events/planner.html', {
            'semester': semester, 'events': semester.events.filter(user=request.user),
            'form': EventForm(),
            'new_event': event,
            'impact': impact,
            'free_hours': round(sum(free_minutes) / 60, 1),
        })

    # Show impact of each existing event
    for ev in events:
        imp = services.simulate_date_range(semester, ev.start_date, ev.end_date)
        event_impacts.append({'event': ev, 'impact': imp})

    return render(request, 'attendance/events/planner.html', {
        'semester': semester, 'events': events,
        'event_impacts': event_impacts, 'form': form
    })


@login_required
def event_delete(request, event_id):
    event = get_object_or_404(Event, id=event_id, user=request.user)
    semester_id = event.semester.id
    if request.method == 'POST':
        event.delete()
        messages.warning(request, f"Event '{event.name}' removed.")
    return redirect('event_planner', semester_id=semester_id)


# ═════════════════════════════════════════════════════════════════════════════
# Bridge Day Planner
# ═════════════════════════════════════════════════════════════════════════════

@login_required
def bridge_days(request, semester_id):
    semester = get_object_or_404(Semester, id=semester_id, user=request.user)
    bridges  = services.find_bridge_days(semester)
    return render(request, 'attendance/optimizer/bridge_days.html', {
        'semester': semester, 'bridges': bridges
    })


# ═════════════════════════════════════════════════════════════════════════════
# Analytics & Charts (Pandas + Matplotlib)
# ═════════════════════════════════════════════════════════════════════════════

def _fig_to_base64(fig):
    """Convert a Matplotlib figure to a base64 PNG string for embedding in HTML."""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=120, facecolor=fig.get_facecolor())
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return img_b64


@login_required
def analytics(request, semester_id):
    semester = get_object_or_404(Semester, id=semester_id, user=request.user)
    subjects = list(semester.subjects.all())

    # ── Build Pandas DataFrame from attendance data ──────────────────────────
    rows = []
    for subj in subjects:
        att = services.calculate_attendance(subj)
        rows.append({
            'Subject':    subj.name,
            'Conducted':  att['conducted'],
            'Attended':   att['attended'],
            'Absent':     att['absent'],
            'Percentage': att['percentage'],
            'Target':     att['min_required'],
            'Risk':       services.classify_risk(att),
        })
    df = pd.DataFrame(rows)

    charts = {}

    if not df.empty:
        DARK_BG  = '#1a1a2e'
        GRID_CLR = '#2d2d4e'
        TEXT_CLR = '#e2e8f0'
        SAFE_CLR = '#22c55e'
        CAUT_CLR = '#f59e0b'
        CRIT_CLR = '#ef4444'
        ACCENT   = '#818cf8'

        def risk_color(risk):
            return {
                'SAFE':     SAFE_CLR,
                'CAUTION':  CAUT_CLR,
                'CRITICAL': CRIT_CLR,
            }.get(risk, ACCENT)

        bar_colors = [risk_color(r) for r in df['Risk']]

        # ── Chart 1: Subject-wise attendance bar chart ────────────────────
        fig, ax = plt.subplots(figsize=(9, 4), facecolor=DARK_BG)
        ax.set_facecolor(DARK_BG)
        bars = ax.bar(df['Subject'], df['Percentage'], color=bar_colors, width=0.55, zorder=3)
        ax.axhline(y=semester.min_attendance, color=CRIT_CLR, linestyle='--', linewidth=1.5,
                   label=f'Minimum ({semester.min_attendance}%)', zorder=4)
        ax.axhline(y=semester.effective_target, color=CAUT_CLR, linestyle=':', linewidth=1.5,
                   label=f'Target ({semester.effective_target}%)', zorder=4)
        ax.set_ylim(0, 105)
        ax.set_ylabel('Attendance %', color=TEXT_CLR, fontsize=10)
        ax.set_title('Subject-wise Attendance', color=TEXT_CLR, fontsize=13, pad=12)
        ax.tick_params(colors=TEXT_CLR, labelsize=9)
        ax.set_xticks(range(len(df)))
        ax.set_xticklabels(df['Subject'], rotation=20, ha='right', color=TEXT_CLR)
        for spine in ax.spines.values():
            spine.set_edgecolor(GRID_CLR)
        ax.yaxis.grid(True, color=GRID_CLR, linestyle='-', linewidth=0.5, zorder=0)
        ax.legend(facecolor=DARK_BG, labelcolor=TEXT_CLR, fontsize=8)
        for bar, pct in zip(bars, df['Percentage']):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5,
                    f'{pct:.1f}%', ha='center', va='bottom', color=TEXT_CLR, fontsize=8)
        charts['bar'] = _fig_to_base64(fig)

        # ── Chart 2: Present vs Absent stacked bar ────────────────────────
        fig, ax = plt.subplots(figsize=(9, 4), facecolor=DARK_BG)
        ax.set_facecolor(DARK_BG)
        x = range(len(df))
        ax.bar(x, df['Attended'], label='Present', color=SAFE_CLR, width=0.5, zorder=3)
        ax.bar(x, df['Absent'],   label='Absent',  color=CRIT_CLR, width=0.5, bottom=df['Attended'], zorder=3)
        ax.set_xticks(list(x))
        ax.set_xticklabels(df['Subject'], rotation=20, ha='right', color=TEXT_CLR, fontsize=9)
        ax.set_ylabel('Sessions', color=TEXT_CLR, fontsize=10)
        ax.set_title('Present vs Absent Sessions', color=TEXT_CLR, fontsize=13, pad=12)
        ax.tick_params(colors=TEXT_CLR)
        for spine in ax.spines.values():
            spine.set_edgecolor(GRID_CLR)
        ax.yaxis.grid(True, color=GRID_CLR, linestyle='-', linewidth=0.5, zorder=0)
        ax.legend(facecolor=DARK_BG, labelcolor=TEXT_CLR, fontsize=9)
        charts['stacked'] = _fig_to_base64(fig)

        # ── Chart 3: Attendance vs Target horizontal bars ─────────────────
        fig, ax = plt.subplots(figsize=(8, max(3, len(df) * 0.7)), facecolor=DARK_BG)
        ax.set_facecolor(DARK_BG)
        y_pos = range(len(df))
        ax.barh(list(y_pos), df['Percentage'], color=bar_colors, height=0.5, zorder=3)
        ax.barh(list(y_pos), df['Target'], color='none',
                edgecolor=CRIT_CLR, linewidth=1.5, height=0.5, linestyle='--', zorder=4)
        ax.set_yticks(list(y_pos))
        ax.set_yticklabels(df['Subject'], color=TEXT_CLR, fontsize=9)
        ax.set_xlabel('Attendance %', color=TEXT_CLR, fontsize=10)
        ax.set_title('Attendance vs Target', color=TEXT_CLR, fontsize=13, pad=12)
        ax.set_xlim(0, 110)
        ax.tick_params(colors=TEXT_CLR)
        for spine in ax.spines.values():
            spine.set_edgecolor(GRID_CLR)
        ax.xaxis.grid(True, color=GRID_CLR, linestyle='-', linewidth=0.5, zorder=0)
        charts['horizontal'] = _fig_to_base64(fig)

        # ── Chart 4: Attendance trend over time (using Pandas groupby) ────
        all_sessions = ClassSession.objects.filter(
            semester=semester,
            status__in=['present', 'absent']
        ).values('date', 'status', 'attendance_weight').order_by('date')

        if all_sessions:
            trend_df = pd.DataFrame(list(all_sessions))
            trend_df['date']      = pd.to_datetime(trend_df['date'])
            trend_df['attended']  = trend_df.apply(
                lambda r: r['attendance_weight'] if r['status'] == 'present' else 0, axis=1)
            trend_df['conducted'] = trend_df['attendance_weight']

            weekly = trend_df.groupby(pd.Grouper(key='date', freq='W')).agg(
                attended=('attended', 'sum'),
                conducted=('conducted', 'sum')
            ).reset_index()
            weekly = weekly[weekly['conducted'] > 0]
            weekly['cum_attended']  = weekly['attended'].cumsum()
            weekly['cum_conducted'] = weekly['conducted'].cumsum()
            weekly['cum_pct']       = weekly['cum_attended'] / weekly['cum_conducted'] * 100

            fig, ax = plt.subplots(figsize=(10, 4), facecolor=DARK_BG)
            ax.set_facecolor(DARK_BG)
            ax.plot(weekly['date'], weekly['cum_pct'], color=ACCENT, linewidth=2, marker='o',
                    markersize=4, zorder=3, label='Overall Attendance %')
            ax.axhline(y=semester.min_attendance, color=CRIT_CLR, linestyle='--',
                       linewidth=1.5, label=f'Minimum ({semester.min_attendance}%)')
            ax.axhline(y=semester.effective_target, color=CAUT_CLR, linestyle=':',
                       linewidth=1.5, label=f'Target ({semester.effective_target}%)')
            ax.fill_between(weekly['date'], weekly['cum_pct'],
                            alpha=0.15, color=ACCENT)
            ax.set_ylim(0, 105)
            ax.set_ylabel('Cumulative Attendance %', color=TEXT_CLR, fontsize=10)
            ax.set_title('Attendance Trend Over Time', color=TEXT_CLR, fontsize=13, pad=12)
            ax.tick_params(colors=TEXT_CLR, labelsize=8)
            for spine in ax.spines.values():
                spine.set_edgecolor(GRID_CLR)
            ax.yaxis.grid(True, color=GRID_CLR, linestyle='-', linewidth=0.5)
            ax.legend(facecolor=DARK_BG, labelcolor=TEXT_CLR, fontsize=8)
            plt.xticks(rotation=30)
            charts['trend'] = _fig_to_base64(fig)

    return render(request, 'attendance/analytics/analytics.html', {
        'semester': semester,
        'df_html':  df.to_html(classes='table table-dark table-sm', index=False, border=0) if not df.empty else '',
        'charts':   charts,
    })


# ═════════════════════════════════════════════════════════════════════════════
# Special Days Management
# ═════════════════════════════════════════════════════════════════════════════

@login_required
def special_days(request, semester_id):
    semester = get_object_or_404(Semester, id=semester_id, user=request.user)
    special  = semester.special_days.order_by('date')
    form     = SpecialDayForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        sp = form.save(commit=False)
        sp.semester = semester
        sp.save()
        services.apply_special_day(sp)
        messages.success(request, f"'{sp.name}' added.")
        return redirect('special_days', semester_id=semester_id)
    return render(request, 'attendance/calendar/special_days.html', {
        'semester': semester, 'special': special, 'form': form
    })


@login_required
def special_day_delete(request, day_id):
    sp = get_object_or_404(SpecialDay, id=day_id, semester__user=request.user)
    semester_id = sp.semester.id
    if request.method == 'POST':
        sp.delete()
        messages.warning(request, f"'{sp.name}' removed.")
    return redirect('special_days', semester_id=semester_id)


# ═════════════════════════════════════════════════════════════════════════════
# AJAX helpers
# ═════════════════════════════════════════════════════════════════════════════

@login_required
def api_session_status(request, session_id):
    """AJAX: update a single session's attendance status."""
    session = get_object_or_404(ClassSession, id=session_id, semester__user=request.user)
    if request.method == 'POST':
        data       = json.loads(request.body)
        new_status = data.get('status')
        valid      = [s[0] for s in ClassSession.STATUS_CHOICES]
        if new_status not in valid:
            return JsonResponse({'error': 'Invalid status'}, status=400)
        session.status = new_status
        session.save(update_fields=['status'])
        AttendanceRecord.objects.update_or_create(
            session=session,
            defaults={'student': request.user, 'status': new_status}
        )
        return JsonResponse({'ok': True, 'status': new_status})
    return JsonResponse({'error': 'POST required'}, status=405)
