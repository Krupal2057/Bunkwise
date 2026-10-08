"""BunkWise context processor — injects active semester into every template."""

from .models import Semester


def active_semester(request):
    """
    Makes `semester_id` available in every template so navbar links work.
    """
    if not request.user.is_authenticated:
        return {'semester_id': None}

    semester = Semester.objects.filter(
        user=request.user, is_active=True
    ).order_by('-start_date').first()

    return {
        'semester_id': semester.id if semester else None,
        'active_semester': semester,
    }
