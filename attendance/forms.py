"""BunkWise — Forms for all models."""

from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import Semester, Subject, TimetableEntry, ClassSession, SpecialDay, Event


# ─────────────────────────────────────────────────────────────────────────────
# Auth Forms
# ─────────────────────────────────────────────────────────────────────────────

class RegisterForm(UserCreationForm):
    email      = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=50, required=True)
    last_name  = forms.CharField(max_length=50, required=False)

    class Meta:
        model  = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
            field.widget.attrs['autocomplete'] = 'off'


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


# ─────────────────────────────────────────────────────────────────────────────
# Semester Form
# ─────────────────────────────────────────────────────────────────────────────

class SemesterForm(forms.ModelForm):
    class Meta:
        model  = Semester
        fields = ['name', 'start_date', 'end_date', 'min_attendance', 'safety_buffer', 'attendance_policy']
        widgets = {
            'start_date':    forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date':      forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'name':          forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 5th Semester'}),
            'min_attendance': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100, 'step': 0.5}),
            'safety_buffer': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 30, 'step': 0.5}),
            'attendance_policy': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_date')
        end   = cleaned.get('end_date')
        if start and end and end <= start:
            raise forms.ValidationError("End date must be after start date.")
        return cleaned


# ─────────────────────────────────────────────────────────────────────────────
# Subject Form
# ─────────────────────────────────────────────────────────────────────────────

class SubjectForm(forms.ModelForm):
    class Meta:
        model  = Subject
        fields = ['name', 'code', 'subject_type', 'has_lab', 'min_attendance', 'color', 'icon']
        widgets = {
            'name':           forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Data Structures'}),
            'code':           forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. CS301'}),
            'subject_type':   forms.Select(attrs={'class': 'form-select'}),
            'has_lab':        forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'min_attendance': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100, 'step': 0.5,
                                                       'placeholder': 'Leave blank for semester default'}),
            'color':          forms.TextInput(attrs={'type': 'color', 'class': 'form-control form-control-color'}),
            'icon':           forms.TextInput(attrs={'class': 'form-control', 'placeholder': '📚'}),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Timetable Entry Form
# ─────────────────────────────────────────────────────────────────────────────

class TimetableEntryForm(forms.ModelForm):
    class Meta:
        model  = TimetableEntry
        fields = ['subject', 'session_type', 'day_of_week', 'start_time', 'end_time', 'room']
        widgets = {
            'subject':      forms.Select(attrs={'class': 'form-select'}),
            'session_type': forms.Select(attrs={'class': 'form-select'}),
            'day_of_week':  forms.Select(attrs={'class': 'form-select'}),
            'start_time':   forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'end_time':     forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'room':         forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Room 204 / Lab 3'}),
        }

    def __init__(self, semester, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['subject'].queryset = Subject.objects.filter(semester=semester)

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_time')
        end   = cleaned.get('end_time')
        if start and end and end <= start:
            raise forms.ValidationError("End time must be after start time.")
        return cleaned


# ─────────────────────────────────────────────────────────────────────────────
# Special Day Form
# ─────────────────────────────────────────────────────────────────────────────

class SpecialDayForm(forms.ModelForm):
    class Meta:
        model  = SpecialDay
        fields = ['date', 'day_type', 'name', 'description', 'affects_all_sessions']
        widgets = {
            'date':        forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'day_type':    forms.Select(attrs={'class': 'form-select'}),
            'name':        forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Diwali'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'affects_all_sessions': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Attendance Marking Form
# ─────────────────────────────────────────────────────────────────────────────

class AttendanceMarkForm(forms.Form):
    """
    Dynamically generated form for marking attendance on a given day.
    Each session gets a status field.
    """
    STATUS_CHOICES = [
        ('present',   '✅ Present'),
        ('absent',    '❌ Absent'),
        ('cancelled', '🚫 Cancelled'),
    ]

    def __init__(self, sessions, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for session in sessions:
            field_name = f'session_{session.id}'
            current    = session.status if session.status in ('present', 'absent', 'cancelled') else 'present'
            self.fields[field_name] = forms.ChoiceField(
                choices=self.STATUS_CHOICES,
                initial=current,
                label=f"{session.start_time.strftime('%H:%M')} — {session.subject.name}",
                widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
            )


# ─────────────────────────────────────────────────────────────────────────────
# Event Form
# ─────────────────────────────────────────────────────────────────────────────

class EventForm(forms.ModelForm):
    class Meta:
        model  = Event
        fields = ['name', 'event_type', 'start_date', 'end_date', 'description']
        widgets = {
            'name':        forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Trip to Goa'}),
            'event_type':  forms.Select(attrs={'class': 'form-select'}),
            'start_date':  forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date':    forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_date')
        end   = cleaned.get('end_date')
        if start and end and end < start:
            raise forms.ValidationError("End date cannot be before start date.")
        return cleaned
