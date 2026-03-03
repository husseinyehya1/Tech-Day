from students.models import Badge, StudentBadge
from attendance.models import Attendance
from workshops.models import WorkshopSession

def check_and_award_badges(student):
    """
    Check if a student is eligible for any new badges and award them.
    Returns a list of newly awarded badges.
    """
    newly_awarded = []
    
    # 1. Check Points Badges
    points_badges = Badge.objects.filter(criteria_type=Badge.CriteriaType.POINTS)
    for badge in points_badges:
        if student.points >= badge.criteria_value:
            # Award badge if student doesn't have it yet
            sb, created = StudentBadge.objects.get_or_create(
                student=student,
                badge=badge
            )
            if created:
                newly_awarded.append(badge)
    
    # 2. Check Attendance Rate Badges
    attendance_badges = Badge.objects.filter(criteria_type=Badge.CriteriaType.ATTENDANCE_RATE)
    if attendance_badges.exists():
        # Get total number of sessions for the student's group
        if student.group:
            total_sessions = WorkshopSession.objects.filter(group=student.group).count()
            if total_sessions > 0:
                # Count student's attendance for these sessions
                attended_count = Attendance.objects.filter(
                    student=student,
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
