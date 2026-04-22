from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import models
from students.models import Student, StudentRegistration, Badge, StudentBadge, StudentWorkshopNote
from groups.models import Group
from workshops.models import Workshop, WorkshopSession, WorkshopFeedback, WorkshopResource
from dashboard.models import (
    Event, Notification, SOSRequest, StudentSupportRequest, 
    VolunteerNote, FailedEmail, BroadcastMessage, VIPInvite, 
    StudentViolation, AdminLog
)
from attendance.models import Attendance

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'role', 'first_name', 'last_name')

class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = '__all__'

class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = '__all__'

class BadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = '__all__'

class WorkshopResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkshopResource
        fields = '__all__'

class WorkshopSerializer(serializers.ModelSerializer):
    resources = WorkshopResourceSerializer(many=True, read_only=True)
    supervisor_name = serializers.ReadOnlyField(source='supervisor.username')
    
    class Meta:
        model = Workshop
        fields = '__all__'

class WorkshopSessionSerializer(serializers.ModelSerializer):
    workshop_details = WorkshopSerializer(source='workshop', read_only=True)
    attendance_status = serializers.SerializerMethodField()
    feedback_status = serializers.SerializerMethodField()
    feedback_rating = serializers.SerializerMethodField()
    feedback_comment = serializers.SerializerMethodField()
    note_content = serializers.SerializerMethodField()

    class Meta:
        model = WorkshopSession
        fields = '__all__'

    def get_attendance_status(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            try:
                student = Student.objects.get(user=request.user)
                # Correct field is 'session'
                attendance = Attendance.objects.filter(student=student, session=obj).first()
                if attendance:
                    return attendance.status
                return 'waiting'
            except Student.DoesNotExist:
                pass
        return 'unknown'

    def get_feedback_status(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            try:
                student = Student.objects.get(user=request.user)
                return WorkshopFeedback.objects.filter(student=student, workshop=obj.workshop).exists()
            except Student.DoesNotExist:
                pass
        return False

    def get_feedback_rating(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            try:
                student = Student.objects.get(user=request.user)
                feedback = WorkshopFeedback.objects.filter(student=student, workshop=obj.workshop).first()
                return feedback.rating if feedback else None
            except Student.DoesNotExist:
                pass
        return None

    def get_feedback_comment(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            try:
                student = Student.objects.get(user=request.user)
                feedback = WorkshopFeedback.objects.filter(student=student, workshop=obj.workshop).first()
                return feedback.comment if feedback else None
            except Student.DoesNotExist:
                pass
        return None

    def get_note_content(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            try:
                student = Student.objects.get(user=request.user)
                note = StudentWorkshopNote.objects.filter(student=student, workshop=obj.workshop).first()
                return note.content if note else None
            except Student.DoesNotExist:
                pass
        return None

class StudentSerializer(serializers.ModelSerializer):
    group_details = GroupSerializer(source='group', read_only=True)
    badges = serializers.SerializerMethodField()
    stats = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = '__all__'

    def get_badges(self, obj):
        student_badges = StudentBadge.objects.filter(student=obj).select_related('badge')
        return BadgeSerializer([sb.badge for sb in student_badges], many=True).data

    def get_stats(self, obj):
        event = Event.get_current()
        # Personal rank
        all_students = Student.objects.filter(registrations__event=event).order_by('-points', 'name')
        rank = 1
        for s in all_students:
            if s.id == obj.id:
                break
            rank += 1

        # Attendance
        total_sessions = WorkshopSession.objects.filter(group=obj.group).count()
        attended_count = Attendance.objects.filter(student=obj).count()
        
        # Group rank
        group_rank = 1
        if obj.group:
            all_groups = Group.objects.filter(event=event).order_by('-points')
            for g in all_groups:
                if g.id == obj.group.id:
                    break
                group_rank += 1

        return {
            'rank': rank,
            'attendance_rate': round((attended_count / total_sessions * 100), 1) if total_sessions > 0 else 0,
            'attended_count': attended_count,
            'total_sessions': total_sessions,
            'group_rank': group_rank,
            'group_total_points': obj.group.points if obj.group else 0,
            'is_eligible_for_certificate': obj.checked_in and not obj.is_certificate_banned
        }

class StudentRegistrationSerializer(serializers.ModelSerializer):
    student_details = serializers.SerializerMethodField()

    class Meta:
        model = StudentRegistration
        fields = '__all__'

    def get_student_details(self, obj):
        if obj.student:
            return {
                'id': obj.student.id,
                'student_id': obj.student.student_id,
                'name': obj.student.name,
                'group_code': obj.student.group.code if obj.student.group else None
            }
        return None

class AttendanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attendance
        fields = '__all__'

class WorkshopFeedbackSerializer(serializers.ModelSerializer):
    workshop_title = serializers.ReadOnlyField(source='workshop.title')

    class Meta:
        model = WorkshopFeedback
        fields = '__all__'

class StudentWorkshopNoteSerializer(serializers.ModelSerializer):
    workshop_title = serializers.ReadOnlyField(source='workshop.title')
    
    class Meta:
        model = StudentWorkshopNote
        fields = '__all__'

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'

class SOSRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = SOSRequest
        fields = '__all__'

class StudentSupportRequestSerializer(serializers.ModelSerializer):
    student_name = serializers.ReadOnlyField(source='student.name')
    student_id_code = serializers.ReadOnlyField(source='student.student_id')

    class Meta:
        model = StudentSupportRequest
        fields = '__all__'

class VolunteerNoteSerializer(serializers.ModelSerializer):
    author_name = serializers.ReadOnlyField(source='author.username')
    
    class Meta:
        model = VolunteerNote
        fields = '__all__'

class FailedEmailSerializer(serializers.ModelSerializer):
    class Meta:
        model = FailedEmail
        fields = '__all__'

class VIPInviteSerializer(serializers.ModelSerializer):
    class Meta:
        model = VIPInvite
        fields = '__all__'

class StudentViolationSerializer(serializers.ModelSerializer):
    student_name = serializers.ReadOnlyField(source='student.name')
    student_id_code = serializers.ReadOnlyField(source='student.student_id')
    
    class Meta:
        model = StudentViolation
        fields = '__all__'

class AdminLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminLog
        fields = '__all__'
