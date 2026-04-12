import re
from django.conf import settings
from django.shortcuts import redirect

_BOT_RE = re.compile(
    r'bot|crawl|spider|slurp|mediapartners|yahoo|wget|curl|python-requests|'
    r'zgrab|nmap|masscan|nikto|sqlmap|nuclei|headless|phantom|selenium|'
    r'go-http|axios|libwww|jakarta|java/',
    re.IGNORECASE,
)

_SKIP_RE = re.compile(r'^/(admin|static|staticfiles|favicon\.ico|robots\.txt|sitemap|apple-touch-icon)')
def _is_private_ip(ip):
    import ipaddress
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return False


def _get_ip(request):
    for header in ('HTTP_X_FORWARDED_FOR', 'HTTP_X_REAL_IP', 'REMOTE_ADDR'):
        ip = request.META.get(header, '').split(',')[0].strip()
        if ip:
            return ip
    return ''


def _anonymize_ip(ip):
    if not ip:
        return ''
    try:
        if ':' in ip:
            parts = ip.split(':')
            return ':'.join(parts[:4]) + '::'
        parts = ip.split('.')
        return '.'.join(parts[:3]) + '.0'
    except Exception:
        return ''


def _parse_ua(ua_string):
    if not ua_string:
        return '', '', False
    try:
        from user_agents import parse
        ua = parse(ua_string)
        return ua.browser.family or 'Other', ua.os.family or 'Other', ua.is_mobile
    except ImportError:
        pass
    # Fallback ohne user-agents
    for browser, token in (
        ('Edge', 'Edg/'), ('Chrome', 'Chrome/'), ('Firefox', 'Firefox/'),
        ('Safari', 'Safari/'), ('Opera', 'OPR/'), ('IE', 'Trident/'),
    ):
        if token in ua_string:
            break
    else:
        browser = 'Other'
    for os_name, token in (
        ('Android', 'Android'), ('iOS', 'iPhone'), ('iOS', 'iPad'),
        ('Windows', 'Windows'), ('macOS', 'Macintosh'), ('Linux', 'Linux'),
    ):
        if token in ua_string:
            break
    else:
        os_name = 'Other'
    is_mobile = any(x in ua_string for x in ('Mobile', 'Android', 'iPhone', 'iPad'))
    return browser, os_name, is_mobile


def _get_country(ip):
    if not ip or ip.endswith('.0') or ip.endswith('::'):
        return '', ''
    try:
        from django.conf import settings as djsettings
        geoip_path = getattr(djsettings, 'GEOIP_PATH', None)
        if not geoip_path:
            return '', ''
        import geoip2.database
        import os
        db = os.path.join(geoip_path, 'GeoLite2-Country.mmdb')
        with geoip2.database.Reader(db) as reader:
            r = reader.country(ip)
            return r.country.iso_code or '', r.country.name or ''
    except Exception:
        return '', ''


_TOTP_EXEMPT = {
    '/admin/login/',
    '/admin/logout/',
    '/admin/totp/setup/',
    '/admin/totp/verify/',
    '/admin/jsi18n/',
}


class IPBlockMiddleware:
    CACHE_KEY = 'ip_block_list'
    CACHE_TTL = 60  # seconds

    def __init__(self, get_response):
        self.get_response = get_response

    def _get_blocked(self):
        from django.core.cache import cache
        blocked = cache.get(self.CACHE_KEY)
        if blocked is None:
            try:
                from generator.models import AnalyticsSettings
                s = AnalyticsSettings.objects.filter(pk=1).first()
                raw = s.access_blocked_ips if s else ''
            except Exception:
                raw = ''
            blocked = {line.strip() for line in raw.splitlines() if line.strip()}
            cache.set(self.CACHE_KEY, blocked, self.CACHE_TTL)
        return blocked

    def __call__(self, request):
        ip = _get_ip(request)
        if ip and ip in self._get_blocked():
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden('Access denied.')
        return self.get_response(request)


class AdminTOTPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.path.startswith('/admin/')
            and request.path not in _TOTP_EXEMPT
            and not getattr(settings, 'TOTP_DISABLED', False)
            and request.user.is_authenticated
            and request.user.is_staff
        ):
            if not request.session.get('admin_totp_verified'):
                try:
                    device = request.user.totp_device
                    if device.confirmed:
                        return redirect(f'/admin/totp/verify/?next={request.path}')
                    else:
                        return redirect('/admin/totp/setup/')
                except Exception:
                    return redirect('/admin/totp/setup/')

        return self.get_response(request)


class VisitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.method == 'GET' and not _SKIP_RE.match(request.path):
            try:
                self._track(request)
            except Exception:
                pass
        return response

    def _track(self, request):
        from .models import AnalyticsSettings, Visit
        cfg = AnalyticsSettings.get_solo()
        if not cfg.enabled:
            return
        ua_string = request.META.get('HTTP_USER_AGENT', '')
        if not cfg.track_bots and _BOT_RE.search(ua_string):
            return

        ip = _get_ip(request)
        if _is_private_ip(ip) and not cfg.track_private_ips:
            return
        blocked = {line.strip() for line in (cfg.blocked_ips or '').splitlines() if line.strip()}
        if ip in blocked:
            return
        for prefix in (cfg.exclude_paths or '').splitlines():
            prefix = prefix.strip()
            if prefix and request.path.startswith(prefix):
                return
        country_code, country_name = _get_country(ip)
        if cfg.anonymize_ip:
            ip = _anonymize_ip(ip)

        browser_family, os_family, is_mobile = _parse_ua(ua_string)
        referrer = request.META.get('HTTP_REFERER', '')[:500]

        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key or ''

        Visit.objects.create(
            path=request.path[:500],
            ip=ip,
            country_code=country_code,
            country_name=country_name,
            browser_family=browser_family,
            os_family=os_family,
            is_mobile=is_mobile,
            referrer=referrer,
            session_key=session_key,
        )

        # Retention cleanup (1% chance per request to avoid overhead)
        import random
        if cfg.retention_days > 0 and random.random() < 0.01:
            from django.utils import timezone
            from datetime import timedelta
            cutoff = timezone.now() - timedelta(days=cfg.retention_days)
            Visit.objects.filter(timestamp__lt=cutoff).delete()
