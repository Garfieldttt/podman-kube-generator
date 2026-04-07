import csv
import json
from urllib.parse import urlparse
from django.contrib import admin
from django.contrib.admin.widgets import AdminTextareaWidget
from django.db import models as db_models
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponseForbidden, HttpResponse, JsonResponse
from django.utils import timezone
from datetime import timedelta
import re
from django.db.models import Count, Max, Min, Avg
from django.db.models.functions import TruncDate, TruncHour, ExtractHour
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import StackTemplate, SavedConfig, ImpressumSettings, SeoSettings, AnalyticsSettings, Visit, CookieBannerSettings, SiteSettings, HiroMessage, FooterLink, UserStack, RegistrationSettings, EmailSettings, StackComment, StackLike, GeneratedYAML
from .compose_parser import parse_compose
from .mail import send_app_mail_sync, mail_test


class PrettyJSONWidget(AdminTextareaWidget):
    def format_value(self, value):
        if isinstance(value, (dict, list)):
            value = json.dumps(value, indent=2, ensure_ascii=False)
        elif isinstance(value, str):
            try:
                value = json.dumps(json.loads(value), indent=2, ensure_ascii=False)
            except (json.JSONDecodeError, ValueError):
                pass
        return super().format_value(value)


@admin.register(StackTemplate)
class StackTemplateAdmin(admin.ModelAdmin):
    change_list_template = 'admin/generator/stacktemplate/change_list.html'
    formfield_overrides = {
        db_models.JSONField: {'widget': PrettyJSONWidget(attrs={'rows': 30, 'style': 'font-family: monospace; width: 100%;'})},
    }
    list_display = ['label', 'category', 'key', 'icon', 'is_active', 'sort_order', 'created_at']
    list_filter = ['category', 'is_active']
    search_fields = ['label', 'key', 'category']
    list_editable = ['is_active', 'sort_order']
    readonly_fields = ['created_at']
    fieldsets = [
        (None, {'fields': ['key', 'label', 'description', 'icon', 'category', 'is_active', 'sort_order']}),
        ('Stack Configuration (JSON)', {'fields': ['stack_data']}),
        ('Meta', {'fields': ['created_at']}),
    ]

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('upload-compose/', self.admin_site.admin_view(self.upload_compose_view), name='generator_stacktemplate_upload_compose'),
        ]
        return custom + urls

    def upload_compose_view(self, request):
        if not request.user.has_perm('generator.add_stacktemplate'):
            return HttpResponseForbidden()

        ctx = dict(self.admin_site.each_context(request), title='Upload Compose File')

        if request.method == 'POST':
            f = request.FILES.get('compose_file')
            label = request.POST.get('label', '').strip()
            category = request.POST.get('category', 'Eigene').strip() or 'Eigene'
            icon = request.POST.get('icon', 'bi-file-earmark-code').strip() or 'bi-file-earmark-code'

            if not f:
                messages.error(request, 'No file selected.')
                return render(request, 'admin/generator/stacktemplate/upload_compose.html', ctx)

            try:
                content = f.read().decode('utf-8')
                stack_data, pod_name = parse_compose(content, f.name)
            except Exception as e:
                messages.error(request, f'Parse error: {e}')
                return render(request, 'admin/generator/stacktemplate/upload_compose.html', ctx)

            key = pod_name
            display_label = label or pod_name

            # key eindeutig machen falls nötig
            base_key = key
            counter = 1
            while StackTemplate.objects.filter(key=key).exists():
                key = f'{base_key}-{counter}'
                counter += 1

            obj = StackTemplate.objects.create(
                key=key,
                label=display_label,
                icon=icon,
                category=category,
                stack_data=stack_data,
            )
            messages.success(request, f'Stack "{obj.label}" (key: {obj.key}) imported successfully.')
            return redirect('admin:generator_stacktemplate_change', obj.pk)

        return render(request, 'admin/generator/stacktemplate/upload_compose.html', ctx)


