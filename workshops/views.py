from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponseForbidden

from .models import Workshop, WorkshopSession, WorkshopFeedback, WorkshopResource


from dashboard.models import Event

@login_required
def workshop_list(request):
    current_event = Event.get_current()
    
    # Check if admin is trying to view a specific supervisor's dashboard
    target_supervisor_id = request.GET.get('supervisor_id')
    viewing_as_supervisor = None
    event_filter = (request.GET.get('event') or '').strip().lower()
    
    if target_supervisor_id and request.user.is_admin():
        workshops = Workshop.objects.filter(supervisor_id=target_supervisor_id)
        from users.models import User
        viewing_as_supervisor = get_object_or_404(User, pk=target_supervisor_id)
    elif request.user.is_admin():
        workshops = Workshop.objects.all()
        if event_filter == 'current' and current_event:
            workshops = workshops.filter(event=current_event)
        elif event_filter.isdigit():
            workshops = workshops.filter(event_id=int(event_filter))
    elif request.user.is_supervisor():
        # المشرف يرى الورش المسندة إليه فقط
        workshops = Workshop.objects.filter(supervisor=request.user)
        # إذا كان هناك فعالية نشطة، نفضل عرض ورش هذه الفعالية إذا وجدت
        if current_event and workshops.filter(event=current_event).exists():
            workshops = workshops.filter(event=current_event)
    else:
        # أي مستخدم آخر (متطوع مثلاً) يرى ورش الفعالية الحالية
        workshops = Workshop.objects.filter(event=current_event)

    workshops = workshops.select_related('supervisor').prefetch_related('sessions__group')
    
    total_workshops = workshops.count()
    active_workshops = workshops.filter(status='active').count()
    upcoming_workshops = workshops.filter(status='upcoming').count()
    finished_workshops = workshops.filter(status='finished').count()
    total_sessions = WorkshopSession.objects.filter(workshop__in=workshops).count()
    
    # Get feedback for the workshops
    feedbacks = WorkshopFeedback.objects.filter(workshop__in=workshops).select_related('student', 'workshop').order_by('-created_at')
    
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
            'feedbacks': feedbacks,
            'viewing_as_supervisor': viewing_as_supervisor,
        },
    )


@login_required
def workshop_resource_manage(request, workshop_id):
    workshop = get_object_or_404(Workshop, pk=workshop_id)
    
    # التأكد أن المستخدم هو المشرف على هذه الورشة أو أدمن
    if not (request.user.is_superuser or request.user == workshop.supervisor or (hasattr(request.user, 'role') and request.user.role == 'admin')):
        return HttpResponseForbidden("ليس لديك صلاحية لإدارة مصادر هذه الورشة.")

    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add':
            title = request.POST.get('title')
            resource_type = request.POST.get('resource_type')
            url = request.POST.get('url')
            file = request.FILES.get('file')
            description = request.POST.get('description', '')
            
            if title and (url or file):
                WorkshopResource.objects.create(
                    workshop=workshop,
                    title=title,
                    resource_type=resource_type,
                    url=url,
                    file=file,
                    description=description
                )
                messages.success(request, f'تم إضافة المصدر "{title}" بنجاح.')
            else:
                messages.error(request, 'يرجى إدخال رابط أو رفع ملف.')
        
        elif action == 'delete':
            resource_id = request.POST.get('resource_id')
            resource = get_object_or_404(WorkshopResource, pk=resource_id, workshop=workshop)
            resource.delete()
            messages.success(request, 'تم حذف المصدر بنجاح.')

        return redirect('workshops:resource_manage', workshop_id=workshop.id)

    resources = workshop.resources.all()
    return render(request, 'workshops/resource_manage.html', {
        'workshop': workshop,
        'resources': resources,
    })


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
