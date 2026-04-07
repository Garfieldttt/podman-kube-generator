import base64
import pyotp
import qrcode
from io import BytesIO

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods

from .models import TOTPDevice


def _require_staff(view_func):
    """Decorator: Nur eingeloggte Staff-User dürfen diese Views aufrufen."""
    @login_required(login_url='/admin/login/')
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.path, '/admin/login/')
        return view_func(request, *args, **kwargs)
    return wrapper


def _make_qr_png(uri):
    img = qrcode.make(uri)
    buf = BytesIO()
    img.save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode()


@_require_staff
@require_http_methods(['GET', 'POST'])
def totp_setup(request):
    if getattr(settings, 'TOTP_DISABLED', False):
        return redirect('/admin/')

    # Bereits ein bestätigtes Gerät → direkt zu verify
    try:
        device = request.user.totp_device
        if device.confirmed:
            return redirect('/admin/totp/verify/')
    except TOTPDevice.DoesNotExist:
        device = None

    # Secret erstellen (oder vorhandenes unbestätigtes verwenden)
    if device is None:
        secret = pyotp.random_base32()
        device = TOTPDevice.objects.create(user=request.user, secret=secret, confirmed=False)
    else:
        secret = device.secret

    site_name = getattr(settings, 'TOTP_ISSUER', 'Podman Kube Generator')
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=request.user.email or request.user.username, issuer_name=site_name)
    qr_b64 = _make_qr_png(uri)

    error = None
    if request.method == 'POST':
        code = request.POST.get('code', '').strip().replace(' ', '')
        if totp.verify(code, valid_window=1):
            device.confirmed = True
            device.save()
            request.session['admin_totp_verified'] = True
            return redirect('/admin/')
        else:
            error = 'Ungültiger Code. Bitte erneut versuchen.'

    return render(request, 'admin/totp_setup.html', {
        'qr_b64': qr_b64,
        'secret': secret,
        'error': error,
    })


@_require_staff
@require_http_methods(['GET', 'POST'])
def totp_verify(request):
    if getattr(settings, 'TOTP_DISABLED', False):
        return redirect('/admin/')

    # Kein bestätigtes Gerät → Setup
    try:
        device = request.user.totp_device
        if not device.confirmed:
            return redirect('/admin/totp/setup/')
    except TOTPDevice.DoesNotExist:
        return redirect('/admin/totp/setup/')

    next_url = request.GET.get('next', '/admin/')
    if not next_url.startswith('/admin/'):
        next_url = '/admin/'

    error = None
    attempts = request.session.get('totp_attempts', 0)

    if request.method == 'POST':
        if attempts >= 5:
            error = 'Zu viele Fehlversuche. Bitte neu einloggen.'
        else:
            code = request.POST.get('code', '').strip().replace(' ', '')
            totp = pyotp.TOTP(device.secret)
            if totp.verify(code, valid_window=1):
                request.session['admin_totp_verified'] = True
                request.session.pop('totp_attempts', None)
                return redirect(next_url)
            else:
                attempts += 1
                request.session['totp_attempts'] = attempts
                remaining = 5 - attempts
                error = f'Ungültiger Code. Noch {remaining} Versuch{"e" if remaining != 1 else ""} übrig.'

    return render(request, 'admin/totp_verify.html', {
        'error': error,
        'next': next_url,
    })
