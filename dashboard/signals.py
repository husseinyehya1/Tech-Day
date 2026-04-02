from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from fcm_django.models import FCMDevice
from .models import StudentSupportRequest, Notification

User = get_user_model()

@receiver(post_save, sender=StudentSupportRequest)
def create_support_reply_notification(sender, instance, created, **kwargs):
    if not created and instance.admin_reply and instance.status in ['solved', 'in_progress']:
        # Check if a notification for this reply already exists to avoid duplicates
        if not Notification.objects.filter(target_user=instance.student.user, related_support_request=instance).exists():
            Notification.objects.create(
                target_user=instance.student.user,
                title='تم الرد على طلب الدعم الخاص بك',
                body=f'تم الرد على طلبك بخصوص "{instance.subject}".',
                related_support_request=instance
            )
            
            # Send push notification
            devices = FCMDevice.objects.filter(user=instance.student.user, active=True)
            for device in devices:
                device.send_message(
                    title="تم الرد على طلبك",
                    body=f'"{instance.subject}"'
                )
