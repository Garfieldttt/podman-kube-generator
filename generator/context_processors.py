import json
from django.conf import settings
from .models import SeoSettings, CookieBannerSettings, SiteSettings, HiroMessage, FooterLink, ImpressumSettings


def nav_user(request):
    if not request.user.is_authenticated:
        return {}
    try:
        avatar_url = request.user.profile.get_avatar_url()
    except Exception:
        avatar_url = ''
    return {
        'nav_avatar_url': avatar_url,
        'nav_username_initial': (request.user.username[0] if request.user.username else '?').upper(),
    }


def site_url(request):
    return {'site_url': getattr(settings, 'SITE_URL', 'http://localhost:8000')}


def seo(request):
    return {'seo': SeoSettings.get_solo()}


def site(request):
    s = SiteSettings.get_solo()
    resolved = {
        'brand_name': s.brand_name_en or s.brand_name,
        'brand_tagline': s.brand_tagline_en or s.brand_tagline,
        'brand_icon': s.brand_icon,
        'home_heading': s.home_heading_en or s.home_heading,
        'home_intro': s.home_intro_en or s.home_intro,
        'donation_url': s.donation_url,
        'canvas_enabled': s.canvas_enabled,
    }
    return {'site': type('Site', (), resolved)()}


def hiro_messages(request):
    msgs = HiroMessage.objects.filter(is_active=True)
    data = [m.text_en or m.text_de for m in msgs]
    return {'hiro_msgs_json': json.dumps(data, ensure_ascii=False)}


def footer_links(request):
    return {'footer_links': FooterLink.objects.filter(is_active=True)}


def legal(request):
    imp = ImpressumSettings.get_solo()
    return {
        'legal_impressum_enabled': imp.impressum_enabled,
        'legal_privacy_enabled': imp.privacy_enabled,
    }


def cookie_banner(request):
    banner = CookieBannerSettings.get_solo()
    consent = request.COOKIES.get('cookie_consent')
    resolved = {
        'enabled': banner.enabled,
        'position': banner.position,
        'lifetime_days': banner.lifetime_days,
        'show_decline_button': banner.show_decline_button,
        'privacy_url': banner.privacy_url,
        'title': banner.title_en or banner.title,
        'text': banner.text_en or banner.text,
        'accept_label': banner.accept_label_en or banner.accept_label,
        'decline_label': banner.decline_label_en or banner.decline_label,
        'privacy_label': banner.privacy_label_en or banner.privacy_label,
        'analytics_label': banner.analytics_label_en or banner.analytics_label,
        'analytics_description': banner.analytics_description_en or banner.analytics_description,
    }
    return {
        'cookie_banner': type('CookieBanner', (), resolved)(),
        'cookie_consent': consent,
    }
