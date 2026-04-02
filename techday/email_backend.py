import ssl
import os
from django.core.mail.backends.smtp import EmailBackend

class CustomEmailBackend(EmailBackend):
    def open(self):
        if self.connection:
            return False
        
        try:
            if os.environ.get('SMTP_INSECURE_SSL', '').strip() == '1':
                self.ssl_context = ssl._create_unverified_context()
            return super().open()
        except Exception:
            if not self.fail_silently:
                raise
            return False