@admin.register(HiroMessage)
class HiroMessageAdmin(admin.ModelAdmin):
    list_display = ['text_de', 'text_en', 'is_active', 'sort_order']
    list_editable = ['is_active', 'sort_order']
    list_display_links = ['text_de']
    ordering = ['sort_order', 'pk']


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = [
        ('Features', {'fields': ['canvas_enabled', 'compose_import_timeout']}),
        ('Navbar', {'fields': ['brand_icon', 'brand_name', 'brand_tagline', 'brand_name_en', 'brand_tagline_en']}),
        ('Homepage', {'fields': ['home_heading', 'home_intro', 'home_heading_en', 'home_intro_en']}),
        ('Footer', {'fields': ['footer_author', 'footer_author_url', 'donation_url']}),
    ]

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ImpressumSettings)
class ImpressumAdmin(admin.ModelAdmin):
    fieldsets = [
        ('Contact', {'fields': ['name', 'adresse', 'email', 'telefon', 'website']}),
        ('Additional Info', {'fields': ['zusatz']}),
    ]

    def has_add_permission(self, request):
        return not ImpressumSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SeoSettings)
class SeoAdmin(admin.ModelAdmin):
    fieldsets = [
        ('General', {'fields': ['site_name', 'home_title', 'home_description', 'keywords']}),
        ('Social Media', {'fields': ['og_image_url']}),
        ('Google', {'fields': ['google_site_verification']}),
        ('robots.txt', {'fields': ['robots_txt']}),
    ]

    def has_add_permission(self, request):
        return not SeoSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AnalyticsSettings)
class AnalyticsSettingsAdmin(admin.ModelAdmin):
    fieldsets = [
        ('Tracking', {'fields': ['enabled', 'anonymize_ip', 'track_bots', 'track_private_ips', 'retention_days']}),
        ('Exclusions', {'fields': ['exclude_paths', 'blocked_ips']}),
    ]

    def has_add_permission(self, request):
        return not AnalyticsSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


def _analytics_qs(range_param):
    qs = Visit.objects.all()
    now = timezone.now()
    if range_param == 'realtime':
        qs = qs.filter(timestamp__gte=now - timedelta(minutes=5))
    elif range_param == 'today':
        qs = qs.filter(timestamp__date=now.date())
    elif range_param == '7':
        qs = qs.filter(timestamp__gte=now - timedelta(days=7))
    elif range_param == '30':
        qs = qs.filter(timestamp__gte=now - timedelta(days=30))
    return qs


def _pct_rows(qs, field, total, limit=10):
    rows = list(qs.values(field).annotate(cnt=Count('id')).order_by('-cnt')[:limit])
    for r in rows:
        r['pct'] = round(r['cnt'] / total * 100) if total else 0
    return rows


def _range_start(range_param):
    now = timezone.now()
    if range_param == 'realtime':
        return now - timedelta(minutes=5)
    elif range_param == 'today':
        local_now = timezone.localtime(now)
        return local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif range_param == '7':
        return now - timedelta(days=7)
    elif range_param == '30':
        return now - timedelta(days=30)
    return None


