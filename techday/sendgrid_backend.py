import json
import os
import urllib.request

from django.core.mail.backends.base import BaseEmailBackend


class SendGridEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        api_key = os.environ.get('SENDGRID_API_KEY', '').strip()
        if not api_key:
            raise RuntimeError('SENDGRID_API_KEY is not set')

        timeout = int(os.environ.get('SENDGRID_TIMEOUT', '20') or 20)
        sent = 0
        for message in email_messages:
            payload = _build_sendgrid_payload(message)
            req = urllib.request.Request(
                url='https://api.sendgrid.com/v3/mail/send',
                data=json.dumps(payload).encode('utf-8'),
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                },
                method='POST',
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    if 200 <= resp.status < 300:
                        sent += 1
                    else:
                        raise RuntimeError(f'SendGrid HTTP {resp.status}')
            except Exception:
                if not self.fail_silently:
                    raise
        return sent


def _build_sendgrid_payload(message):
    from_email = (message.from_email or os.environ.get('SENDGRID_FROM_EMAIL') or '').strip()
    if not from_email:
        from_email = os.environ.get('TECHDAY_EMAIL_USER', 'noreply@edutech-egy.com')

    to_list = [{'email': addr} for addr in (message.to or [])]
    cc_list = [{'email': addr} for addr in (getattr(message, 'cc', None) or [])]
    bcc_list = [{'email': addr} for addr in (getattr(message, 'bcc', None) or [])]

    html_body = None
    if hasattr(message, 'alternatives'):
        for alt, mimetype in message.alternatives:
            if mimetype == 'text/html':
                html_body = alt
                break

    content = [{'type': 'text/plain', 'value': message.body or ''}]
    if html_body:
        content.append({'type': 'text/html', 'value': html_body})

    personalization = {'to': to_list}
    if cc_list:
        personalization['cc'] = cc_list
    if bcc_list:
        personalization['bcc'] = bcc_list

    return {
        'from': {'email': from_email},
        'subject': message.subject or '',
        'personalizations': [personalization],
        'content': content,
    }

