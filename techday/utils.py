import threading
from django.conf import settings
from django.core.mail import EmailMultiAlternatives

def get_styled_email_html(subject, preview_text, title, main_text, content_blocks_html="", footer_extra_html=""):
    return """
<!DOCTYPE html>
<html lang="ar">
  <head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <meta name="color-scheme" content="dark light">
    <title>{subject}</title>
    <style>
      @media (prefers-color-scheme: light) {{
        .td-email-body {{ background-color:#f3f4f6 !important; color:#0f172a !important; }}
        .td-email-card {{ background-color:#ffffff !important; border-color:#e5e7eb !important; }}
        .td-email-title {{ color:#0f172a !important; }}
        .td-email-text-main {{ color:#111827 !important; }}
        .td-email-text-muted {{ color:#4b5563 !important; }}
        .td-email-box {{ background-color:#f8fafc !important; border-color:#e2e8f0 !important; }}
        .td-group-badge {{ color:#0f172a !important; border-color:rgba(15,23,42,0.1) !important; background-color:rgba(15,23,42,0.05) !important; }}
      }}
    </style>
  </head>
  <body class="td-email-body" style="margin:0;padding:0;background-color:#0f172a;direction:rtl;text-align:right;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
    <div style="display:none !important;visibility:hidden;mso-hide:all;font-size:1px;line-height:1px;color:#0f172a;max-height:0;max-width:0;opacity:0;overflow:hidden;">
      {preview_text}
    </div>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td align="center" style="padding:24px 16px;">
          <table role="presentation" cellpadding="0" cellspacing="0" width="100%" class="td-email-card" style="max-width:600px;background-color:#020617;border-radius:24px;border:1px solid #1e293b;box-shadow:0 20px 50px rgba(0,0,0,0.5);">
            <tr>
              <td style="padding:30px 24px 20px 24px;text-align:center;border-bottom:1px solid #1e293b;">
                <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 auto 15px auto;text-align:center;">
                  <tr>
                    <td align="center">
                      <table role="presentation" cellpadding="0" cellspacing="0" style="border-radius:999px;background-color:#020617;border:1px solid #1e293b;margin:0 auto;">
                        <tr>
                          <td align="center" style="padding:12px 16px;">
                            <table role="presentation" cellpadding="0" cellspacing="0">
                              <tr>
                                <td align="center" style="padding:0 8px;">
                                  <img src="https://td.edutech-egy.com/static/edutech-logo.webp" alt="EduTech Egypt" style="display:block;width:48px;height:48px;border-radius:999px;background-color:#ffffff;padding:4px;">
                                </td>
                                <td width="48" style="padding-right:12px;">
                                  <img src="https://td.edutech-egy.com/static/Ministry_of_Education_(Egypt)_logo.webp" alt="وزارة التربية والتعليم المصرية" style="display:block;width:48px;height:48px;border-radius:999px;background-color:#ffffff;padding:4px;">
                                </td>
                              </tr>
                            </table>
                          </td>
                        </tr>
                      </table>
                    </td>
                  </tr>
                </table>
                <h1 class="td-email-title" style="margin:0;font-size:24px;color:#e5e7eb;font-weight:800;">{title}</h1>
                <p class="td-email-text-main" style="margin:10px 0 0;font-size:14px;color:#cbd5f5;">{main_text}</p>
              </td>
            </tr>
            <tr>
              <td style="padding:24px;">
                {content_blocks_html}
              </td>
            </tr>
            <tr>
              <td style="padding:0 24px 30px 24px;text-align:center;">
                {footer_extra_html}
                <p class="td-email-text-muted" style="margin:20px 0 0;font-size:12px;color:#64748b;">
                  تحياتنا،<br><b>EduTech Egypt System</b>
                </p>
                <table role="presentation" cellpadding="0" cellspacing="0" style="margin:15px auto 0;">
                  <tr>
                    <td align="center">
                      <a href="https://www.facebook.com/ETQal/" target="_blank" style="display:inline-block;margin:0 5px;color:#94a3b8;text-decoration:none;font-size:11px;">Facebook</a>
                      <a href="https://www.instagram.com/edutech_eg/" target="_blank" style="display:inline-block;margin:0 5px;color:#94a3b8;text-decoration:none;font-size:11px;">Instagram</a>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
""".format(
        subject=subject,
        preview_text=preview_text,
        title=title,
        main_text=main_text,
        content_blocks_html=content_blocks_html,
        footer_extra_html=footer_extra_html
    )