def _prev_qs(range_param):
    now = timezone.now()
    if range_param == 'today':
        yesterday = now.date() - timedelta(days=1)
        return Visit.objects.filter(timestamp__date=yesterday)
    elif range_param == '7':
        return Visit.objects.filter(timestamp__gte=now - timedelta(days=14), timestamp__lt=now - timedelta(days=7))
    elif range_param == '30':
        return Visit.objects.filter(timestamp__gte=now - timedelta(days=60), timestamp__lt=now - timedelta(days=30))
    return None


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    change_list_template = 'admin/generator/analytics/dashboard.html'
    list_display = ['timestamp', 'ip', 'country_code', 'browser_family', 'os_family', 'is_mobile', 'path']
    list_filter = ['country_code', 'browser_family', 'os_family', 'is_mobile']
    search_fields = ['ip', 'path', 'referrer']
    readonly_fields = [f.name for f in Visit._meta.fields]

    def has_add_permission(self, request):
        return False

    def get_urls(self):
        urls = super().get_urls()
        return [
            path('export-csv/', self.admin_site.admin_view(self.export_csv), name='generator_visit_export_csv'),
            path('block-ip/', self.admin_site.admin_view(self.block_ip_view), name='generator_visit_block_ip'),
        ] + urls

    def block_ip_view(self, request):
        if request.method != 'POST':
            return JsonResponse({'ok': False}, status=405)
        ip = request.POST.get('ip', '').strip()
        action = request.POST.get('action', 'block')
        if ip:
            cfg = AnalyticsSettings.get_solo()
            ips = {line.strip() for line in (cfg.blocked_ips or '').splitlines() if line.strip()}
            if action == 'block':
                ips.add(ip)
            else:
                ips.discard(ip)
            cfg.blocked_ips = '\n'.join(sorted(ips))
            cfg.save()
        return JsonResponse({'ok': True})

    def export_csv(self, request):
        range_param = request.GET.get('range', '30')
        qs = _analytics_qs(range_param).order_by('-timestamp')
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="visits_{range_param}.csv"'
        writer = csv.writer(response)
        writer.writerow(['timestamp', 'ip', 'country_code', 'country_name', 'browser_family', 'os_family', 'is_mobile', 'path', 'referrer'])
        for row in qs.values_list('timestamp', 'ip', 'country_code', 'country_name', 'browser_family', 'os_family', 'is_mobile', 'path', 'referrer').iterator():
            writer.writerow(row)
        return response

    def changelist_view(self, request, extra_context=None):
        range_param = request.GET.get('range', '30')
        qs = _analytics_qs(range_param)
        total = qs.count()
        today_count = Visit.objects.filter(timestamp__date=timezone.now().date()).count()

        unique_ips = qs.exclude(ip='').values('ip').distinct().count()
        unique_sessions = qs.exclude(session_key='').values('session_key').distinct().count()
        mobile_count = qs.filter(is_mobile=True).count()
        mobile_pct = round(mobile_count / total * 100) if total else 0

        # Bounce rate
        session_counts = qs.exclude(session_key='').values('session_key').annotate(pages=Count('id'))
        total_sessions_br = session_counts.count()
        bounce_sessions = session_counts.filter(pages=1).count()
        bounce_rate = round(bounce_sessions / total_sessions_br * 100) if total_sessions_br else 0

        # Aktive Filter
        filter_country = request.GET.get('country_code', '')
        filter_browser = request.GET.get('browser_family', '')
        filter_os = request.GET.get('os_family', '')
        filter_path = request.GET.get('path', '')
        filter_ip = request.GET.get('ip', '')
        filter_mobile = request.GET.get('is_mobile__exact', '')
        show = request.GET.get('show', '')

        active_filter = filter_country or filter_browser or filter_os or filter_path or filter_ip or filter_mobile

        filtered_qs = qs
        if filter_country:
            filtered_qs = filtered_qs.filter(country_code=filter_country)
        if filter_browser:
            filtered_qs = filtered_qs.filter(browser_family=filter_browser)
        if filter_os:
            filtered_qs = filtered_qs.filter(os_family=filter_os)
        if filter_path:
            filtered_qs = filtered_qs.filter(path=filter_path)
        if filter_ip:
            filtered_qs = filtered_qs.filter(ip=filter_ip)
        if filter_mobile:
            filtered_qs = filtered_qs.filter(is_mobile=(filter_mobile == '1'))

        # Chart: gefilterten QS verwenden; bei unique_ips → distinct IPs pro Periode
        trunc = TruncHour if range_param in ('today', 'realtime') else TruncDate
        fmt = '%H:%M' if range_param in ('today', 'realtime') else '%d.%m.'
        if show == 'unique_ips':
            chart_qs = list(
                filtered_qs.exclude(ip='')
                .annotate(period=trunc('timestamp'))
                .values('period')
                .annotate(cnt=Count('ip', distinct=True))
                .order_by('period')
            )
            chart_label = 'Unique IPs'
        else:
            chart_qs = list(
                filtered_qs
                .annotate(period=trunc('timestamp'))
                .values('period')
                .annotate(cnt=Count('id'))
                .order_by('period')
            )
            chart_label = 'Page views'
        chart_labels = [r['period'].strftime(fmt) for r in chart_qs]
        chart_values = [r['cnt'] for r in chart_qs]

        # Top countries
        country_rows = list(qs.values('country_code', 'country_name').annotate(cnt=Count('id')).order_by('-cnt')[:10])
        for r in country_rows:
            r['pct'] = round(r['cnt'] / total * 100) if total else 0

        browser_rows = _pct_rows(qs, 'browser_family', total)
        os_rows = _pct_rows(qs, 'os_family', total)
        page_rows = _pct_rows(qs, 'path', total)

        # Top referrers
        ref_rows = list(qs.exclude(referrer='').values('referrer').annotate(cnt=Count('id')).order_by('-cnt')[:10])
        for r in ref_rows:
            r['pct'] = round(r['cnt'] / total * 100) if total else 0
            try:
                r['domain'] = urlparse(r['referrer']).netloc or r['referrer']
            except Exception:
                r['domain'] = r['referrer']

        recent_qs = filtered_qs.order_by('-timestamp')

        # Unique-IPs-Ansicht
        ip_rows = None
        if show == 'unique_ips':
            ip_rows = list(
                qs.exclude(ip='')
                .values('ip', 'country_code', 'country_name')
                .annotate(cnt=Count('id'), last_seen=Max('timestamp'))
                .order_by('-cnt')[:200]
            )

        # Comparison chart (prev period aligned to current labels)
        prev_qs = _prev_qs(range_param)
        chart_values_prev = None
        if prev_qs is not None:
            shift_days = {'today': 1, '7': 7, '30': 30}.get(range_param, 0)
            shift = timedelta(days=shift_days)
            prev_chart_raw = list(
                prev_qs.annotate(period=trunc('timestamp'))
                .values('period').annotate(cnt=Count('id')).order_by('period')
            )
            prev_dict = {(r['period'] + shift).strftime(fmt): r['cnt'] for r in prev_chart_raw}
            chart_values_prev = [prev_dict.get(lbl, 0) for lbl in chart_labels]

        # Hour-of-day distribution
        hour_dist_raw = list(
            filtered_qs.annotate(hour=ExtractHour('timestamp'))
            .values('hour').annotate(cnt=Count('id')).order_by('hour')
        )
        hour_dist = [0] * 24
        for r in hour_dist_raw:
            hour_dist[r['hour']] = r['cnt']

        # New vs Returning sessions
        range_start = _range_start(range_param)
        if unique_sessions > 0 and range_start:
            sess_in_range = filtered_qs.exclude(session_key='').values_list('session_key', flat=True).distinct()
            first_visits_qs = (
                Visit.objects.filter(session_key__in=sess_in_range)
                .values('session_key').annotate(first=Min('timestamp'))
            )
            new_sessions = first_visits_qs.filter(first__gte=range_start).count()
            returning_sessions = max(0, unique_sessions - new_sessions)
        else:
            new_sessions, returning_sessions = unique_sessions, 0

        # Top Stacks
        _stack_re = re.compile(r'^/stack/([^/]+)/?$')
        stack_path_rows = list(
            qs.filter(path__startswith='/stack/')
            .values('path').annotate(cnt=Count('id')).order_by('-cnt')
        )
        top_stacks = []
        for r in stack_path_rows:
            m = _stack_re.match(r['path'])
            if m:
                top_stacks.append({'key': m.group(1), 'cnt': r['cnt']})
        top_stacks = top_stacks[:10]

        # Generator stats
        filter_gen_ip = request.GET.get('gen_ip', '')
        filter_gen_mode = request.GET.get('gen_mode', '')
        gen_qs = GeneratedYAML.objects.all()
        if range_start:
            gen_qs = gen_qs.filter(timestamp__gte=range_start)
        if filter_gen_ip:
            gen_qs = gen_qs.filter(ip=filter_gen_ip)
        if filter_gen_mode:
            gen_qs = gen_qs.filter(mode=filter_gen_mode)
        gen_total = gen_qs.count()
        gen_by_mode = list(gen_qs.values('mode').annotate(cnt=Count('id')).order_by('-cnt'))
        gen_avg_containers = round(gen_qs.aggregate(avg=Avg('container_count'))['avg'] or 0, 1)
        gen_top_ips = list(gen_qs.exclude(ip='').values('ip').annotate(cnt=Count('id')).order_by('-cnt')[:10])
        gen_rows = list(gen_qs.order_by('-timestamp')[:200].values(
            'timestamp', 'pod_name', 'images', 'mode', 'container_count', 'init_count', 'ip'
        )) if show == 'pods' else None

        analytics_cfg = AnalyticsSettings.get_solo()
        blocked_ips_set = {line.strip() for line in (analytics_cfg.blocked_ips or '').splitlines() if line.strip()}

        ctx = dict(
            self.admin_site.each_context(request),
            title='Analytics Dashboard',
            range=range_param,
            stats={
                'total': total,
                'unique_ips': unique_ips,
                'unique_sessions': unique_sessions,
                'mobile_pct': mobile_pct,
                'today': today_count,
                'realtime': filtered_qs.filter(timestamp__gte=timezone.now() - timedelta(minutes=5)).count(),
                'bounce_rate': bounce_rate,
                'new_sessions': new_sessions,
                'returning_sessions': returning_sessions,
            },
            chart_labels=json.dumps(chart_labels),
            chart_values=json.dumps(chart_values),
            chart_values_prev=json.dumps(chart_values_prev) if chart_values_prev is not None else 'null',
            chart_label=chart_label,
            hour_dist=json.dumps(hour_dist),
            hour_labels=json.dumps([f'{h:02d}:00' for h in range(24)]),
            top_countries=country_rows,
            top_browsers=browser_rows,
            top_os=os_rows,
            top_pages=page_rows,
            top_referrers=ref_rows,
            top_stacks=top_stacks,
            gen_total=gen_total,
            gen_by_mode=gen_by_mode,
            gen_avg_containers=gen_avg_containers,
            gen_top_ips=gen_top_ips,
            filter_gen_ip=filter_gen_ip,
            filter_gen_mode=filter_gen_mode,
            gen_rows=gen_rows,
            recent=recent_qs[:100],
            active_filter=active_filter,
            ip_rows=ip_rows,
            show=show,
            blocked_ips=sorted(blocked_ips_set),
            blocked_ips_set=blocked_ips_set,
        )
        return render(request, self.change_list_template, ctx)


