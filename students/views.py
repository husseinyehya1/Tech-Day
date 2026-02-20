from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from workshops.models import WorkshopSession

from .models import Student


@login_required
def student_list(request):
    students = Student.objects.select_related('group').all()
    return render(request, 'students/list.html', {'students': students})


@login_required
def student_detail(request, pk):
    student = get_object_or_404(Student.objects.select_related('group'), pk=pk)
    now = timezone.localtime()
    current_session = None
    next_session = None
    if student.group:
        current_session = (
            WorkshopSession.objects.filter(
                group=student.group,
                start_time__lte=now.time(),
                end_time__gte=now.time(),
            )
            .select_related('workshop')
            .first()
        )
        next_session = (
            WorkshopSession.objects.filter(group=student.group, start_time__gt=now.time())
            .select_related('workshop')
            .order_by('start_time')
            .first()
        )
    context = {
        'student': student,
        'current_session': current_session,
        'next_session': next_session,
    }
    return render(request, 'students/detail.html', context)
