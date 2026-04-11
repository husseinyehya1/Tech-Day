import ssl
import os
from django.core.mail.backends.smtp import EmailBackend

try:
    import certifi
except ImportError:
    certifi = None

class CustomEmailBackend(EmailBackend):
    def open(self):
        if self.connection:
            return False
        
        try:
            # التحقق مما إذا كان المستخدم يطلب تجاوز SSL
            if os.environ.get('SMTP_INSECURE_SSL', '').strip() == '1':
                self.ssl_context = ssl._create_unverified_context()
            else:
                # محاولة إنشاء سياق SSL آمن باستخدام certifi إذا كان متاحاً
                # هذا يحل مشاكل SSL على ويندوز عندما تكون شهادات النظام قديمة
                if certifi:
                    self.ssl_context = ssl.create_default_context(cafile=certifi.where())
                else:
                    self.ssl_context = ssl.create_default_context()
                
                # إضافة خيارات إضافية للمرونة
                # بعض السيرفرات القديمة أو مشاكل الشهادات تتطلب خيارات محددة
                # self.ssl_context.check_hostname = False # يمكن تفعيله إذا كانت المشكلة في الهوست
            
            return super().open()
        except Exception:
            if not self.fail_silently:
                raise
            return False