def send_registration_confirmation_email(student, event):
    """
    إرسال بريد إلكتروني لتأكيد التسجيل في الفعالية مع رمز الـ QR
    """
    subject = f'تأكيد حجز مكان في فعالية {event.name} – EduTech Egypt'
    whatsapp_block_html = ""
    if event.whatsapp_group_link:
        whatsapp_block_html = f"""
          <tr>
            <td style="padding:12px 0 0 0;">
              <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;border-radius:16px;background-color:#020617;border:1px solid #25d366;">
                <tr>
                  <td style="padding:14px 16px;text-align:center;">
                    <p style="margin:0 0 10px;font-size:13px;color:#e5e7eb;font-weight:600;">
                      💬 مجموعة الواتساب الرسمية
                    </p>
                    <a href="{event.whatsapp_group_link}"
                       style="display:inline-block;padding:10px 18px;border-radius:999px;background-color:#25d366;color:#ffffff;font-size:13px;font-weight:700;text-decoration:none;">
                      الانضمام لمجموعة الواتساب
                    </a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        """

    content_blocks = f"""
        <div class="td-email-box" style="padding:24px;border-radius:24px;background-color:#0f172a;border:1px solid #1e293b;text-align:center;">
          <p class="td-email-text-main" style="margin:0 0 16px;font-size:15px;color:#e5e7eb;line-height:1.6;">
            تم تأكيد حجز مكانك في فعالية <b>{event.name}</b> بنجاح. نحن بانتظار رؤيتك!
          </p>
          <div class="td-email-box" style="padding:20px;border-radius:20px;background-color:#020617;border:1px solid #1e293b;margin:20px 0;text-align:center;">
            <p style="margin:0 0 12px;font-size:14px;color:#e5e7eb;font-weight:700;">🎫 رمز الـ QR الخاص بحضورك</p>
            <img src="https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={student.student_id}" alt="QR Code" style="display:block;margin:0 auto;border-radius:12px;border:4px solid #ffffff;">
            <p style="margin:12px 0 0;font-size:12px;color:#94a3b8;">استخدم هذا الرمز لتسجيل حضورك عند بوابة الدخول.</p>
          </div>
          {whatsapp_block_html}
        </div>
    """
    
    html_body = get_styled_email_html(
        subject=subject,
        preview_text=f"تفاصيل حضورك في فعالية {event.name}",
        title="✅ تم تأكيد حجز مكانك",
        main_text=f"مرحبًا {student.name}، يسعدنا انضمامك إلينا في فعاليتنا القادمة.",
        content_blocks_html=content_blocks
    )
    
    message = EmailMultiAlternatives(
        subject,
        f"مرحباً {student.name}، تم تأكيد حجز مكانك في الفعالية بنجاح.",
        settings.DEFAULT_FROM_EMAIL,
        [student.email],
    )
    message.attach_alternative(html_body, 'text/html')
    send_email_async(message, 'إرسال تأكيد حجز مكان لطالب')

def send_email_async(message, log_prefix=None):
    def _run(msg, prefix):
        from dashboard.models import AdminLog, FailedEmail
        try:
            msg.send(fail_silently=False)
            if prefix:
                AdminLog.objects.create(action=f'{prefix} | تم إرسال بريد إلى {",".join(msg.to)}')
        except Exception as e:
            # استخراج محتوى HTML إن وجد
            html_body = ""
            if hasattr(msg, 'alternatives'):
                for alt, mimetype in msg.alternatives:
                    if mimetype == 'text/html':
                        html_body = alt
                        break
            
            # حفظ الإيميل الفاشل في قاعدة البيانات
            try:
                FailedEmail.objects.create(
                    recipient=",".join(msg.to),
                    subject=msg.subject,
                    body_text=msg.body,
                    body_html=html_body,
                    error_message=str(e)
                )
            except Exception as db_err:
                if prefix:
                    AdminLog.objects.create(action=f'{prefix} | فشل إرسال بريد وفشل حفظه في قاعدة البيانات: {e} | {db_err}')
                return

            if prefix:
                AdminLog.objects.create(action=f'{prefix} | فشل إرسال بريد إلى {",".join(msg.to)}: {e}')

    threading.Thread(target=_run, args=(message, log_prefix), daemon=True).start()
