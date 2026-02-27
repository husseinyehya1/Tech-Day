from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages

from .models import Workshop, WorkshopSession, WorkshopFeedback


@login_required
def workshop_list(request):
    qs = Workshop.objects.select_related('supervisor').prefetch_related('sessions__group')
    
    # Check if admin is trying to view a specific supervisor's dashboard
    target_supervisor_id = request.GET.get('supervisor_id')
    viewing_as_supervisor = None
    
    if target_supervisor_id and request.user.is_admin():
        workshops = qs.filter(supervisor_id=target_supervisor_id)
        from users.models import User
        viewing_as_supervisor = get_object_or_404(User, pk=target_supervisor_id)
    elif hasattr(request.user, 'is_supervisor') and request.user.is_supervisor():
        workshops = qs.filter(supervisor=request.user)
    else:
        # Default for admin or others is to see everything
        workshops = qs

    total_workshops = workshops.count()
    active_workshops = workshops.filter(status='active').count()
    upcoming_workshops = workshops.filter(status='upcoming').count()
    finished_workshops = workshops.filter(status='finished').count()
    total_sessions = WorkshopSession.objects.filter(workshop__in=workshops).count()
    
    return render(
        request,
        'workshops/list.html',
        {
            'workshops': workshops,
            'total_workshops': total_workshops,
            'active_workshops': active_workshops,
            'upcoming_workshops': upcoming_workshops,
            'finished_workshops': finished_workshops,
            'total_sessions': total_sessions,
            'viewing_as_supervisor': viewing_as_supervisor,
        },
    )


@login_required
def student_submit_feedback(request):
    if not hasattr(request.user, 'student_profile'):
        return redirect('users:login')
    
    if request.method == 'POST':
        workshop_id = request.POST.get('workshop_id')
        rating = int(request.POST.get('rating', 0))
        comment = (request.POST.get('comment') or '').strip()
        
        workshop = get_object_or_404(Workshop, pk=workshop_id)
        student = request.user.student_profile
        
        if 1 <= rating <= 5:
            feedback, created = WorkshopFeedback.objects.update_or_create(
                student=student,
                workshop=workshop,
                defaults={'rating': rating, 'comment': comment}
            )
            if created:
                messages.success(request, f'شكراً لتقييمك لورشة "{workshop.title}".')
            else:
                messages.success(request, f'تم تحديث تقييمك لورشة "{workshop.title}".')
        else:
            messages.error(request, 'يرجى اختيار تقييم صحيح من 1 إلى 5 نجوم.')
            
    return redirect('students:detail', pk=request.user.student_profile.pk)
