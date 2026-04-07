"""Zentrales E-Mail-Modul: liest SMTP-Config aus EmailSettings (DB)."""
import threading
from django.core.mail import get_connection, EmailMultiAlternatives
from django.conf import settings as django_settings


def _get_cfg():
    from .models import EmailSettings
    return EmailSettings.get_solo()


def _get_connection(cfg):
    return get_connection(
        backend='django.core.mail.backends.smtp.EmailBackend',
        host=cfg.host,
        port=cfg.port,
        username=cfg.username,
        password=cfg.password,
        use_tls=cfg.use_tls,
        use_ssl=cfg.use_ssl,
    )


def _wrap_html(title, content_html, action_url=None, action_label=None):
    """Gemeinsames HTML-Layout passend zum Website-Design."""
    button = ''
    if action_url and action_label:
        button = f'''
        <div style="text-align:center;margin:32px 0 8px;">
          <a href="{action_url}"
             style="display:inline-block;padding:12px 28px;background:#14b8a6;color:#fff;
                    text-decoration:none;border-radius:6px;font-weight:600;font-size:15px;
                    letter-spacing:.02em;">
            {action_label}
          </a>
        </div>'''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#0f172a;font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0f172a;min-height:100vh;">
    <tr>
      <td align="center" style="padding:40px 16px;">

        <!-- Card -->
        <table width="100%" cellpadding="0" cellspacing="0" style="max-width:540px;">

          <!-- Header -->
          <tr>
            <td style="background:linear-gradient(135deg,#0c1a2e 0%,#0d9488 100%);
                        border-radius:10px 10px 0 0;padding:28px 36px;">
              <table cellpadding="0" cellspacing="0">
                <tr>
                  <td style="color:#14b8a6;font-size:22px;margin-right:10px;vertical-align:middle;">🦭</td>
                  <td style="padding-left:10px;vertical-align:middle;">
                    <div style="color:#f9fafb;font-size:16px;font-weight:700;letter-spacing:.02em;">
                      Podman Kube Generator
                    </div>
                    <div style="color:#5eead4;font-size:12px;margin-top:2px;">{django_settings.SITE_URL.replace("https://", "").replace("http://", "")}</div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="background:#1e293b;padding:36px;border-left:1px solid #334155;border-right:1px solid #334155;">
              <h1 style="margin:0 0 20px;font-size:20px;font-weight:700;color:#f1f5f9;">{title}</h1>
              <div style="color:#94a3b8;font-size:15px;line-height:1.7;">
                {content_html}
              </div>
              {button}
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background:#0f172a;border:1px solid #334155;border-top:none;
                        border-radius:0 0 10px 10px;padding:20px 36px;text-align:center;">
              <p style="margin:0;color:#475569;font-size:12px;line-height:1.6;">
                This email was sent automatically by
                <a href="{django_settings.SITE_URL}" style="color:#14b8a6;text-decoration:none;">
                  Podman Kube Generator
                </a>.<br>
                If you did not expect this email, you can ignore it.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>'''


def _highlight(text):
    """Text in einem Code-Style-Block."""
    return f'<code style="background:#0f172a;color:#5eead4;padding:2px 7px;border-radius:4px;font-size:14px;font-family:ui-monospace,monospace;">{text}</code>'


def _info_box(text):
    """Grauer Info-Block."""
    return f'<div style="background:#0f172a;border:1px solid #334155;border-left:3px solid #14b8a6;border-radius:6px;padding:14px 18px;margin:20px 0;color:#94a3b8;font-size:14px;">{text}</div>'


# ── Vorgefertigte E-Mail-Typen ─────────────────────────────────────

def mail_activation(username, activation_url):
    subject = 'Activate your account — Podman Kube Generator'
    body_html = f'''
        <p>Hi <strong style="color:#f1f5f9;">{username}</strong>,</p>
        <p>you registered at Podman Kube Generator.
           Click the button below to activate your account:</p>
        {_info_box(f'The link is valid for <strong>24 hours</strong>.')}
        <p style="margin-top:24px;font-size:13px;color:#64748b;">
          If the button doesn't work, copy this link into your browser:<br>
          <a href="{activation_url}" style="color:#14b8a6;word-break:break-all;">{activation_url}</a>
        </p>
    '''
    return subject, _wrap_html('Activate account', body_html, activation_url, 'Activate account →')


def mail_account_activated(username, site_url):
    subject = 'Your account has been activated'
    body_html = f'''
        <p>Hi <strong style="color:#f1f5f9;">{username}</strong>,</p>
        <p>your account on Podman Kube Generator has been activated.
           You can now log in and submit your own Community Stacks.</p>
        {_info_box('After logging in, find all your submitted configurations under <strong style="color:#f1f5f9;">My Stacks</strong>.')}
    '''
    return subject, _wrap_html('Account activated 🎉', body_html, f'{site_url}/login/', 'Log in now →')


def mail_new_registration(username, email, admin_url):
    subject = f'[Podman Kube Generator] New registration: {username}'
    body_html = f'''
        <p>A new account is waiting for activation:</p>
        {_info_box(
            f'<strong style="color:#f1f5f9;">Username:</strong> {_highlight(username)}<br>'
            f'<strong style="color:#f1f5f9;">Email:</strong> {_highlight(email)}'
        )}
        <p>Click the button to activate the account in the admin panel
           (set <em>is_active</em> to ✓).</p>
    '''
    return subject, _wrap_html('New registration', body_html, admin_url, 'Activate in admin →')


def mail_password_reset(username, reset_url):
    subject = 'Reset your password — Podman Kube Generator'
    body_html = f'''
        <p>Hi <strong style="color:#f1f5f9;">{username}</strong>,</p>
        <p>you requested a password reset.
           Click the button below to set a new password:</p>
        {_info_box('The link is valid for <strong>24 hours</strong>. If you did not request a password reset, you can ignore this email.')}
        <p style="margin-top:24px;font-size:13px;color:#64748b;">
          If the button doesn't work, copy this link into your browser:<br>
          <a href="{reset_url}" style="color:#14b8a6;word-break:break-all;">{reset_url}</a>
        </p>
    '''
    return subject, _wrap_html('Reset password', body_html, reset_url, 'Set new password →')


def mail_new_stack(username, stack_name, stack_description, admin_url):
    subject = f'[Podman Kube Generator] New community stack: {stack_name}'
    body_html = f'''
        <p>A new community stack has been submitted and is waiting for approval:</p>
        {_info_box(
            f'<strong style="color:#f1f5f9;">Stack:</strong> {_highlight(stack_name)}<br>'
            f'<strong style="color:#f1f5f9;">Submitted by:</strong> {_highlight(username)}<br>'
            + (f'<strong style="color:#f1f5f9;">Description:</strong> {stack_description}' if stack_description else '')
        )}
        <p>Click the button to approve the stack in the admin panel
           (set <em>is_approved</em> to ✓).</p>
    '''
    return subject, _wrap_html('New community stack', body_html, admin_url, 'Approve in admin →')


def mail_new_comment(stack_owner, commenter, stack_name, comment_body, stack_url):
    subject = f'[Podman Kube Generator] New comment on your stack: {stack_name}'
    body_html = f'''
        <p>Hi <strong style="color:#f1f5f9;">{stack_owner}</strong>,</p>
        <p><strong style="color:#f1f5f9;">{commenter}</strong> commented on your stack
           <strong style="color:#5eead4;">{stack_name}</strong>:</p>
        {_info_box(f'<em style="color:#f1f5f9;">&ldquo;{comment_body}&rdquo;</em>')}
    '''
    return subject, _wrap_html('New comment', body_html, stack_url, 'View comment →')


def mail_test():
    subject = 'Test email — Podman Kube Generator'
    body_html = '''
        <p>This is a <strong style="color:#f1f5f9;">test email</strong>.</p>
        <p>SMTP is correctly configured and emails are being delivered successfully. ✓</p>
    '''
    return subject, _wrap_html('SMTP test successful', body_html)


# ── Sende-Funktionen ───────────────────────────────────────────────

def _send_msg(cfg, subject, html, recipient_list, from_email=None):
    sender = from_email or cfg.from_email or cfg.username
    # Plaintext aus HTML (minimal)
    import re
    plain = re.sub(r'<[^>]+>', '', html).strip()
    plain = re.sub(r'\n{3,}', '\n\n', plain)

    conn = _get_connection(cfg)
    msg = EmailMultiAlternatives(subject, plain, sender, recipient_list, connection=conn)
    msg.attach_alternative(html, 'text/html')
    msg.send()


def send_app_mail(subject, body, recipient_list, from_email=None):
    """Async senden — body kann plain text oder HTML sein."""
    cfg = _get_cfg()
    if not cfg.host or not recipient_list:
        return False

    # Wenn body kein HTML ist, in Layout einbetten
    if not body.strip().startswith('<'):
        html = _wrap_html(subject, f'<p>{body}</p>')
    else:
        html = body

    def _send():
        try:
            _send_msg(cfg, subject, html, recipient_list, from_email)
        except Exception:
            pass

    threading.Thread(target=_send, daemon=True).start()
    return True


def send_app_mail_sync(subject, body, recipient_list, from_email=None):
    """Synchron senden — für Tests. Gibt (True, '') oder (False, Fehlermeldung) zurück."""
    cfg = _get_cfg()
    if not cfg.host:
        return False, 'No SMTP server configured.'
    sender = from_email or cfg.from_email or cfg.username
    if not sender:
        return False, 'No sender configured.'
    if not recipient_list:
        return False, 'No recipient specified.'
    try:
        if not body.strip().startswith('<'):
            html = _wrap_html(subject, f'<p>{body}</p>')
        else:
            html = body
        _send_msg(cfg, subject, html, recipient_list, from_email)
        return True, ''
    except Exception as e:
        return False, str(e)
