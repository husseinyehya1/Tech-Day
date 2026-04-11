import json
import os
import requests
from django.core.mail.backends.base import BaseEmailBackend

class BrevoEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        api_key = os.environ.get('BREVO_API_KEY', '').strip()
        if not api_key:
            if not self.fail_silently:
                raise RuntimeError('BREVO_API_KEY is not set')
            return 0

        sent = 0
        for message in email_messages:
            payload = self._build_payload(message)
            try:
                response = requests.post(
                    'https://api.brevo.com/v3/smtp/email',
                    headers={
                        'api-key': api_key,
                        'content-type': 'application/json',
                        'accept': 'application/json'
                    },
                    json=payload,
                    timeout=getattr(message, 'timeout', 20)
                )
                if response.status_code in [201, 200, 202]:
                    sent += 1
                else:
                    if not self.fail_silently:
                        raise RuntimeError(f"Brevo API Error: {response.status_code} - {response.text}")
            except Exception:
                if not self.fail_silently:
                    raise
        return sent

    def _build_payload(self, message):
        from_email = (message.from_email or os.environ.get('TECHDAY_EMAIL_USER') or 'noreply@edutech-egy.com').strip()
        
        # استخراج الاسم إن وجد من الصيغة "Name <email@example.com>"
        from_name = "Tech Day System"
        if '<' in from_email and '>' in from_email:
            parts = from_email.split('<')
            from_name = parts[0].strip()
            from_email = parts[1].replace('>', '').strip()

        to_list = [{'email': addr} for addr in (message.to or [])]
        
        html_body = None
        if hasattr(message, 'alternatives'):
            for alt, mimetype in message.alternatives:
                if mimetype == 'text/html':
                    html_body = alt
                    break

        payload = {
            'sender': {'name': from_name, 'email': from_email},
            'to': to_list,
            'subject': message.subject or '',
            'textContent': message.body or '',
        }
        
        if html_body:
            payload['htmlContent'] = html_body

        # معالجة المرفقات (إن وجدت)
        if message.attachments:
            payload['attachment'] = []
            import base64
            for attachment in message.attachments:
                # attachment format: (filename, content, mimetype)
                filename, content, mimetype = attachment
                if isinstance(content, bytes):
                    encoded_content = base64.b64encode(content).decode('utf-8')
                    payload['attachment'].append({
                        'content': encoded_content,
                        'name': filename
                    })

        return payload
