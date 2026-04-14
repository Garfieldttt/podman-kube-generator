from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include, re_path
from django.views.generic import TemplateView
from django.conf import settings
from django.views.static import serve
from generator.sitemaps import StaticSitemap, StackSitemap, CommunityStackSitemap
from generator.totp_views import totp_setup, totp_verify

sitemaps = {
    'static': StaticSitemap,
    'stacks': StackSitemap,
    'community': CommunityStackSitemap,
}

ADMIN_URL = getattr(settings, 'ADMIN_URL', 'admin').strip('/')

urlpatterns = [
    path(f'{ADMIN_URL}/totp/setup/', totp_setup, name='totp_setup'),
    path(f'{ADMIN_URL}/totp/verify/', totp_verify, name='totp_verify'),
    path(f'{ADMIN_URL}/', admin.site.urls),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain')),
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    path('', include('generator.urls')),
]