@admin.register(CookieBannerSettings)
class CookieBannerAdmin(admin.ModelAdmin):
    fieldsets = [
        ('General', {'fields': ['enabled', 'position', 'lifetime_days']}),
        ('Texts', {'fields': ['title', 'text', 'title_en', 'text_en']}),
        ('Buttons', {'fields': ['accept_label', 'show_decline_button', 'decline_label', 'accept_label_en', 'decline_label_en']}),
        ('Privacy Link', {'fields': ['privacy_url', 'privacy_label', 'privacy_label_en']}),
        ('Cookie Categories', {'fields': ['analytics_label', 'analytics_description', 'analytics_label_en', 'analytics_description_en']}),
    ]

    def has_add_permission(self, request):
        return not CookieBannerSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FooterLink)
class FooterLinkAdmin(admin.ModelAdmin):
    list_display = ['label', 'url', 'icon', 'sort_order', 'is_active', 'open_new_tab']
    list_editable = ['sort_order', 'is_active', 'open_new_tab']
    list_display_links = ['label']
    ordering = ['sort_order', 'pk']


@admin.register(SavedConfig)
class SavedConfigAdmin(admin.ModelAdmin):
    list_display = ['name', 'uuid', 'created_at']
    readonly_fields = ['uuid', 'created_at']
    search_fields = ['name']


