import ssl
from django.core.mail.backends.smtp import EmailBackend

class CustomEmailBackend(EmailBackend):
    def open(self):
        if self.connection:
            return False
        
        try:
            # تجاوز التحقق من الشهادة (SSL Certificate Verification)
            # مفيد في البيئات التي تعاني من مشاكل في CA bundle
            self.ssl_context = ssl._create_unverified_context()
            return super().open()
        except Exception:
            if not self.fail_silently:
                raise
            return False
