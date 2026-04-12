import uuid
from django.db import models
from django.contrib.auth.models import User


class StackTemplate(models.Model):
    key = models.SlugField(max_length=80, unique=True, help_text='Unique key, e.g. wordpress-mariadb')
    label = models.CharField(max_length=100, help_text='Display name, e.g. WordPress + MariaDB')
    icon = models.CharField(max_length=60, default='bi-collection', help_text='Bootstrap Icons class, e.g. bi-globe')
    category = models.CharField(max_length=50, default='Other', help_text='Category for grouping, e.g. CMS')
    description = models.CharField(max_length=160, blank=True, default='', help_text='Short description, e.g. "Self-hosted Git server with web UI"')
    stack_data = models.JSONField(
        help_text='Stack configuration: pod_name, restart_policy, mode, host_network, containers, init_containers'
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order', 'category', 'label']

    def __str__(self):
        return f'{self.category} / {self.label}'


class ImpressumSettings(models.Model):
    impressum_enabled = models.BooleanField(default=False, verbose_name='Show Imprint page')
    privacy_enabled = models.BooleanField(default=False, verbose_name='Show Privacy Policy page')
    name = models.CharField(max_length=200, verbose_name='Name / Company', default='')
    adresse = models.TextField(blank=True, verbose_name='Address')
    email = models.EmailField(blank=True, verbose_name='Email')
    telefon = models.CharField(max_length=50, blank=True, verbose_name='Phone')
    website = models.URLField(blank=True, verbose_name='Website')
    zusatz = models.TextField(blank=True, verbose_name='Additional info / Imprint (liability, copyright etc.)')
    datenschutz_text = models.TextField(blank=True, verbose_name='Privacy Policy text')
    letzte_aenderung = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Impressum'
        verbose_name_plural = 'Impressum'

    def __str__(self):
        return 'Impressum'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class SeoSettings(models.Model):
    site_name = models.CharField(max_length=100, default='Podman Kube Generator', verbose_name='Site name (og:site_name)')
    home_title = models.CharField(max_length=120, default='Podman Kube Generator – Kubernetes YAML for podman play kube', verbose_name='Homepage title tag')
    home_description = models.TextField(max_length=300, default='Generate Kubernetes YAML for podman play kube for free. Create pod configurations, multi-container stacks and systemd Quadlet instructions in seconds.', verbose_name='Homepage meta description')
    keywords = models.CharField(max_length=500, default='podman, kubernetes yaml, podman play kube, container, pod generator, quadlet, systemd, rootless container', verbose_name='Meta keywords')
    og_image_url = models.URLField(blank=True, verbose_name='OG image URL (Social Media preview)', help_text='Absolute URL to preview image, e.g. https://example.com/og.png')
    google_site_verification = models.CharField(max_length=200, blank=True, verbose_name='Google Site Verification', help_text='Content of the content attribute in the meta tag')
    robots_txt = models.TextField(
        verbose_name='robots.txt content',
        default='User-agent: *\nDisallow: /\n',
        help_text='Served directly as /robots.txt. {site_url} is replaced with the site URL.',
    )

    class Meta:
        verbose_name = 'SEO Settings'
        verbose_name_plural = 'SEO Settings'

    def __str__(self):
        return 'SEO Settings'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class AnalyticsSettings(models.Model):
    enabled = models.BooleanField(default=True, verbose_name='Enable tracking')
    anonymize_ip = models.BooleanField(
        default=True,
        verbose_name='Anonymize IP',
        help_text='Store only the first 3 octets, e.g. 192.168.1.x → 192.168.1.0 (GDPR)',
    )
    track_bots = models.BooleanField(default=False, verbose_name='Track bots')
    track_private_ips = models.BooleanField(default=False, verbose_name='Track LAN IPs',
        help_text='Record visits from private IP addresses (10.x, 172.16.x, 192.168.x).')
    exclude_paths = models.TextField(
        blank=True, default='',
        verbose_name='Exclude paths',
        help_text='One path per line, e.g. /api/ or /stack/. Prefix matching.',
    )
    blocked_ips = models.TextField(
        blank=True, default='',
        verbose_name='Exclude IPs from analytics',
        help_text='One IP per line. Visits from these IPs will not be recorded in analytics.',
    )
    retention_days = models.PositiveSmallIntegerField(
        default=90,
        verbose_name='Retention (days)',
        help_text='Automatically delete visits after X days. 0 = never delete.',
    )

    class Meta:
        verbose_name = 'Analytics Settings'
        verbose_name_plural = 'Analytics Settings'

    def __str__(self):
        return 'Analytics-Einstellungen'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Visit(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    path = models.CharField(max_length=500)
    ip = models.CharField(max_length=45, blank=True, db_index=True)
    country_code = models.CharField(max_length=2, blank=True)
    country_name = models.CharField(max_length=100, blank=True)
    browser_family = models.CharField(max_length=80, blank=True)
    os_family = models.CharField(max_length=80, blank=True)
    is_mobile = models.BooleanField(default=False)
    referrer = models.CharField(max_length=500, blank=True)
    session_key = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Visit'
        verbose_name_plural = 'Visits'
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['country_code']),
            models.Index(fields=['browser_family']),
        ]

    def __str__(self):
        return f'{self.timestamp:%Y-%m-%d %H:%M} {self.path} [{self.country_code or "?"}]'


