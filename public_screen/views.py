from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone

from attendance.models import Attendance
from groups.models import Group
from students.models import Student
from workshops.models import WorkshopSession


def public_screen_view(request):
    now = timezone.localtime()
    current_session = (
        WorkshopSession.objects.select_related('workshop')
        .filter(start_time__lte=now.time(), end_time__gte=now.time())
        .first()
    )
    next_session = (
        WorkshopSession.objects.select_related('workshop')
        .filter(start_time__gt=now.time())
        .order_by('start_time')
        .first()
    )
    total_present = Student.objects.filter(checked_in=True).count()
    groups = Group.objects.all()
    best_groups = Group.objects.annotate(
        present_count=Count(
            'students',
            filter=Q(students__checked_in=True),
            distinct=True,
        )
    ).filter(present_count__gt=0).order_by('-present_count')[:4]
    context = {
        'now': now,
        'current_session': current_session,
        'next_session': next_session,
        'total_present': total_present,
        'groups': groups,
        'best_groups': [{'group': g, 'present_count': g.present_count} for g in best_groups],
    }
    return render(request, 'public_screen/public_screen.html', context)