@admin.register(UserStack)
class UserStackAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'description', 'is_approved', 'created_at']
    list_editable = ['is_approved']
    list_filter = ['is_approved']
    list_display_links = ['name']
    readonly_fields = ['user', 'name', 'description', 'form_data', 'created_at']
    search_fields = ['name', 'user__username']

    def has_add_permission(self, request):
        return False


@admin.register(StackComment)
class StackCommentAdmin(admin.ModelAdmin):
    list_display = ['user', 'stack', 'body_short', 'is_approved', 'created_at']
    list_editable = ['is_approved']
    list_filter = ['is_approved', 'created_at']
    list_display_links = ['user']
    search_fields = ['user__username', 'stack__name', 'body']
    readonly_fields = ['user', 'stack', 'body', 'created_at']

    def body_short(self, obj):
        return obj.body[:60]
    body_short.short_description = 'Comment'

    def has_add_permission(self, request):
        return False


@admin.register(StackLike)
class StackLikeAdmin(admin.ModelAdmin):
    list_display = ['user', 'stack', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'stack__name']
    readonly_fields = ['user', 'stack', 'created_at']

    def has_add_permission(self, request):
        return False


@admin.register(RegistrationSettings)
class RegistrationSettingsAdmin(admin.ModelAdmin):
    fieldsets = [
        ('Registration', {'fields': ['registration_enabled']}),
        ('Account Activation', {'fields': ['email_activation', 'email_from'],
          'description': 'Email activation: users confirm via link. Disabled: manual activation by admin (set is_active in the Users section).'}),
        ('Password Reset', {'fields': ['password_reset_enabled']}),
    ]

    def has_add_permission(self, request):
        return not RegistrationSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EmailSettings)