class HiroMessage(models.Model):
    text_de = models.CharField(max_length=300, verbose_name='Text (German)')
    text_en = models.CharField(max_length=300, verbose_name='Text (English)')
    is_active = models.BooleanField(default=True, verbose_name='Active')
    sort_order = models.PositiveSmallIntegerField(default=0, verbose_name='Sort order')

    class Meta:
        ordering = ['sort_order', 'pk']
        verbose_name = 'Hiro Message'
        verbose_name_plural = 'Hiro Messages'

    def __str__(self):
        return self.text_de[:60]


class SiteSettings(models.Model):
    # Navbar
    brand_name = models.CharField(max_length=100, default='Podman Kube Generator', verbose_name='Brand name (Navbar)')
    brand_tagline = models.CharField(max_length=200, default='podman play kube · systemd quadlet', verbose_name='Brand tagline (Navbar)')
    brand_icon = models.CharField(max_length=10, default='🦭', verbose_name='Brand icon (Emoji)')

    # Homepage
    home_heading = models.CharField(max_length=200, default='Podman Pod Generator', verbose_name='Homepage H1 heading')
    home_intro = models.TextField(default='Configure your pod — get ready-to-use Kubernetes YAML for podman play kube.', verbose_name='Homepage intro text')

    # Footer
    donation_url = models.URLField(blank=True, default='', verbose_name='Donation URL (empty = hide)')

    # Features
    canvas_enabled = models.BooleanField(default=True, verbose_name='Pod Builder enabled',
        help_text='Shows the visual Pod Builder (/builder/) and the link on the home page.')
    compose_import_timeout = models.PositiveSmallIntegerField(
        default=10,
        verbose_name='Compose Import Timeout (seconds)',
        help_text='Maximum processing time for a Compose import. 0 = no limit.',
    )

    # EN variants
    brand_name_en = models.CharField(max_length=100, blank=True, default='Podman Kube Generator', verbose_name='[EN] Brand name')
    brand_tagline_en = models.CharField(max_length=200, blank=True, default='podman play kube · systemd quadlet', verbose_name='[EN] Brand tagline')
    home_heading_en = models.CharField(max_length=200, blank=True, default='Podman Pod Generator', verbose_name='[EN] Homepage H1 heading')
    home_intro_en = models.TextField(blank=True, default='Configure your pod — get ready-to-use Kubernetes YAML for podman play kube.', verbose_name='[EN] Homepage intro text')

    class Meta:
        verbose_name = 'Website Settings'
        verbose_name_plural = 'Website Settings'

    def __str__(self):
        return 'Website Settings'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class CookieBannerSettings(models.Model):
    POSITION_CHOICES = [
        ('bottom', 'Bottom (Bar)'),
        ('top', 'Top (Bar)'),
        ('modal', 'Center (Modal)'),
    ]

    enabled = models.BooleanField(default=False, verbose_name='Banner enabled')
    position = models.CharField(max_length=10, choices=POSITION_CHOICES, default='bottom', verbose_name='Position')
    title = models.CharField(max_length=200, default='Cookies & Privacy', verbose_name='Title')
    text = models.TextField(
        default='This website uses cookies for analytics. By clicking "Accept all" you agree to this.',
        verbose_name='Description text',
    )
    accept_label = models.CharField(max_length=80, default='Accept all', verbose_name='Button: Accept all')
    decline_label = models.CharField(max_length=80, default='Essential only', verbose_name='Button: Decline')
    show_decline_button = models.BooleanField(default=True, verbose_name='Show decline button')
    privacy_url = models.URLField(blank=True, verbose_name='Privacy URL', help_text='Optional link to the privacy policy')
    privacy_label = models.CharField(max_length=80, default='Privacy Policy', verbose_name='Privacy link text')
    analytics_label = models.CharField(max_length=80, default='Analytics', verbose_name='Category: Analytics — label')
    analytics_description = models.TextField(
        default='Helps us understand how visitors use the site (anonymised, no cross-site tracking).',
        verbose_name='Category: Analytics — description',
    )
    lifetime_days = models.PositiveSmallIntegerField(default=365, verbose_name='Cookie lifetime (days)')

    # English translations (empty = DE value used as fallback)
    title_en = models.CharField(max_length=200, blank=True, default='Cookies & Privacy', verbose_name='[EN] Title')
    text_en = models.TextField(blank=True, default='This website uses cookies for analytics. By clicking "Accept all" you agree to this.', verbose_name='[EN] Description text')
    accept_label_en = models.CharField(max_length=80, blank=True, default='Accept all', verbose_name='[EN] Button: Accept all')
    decline_label_en = models.CharField(max_length=80, blank=True, default='Essential only', verbose_name='[EN] Button: Decline')
    privacy_label_en = models.CharField(max_length=80, blank=True, default='Privacy Policy', verbose_name='[EN] Privacy link text')
    analytics_label_en = models.CharField(max_length=80, blank=True, default='Analytics', verbose_name='[EN] Category: Analytics — label')
    analytics_description_en = models.TextField(blank=True, default='Helps us understand how visitors use the site (anonymised, no cross-site tracking).', verbose_name='[EN] Category: Analytics — description')

    class Meta:
        verbose_name = 'Cookie Banner'
        verbose_name_plural = 'Cookie Banner'

    def __str__(self):
        return 'Cookie Banner'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class FooterLink(models.Model):
    label = models.CharField(max_length=80, verbose_name='Label')
    url = models.URLField(verbose_name='URL')
    icon = models.CharField(max_length=60, default='bi-github', verbose_name='Bootstrap Icon class', help_text='e.g. bi-github, bi-house, bi-globe2')
    sort_order = models.PositiveSmallIntegerField(default=0, verbose_name='Sort order')
    is_active = models.BooleanField(default=True, verbose_name='Active')
    open_new_tab = models.BooleanField(default=True, verbose_name='Open in new tab')

    class Meta:
        ordering = ['sort_order', 'pk']
        verbose_name = 'Navbar Link'
        verbose_name_plural = 'Navbar Links'

    def __str__(self):
        return self.label


