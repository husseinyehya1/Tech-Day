from students.models import Badge, StudentBadge, StudentEventStats
from attendance.models import Attendance
from workshops.models import WorkshopSession
from dashboard.models import Event

def check_and_award_badges(student, event=None):
    """
    Check if a student is eligible for any new badges and award them.
    Returns a list of newly awarded badges.
    """
    if event is None:
        event = Event.get_current()
        
    if not event:
        return []
        
    newly_awarded = []
    
    # الحصول على نقاط الطالب في هذه الفعالية
    stats = StudentEventStats.objects.filter(student=student, event=event).first()
    if not stats:
        stats = StudentEventStats.objects.create(student=student, event=event)
    event_points = stats.points
    
    # 1. Check Points Badges (Filtered by event)
    points_badges = Badge.objects.filter(event=event, criteria_type=Badge.CriteriaType.POINTS)
    for badge in points_badges:
        if event_points >= badge.criteria_value:
            # Award badge if student doesn't have it yet
            sb, created = StudentBadge.objects.get_or_create(
                student=student,
                badge=badge
            )
            if created:
                newly_awarded.append(badge)
    
    # 2. Check Attendance Rate Badges (Filtered by event)
    attendance_badges = Badge.objects.filter(event=event, criteria_type=Badge.CriteriaType.ATTENDANCE_RATE)
    if attendance_badges.exists():
        # Get total number of sessions for the student's group IN THIS EVENT
        if student.group and student.group.event == event:
            total_sessions = WorkshopSession.objects.filter(group=student.group).count()
            if total_sessions > 0:
                # Count student's attendance for these sessions
                attended_count = Attendance.objects.filter(
                    student=student,
                    session__group=student.group,
                    status=Attendance.Status.PRESENT
                ).count()
                
                attendance_rate = (attended_count / total_sessions) * 100
                
                for badge in attendance_badges:
                    if attendance_rate >= badge.criteria_value:
                        sb, created = StudentBadge.objects.get_or_create(
                            student=student,
                            badge=badge
                        )
                        if created:
                            newly_awarded.append(badge)
                            
    return newly_awarded