class EmailSettingsAdmin(admin.ModelAdmin):
    change_list_template = None
    fieldsets = [
        ('SMTP Server', {'fields': ['host', 'port', 'use_tls', 'use_ssl']}),
        ('Authentication', {'fields': ['username', 'password']}),
        ('Addresses', {'fields': ['from_email', 'admin_email']}),
    ]

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('<path:object_id>/test-mail/', self.admin_site.admin_view(self.test_mail_view), name='generator_emailsettings_test_mail'),
        ]
        return custom + urls

    def test_mail_view(self, request, object_id):
        obj = EmailSettings.get_solo()
        recipient = request.POST.get('recipient', '').strip() or obj.admin_email
        if request.method == 'POST' and recipient:
            subject, html = mail_test()
            ok, err = send_app_mail_sync(subject=subject, body=html, recipient_list=[recipient])
            if ok:
                messages.success(request, f'Test email sent successfully to {recipient}.')
            else:
                messages.error(request, f'Error: {err}')
            return redirect('admin:generator_emailsettings_change', obj.pk)
        return redirect('admin:generator_emailsettings_change', obj.pk)

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['test_mail_url'] = f'{object_id}/test-mail/' if object_id else None
        return super().changeform_view(request, object_id, form_url, extra_context)

    def has_add_permission(self, request):
        return not EmailSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


# User-Admin erweitern: is_active direkt in der Liste editierbar
admin.site.unregister(User)

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'is_active', 'is_staff', 'date_joined']
    list_editable = ['is_active']
    list_display_links = ['username']