class TOTPDevice(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='totp_device')
    secret = models.CharField(max_length=64)
    confirmed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'TOTP Device'
        verbose_name_plural = 'TOTP Devices'

    def __str__(self):
        return f'TOTP for {self.user.username} ({"active" if self.confirmed else "unconfirmed"})'


class SavedConfig(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=100)
    yaml_content = models.TextField()
    form_data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class UserStack(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='community_stacks')
    name = models.CharField(max_length=100, verbose_name='Name')
    description = models.CharField(max_length=300, blank=True, verbose_name='Description')
    icon = models.CharField(max_length=60, default='bi-box', verbose_name='Icon', help_text='Bootstrap Icons class, e.g. bi-database')
    category = models.CharField(max_length=50, blank=True, default='', verbose_name='Category', help_text='e.g. Database, CMS, Monitoring')
    form_data = models.JSONField()
    is_approved = models.BooleanField(default=False, verbose_name='Approved')
    view_count = models.PositiveIntegerField(default=0, verbose_name='View count')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Community Stack'
        verbose_name_plural = 'Community Stacks'

    def __str__(self):
        return f'{self.user.username} / {self.name}'


class StackLike(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stack_likes')
    stack = models.ForeignKey(UserStack, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'stack')
        verbose_name = 'Stack Like'
        verbose_name_plural = 'Stack Likes'

    def __str__(self):
        return f'{self.user.username} → {self.stack.name}'


class StackComment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stack_comments')
    stack = models.ForeignKey(UserStack, on_delete=models.CASCADE, related_name='comments')
    body = models.CharField(max_length=1000, verbose_name='Comment')
    is_approved = models.BooleanField(default=True, verbose_name='Visible')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Stack Comment'
        verbose_name_plural = 'Stack Comments'

    def __str__(self):
        return f'{self.user.username} @ {self.stack.name}: {self.body[:40]}'


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    bio = models.CharField(max_length=300, blank=True, verbose_name='About me')
    avatar = models.CharField(max_length=200, blank=True, verbose_name='Avatar', help_text='Local path (set automatically on upload).')
    avatar_url = models.URLField(blank=True, verbose_name='Avatar URL (external)', help_text='Direct link to an external image. Ignored if an uploaded avatar exists.')
    website = models.URLField(blank=True, verbose_name='Website')
    github = models.CharField(max_length=100, blank=True, verbose_name='GitHub username')
    twitter = models.CharField(max_length=100, blank=True, verbose_name='X / Twitter username')
    mastodon = models.CharField(max_length=200, blank=True, verbose_name='Mastodon', help_text='e.g. @user@mastodon.social')
    linkedin = models.CharField(max_length=100, blank=True, verbose_name='LinkedIn username')

    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f'Profile of {self.user.username}'

    def get_avatar_url(self):
        if self.avatar:
            return f'/media/{self.avatar}'
        return self.avatar_url or ''


class RegistrationSettings(models.Model):
    registration_enabled = models.BooleanField(default=True, verbose_name='Registration enabled')
    email_activation = models.BooleanField(
        default=False,
        verbose_name='Enable email activation',
        help_text='Users receive an activation link by email. Disabled = manual activation by admin.',
    )
    password_reset_enabled = models.BooleanField(
        default=False,
        verbose_name='Enable password reset',
        help_text='Shows "Forgot password?" link on the login page. Requires working SMTP.',
    )
    email_from = models.EmailField(
        default='noreply@example.com',
        verbose_name='Sender email',
        help_text='Sender of activation emails. SMTP is configured under "Email Settings".',
    )

    class Meta:
        verbose_name = 'Registration Settings'
        verbose_name_plural = 'Registration Settings'

    def __str__(self):
        return 'Registration Settings'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class GeneratedYAML(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    mode = models.CharField(max_length=10, default='rootless')
    pod_name = models.CharField(max_length=200, blank=True, default='')
    container_count = models.PositiveSmallIntegerField(default=1)
    init_count = models.PositiveSmallIntegerField(default=0)
    images = models.CharField(max_length=1000, blank=True, default='')
    ip = models.CharField(max_length=45, blank=True, default='')

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Generated YAML'
        verbose_name_plural = 'Generated YAMLs'

    def __str__(self):
        return f'{self.timestamp:%Y-%m-%d %H:%M} [{self.mode}] {self.container_count}c'


class EmailSettings(models.Model):
    host = models.CharField(max_length=200, blank=True, verbose_name='SMTP server', help_text='e.g. mail.example.com')
    port = models.PositiveSmallIntegerField(default=587, verbose_name='Port')
    use_tls = models.BooleanField(default=True, verbose_name='Use STARTTLS')
    use_ssl = models.BooleanField(default=False, verbose_name='Use SSL/TLS (port 465)')
    username = models.CharField(max_length=200, blank=True, verbose_name='Username')
    password = models.CharField(max_length=200, blank=True, verbose_name='Password')
    from_email = models.CharField(
        max_length=200, blank=True,
        verbose_name='Sender',
        help_text='e.g. "Podman Kube Generator <noreply@example.com>"',
    )
    admin_email = models.EmailField(
        blank=True,
        verbose_name='Admin email',
        help_text='Recipient for notifications (new registrations). Empty = no admin emails.',
    )

    class Meta:
        verbose_name = 'Email Settings'
        verbose_name_plural = 'Email Settings'

    def __str__(self):
        return 'E-Mail-Einstellungen'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class SavedConfigVersion(models.Model):
    config = models.ForeignKey(SavedConfig, on_delete=models.CASCADE, related_name='versions')
    yaml_content = models.TextField()
    form_data = models.JSONField()
    label = models.CharField(max_length=100, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Config Version'
        verbose_name_plural = 'Config Versions'

    def __str__(self):
        return f'{self.config.name} @ {self.created_at:%Y-%m-%d %H:%M}'


class StackCollection(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='collections')
    name = models.CharField(max_length=100, verbose_name='Name')
    description = models.CharField(max_length=300, blank=True, verbose_name='Description')
    is_public = models.BooleanField(default=False, verbose_name='Public')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Stack Collection'
        verbose_name_plural = 'Stack Collections'

    def __str__(self):
        return f'{self.user.username} / {self.name}'


class StackCollectionItem(models.Model):
    collection = models.ForeignKey(StackCollection, on_delete=models.CASCADE, related_name='items')
    saved_config = models.ForeignKey(SavedConfig, on_delete=models.CASCADE, related_name='collection_items')
    note = models.CharField(max_length=200, blank=True, verbose_name='Note')
    position = models.PositiveSmallIntegerField(default=0)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['position', 'added_at']
        unique_together = ('collection', 'saved_config')
        verbose_name = 'Collection Item'
        verbose_name_plural = 'Collection Items'

    def __str__(self):
        return f'{self.collection.name} → {self.saved_config.name}'
