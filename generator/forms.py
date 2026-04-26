import re
from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordResetForm as DjangoPasswordResetForm
from django.contrib.auth.models import User

_K8S_NAME_RE = re.compile(r'^[a-z0-9][a-z0-9\-]*[a-z0-9]$|^[a-z0-9]$')

RESTART_CHOICES = [
    ('Always', 'Always'),
    ('OnFailure', 'OnFailure'),
    ('Never', 'Never'),
]

GPU_ACCESS_CHOICES = [
    ('', '— None —'),
    ('nvidia', 'NVIDIA GPU (CDI)'),
    ('amd_rocm', 'AMD GPU – ROCm (CDI)'),
    ('vaapi', 'Intel / AMD – VAAPI (/dev/dri)'),
    ('webcam', 'Webcam (/dev/video0)'),
    ('custom', 'Custom device'),
]

PULL_POLICY_CHOICES = [
    ('', '— Default (IfNotPresent) —'),
    ('IfNotPresent', 'IfNotPresent'),
    ('Always', 'Always'),
    ('Never', 'Never'),
]

USERNS_CHOICES = [
    ('', '— none —'),
    ('keep-id', 'keep-id (rootless: same UID/GID)'),
    ('auto', 'auto (assign dynamically)'),
    ('host', 'host (no user namespace)'),
]

QUADLET_AUTO_UPDATE_CHOICES = [
    ('', 'off'),
    ('registry', 'registry (pull new image on update)'),
    ('local', 'local (rebuild from local image)'),
]

QUADLET_LOG_DRIVER_CHOICES = [
    ('', '— default —'),
    ('journald', 'journald'),
    ('k8s-file', 'k8s-file'),
    ('none', 'none'),
    ('passthrough', 'passthrough'),
]

QUADLET_EXIT_CODE_CHOICES = [
    ('', '— none —'),
    ('all', 'all (exit 0 only if all containers exit 0)'),
    ('any', 'any (exit 0 if any container exits 0)'),
]

QUADLET_IMAGE_PRUNE_CHOICES = [
    ('', 'off'),
    ('weekly', 'weekly'),
    ('monthly', 'monthly'),
    ('daily', 'daily'),
]

QUADLET_IMAGE_PRUNE_KEEP_CHOICES = [
    ('', 'Remove all unused'),
    ('168', 'Keep last 7 days'),
    ('336', 'Keep last 14 days'),
    ('720', 'Keep last 30 days'),
]

MODE_CHOICES = [
    ('rootless', 'Rootless (recommended, regular user)'),
    ('rootful', 'Rootful (root / sudo)'),
]


class PodForm(forms.Form):
    pod_name = forms.CharField(
        label='Pod Name',
        max_length=63,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. myapp'}),
    )
    deploy_user = forms.CharField(
        label='Deploy as user',
        max_length=64,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. nextcloud'}),
    )

    def clean_pod_name(self):
        name = self.cleaned_data['pod_name'].strip().lower().replace(' ', '-')
        if not _K8S_NAME_RE.match(name):
            raise forms.ValidationError(
                'Only lowercase letters, digits and hyphens allowed. Must start and end with a letter or digit.'
            )
        return name
    restart_policy = forms.ChoiceField(
        label='Restart Policy',
        choices=RESTART_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    mode = forms.ChoiceField(
        label='Mode',
        choices=MODE_CHOICES,
        initial='rootless',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    # Advanced pod options
    host_network = forms.BooleanField(
        label='hostNetwork (use host network)',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    host_pid = forms.BooleanField(
        label='hostPID (host PID namespace)',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    host_ipc = forms.BooleanField(
        label='hostIPC (host IPC namespace)',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    hostname = forms.CharField(
        label='Hostname (optional)',
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'mypod'}),
    )
    host_aliases = forms.CharField(
        label='Host aliases (/etc/hosts entries, one per line: IP hostname)',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control font-monospace', 'rows': 3,
            'placeholder': '10.0.0.1 db.internal\n10.0.0.2 cache.internal',
        }),
    )
    userns = forms.ChoiceField(
        label='User namespace (Podman annotation)',
        choices=USERNS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    dns = forms.CharField(
        label='DNS servers (optional, one per line)',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control font-monospace', 'rows': 2,
            'placeholder': '8.8.8.8\n8.8.4.4',
        }),
    )
    network = forms.CharField(
        label='Network (optional)',
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. podman-net (empty = default)',
        }),
    )
    supplemental_groups = forms.CharField(
        label='Supplemental Groups (one GID per line)',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control font-monospace', 'rows': 2,
            'placeholder': '44\n109',
        }),
    )
    image_pull_secrets = forms.CharField(
        label='imagePullSecrets (one secret name per line)',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control font-monospace', 'rows': 2,
            'placeholder': 'my-registry-secret',
        }),
    )
    termination_grace_period = forms.IntegerField(
        label='terminationGracePeriodSeconds',
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 60'}),
    )
    # Quadlet options
    quadlet_auto_update = forms.ChoiceField(
        label='Auto-Update',
        choices=QUADLET_AUTO_UPDATE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    quadlet_log_driver = forms.ChoiceField(
        label='Log Driver',
        choices=QUADLET_LOG_DRIVER_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    quadlet_exit_code_propagation = forms.ChoiceField(
        label='Exit Code Propagation',
        choices=QUADLET_EXIT_CODE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    quadlet_kube_down_force = forms.BooleanField(
        label='KubeDownForce (force remove on stop)',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    quadlet_timeout_start = forms.IntegerField(
        label='Timeout Start (seconds)',
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 120'}),
    )
    quadlet_image_prune = forms.ChoiceField(
        label='Image Prune Timer',
        choices=QUADLET_IMAGE_PRUNE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    quadlet_image_prune_keep = forms.ChoiceField(
        label='Keep images for',
        choices=QUADLET_IMAGE_PRUNE_KEEP_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )


PROBE_TYPE_CHOICES = [
    ('exec', 'exec (command)'),
    ('httpGet', 'HTTP GET'),
    ('tcpSocket', 'TCP Socket'),
]


class ContainerForm(forms.Form):
    name = forms.CharField(
        label='Container name',
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. webserver'}),
    )
    image = forms.CharField(
        label='Image',
        max_length=300,
        widget=forms.HiddenInput(),
    )
    pull_policy = forms.ChoiceField(
        label='Image Pull Policy',
        choices=PULL_POLICY_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    ports = forms.CharField(
        label='Ports (host:container, one per line)',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control font-monospace', 'rows': 3,
            'placeholder': '8080:80\n443:443',
        }),
    )
    env = forms.CharField(
        label='Environment variables (KEY=value)',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control font-monospace', 'rows': 3,
            'placeholder': 'DB_HOST=localhost\nDB_PORT=5432',
        }),
    )
    volumes = forms.CharField(
        label='Volumes (name:/container/path)',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control font-monospace', 'rows': 3,
            'placeholder': 'mydata:/var/lib/mysql\nwwwdata:/var/www/html',
        }),
    )
    command = forms.CharField(
        label='Command (overrides ENTRYPOINT)',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control font-monospace',
            'placeholder': '/bin/sh',
        }),
    )
    args = forms.CharField(
        label='Args (overrides CMD)',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control font-monospace',
            'placeholder': '--config.file=/etc/prometheus/prometheus.yml',
        }),
    )
    # Ressourcen
    memory_limit = forms.CharField(
        label='Memory Limit',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '512Mi'}),
    )
    cpu_limit = forms.CharField(
        label='CPU Limit',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '0.5'}),
    )
    memory_request = forms.CharField(
        label='Memory Request',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '128Mi'}),
    )
    cpu_request = forms.CharField(
        label='CPU Request',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '0.1'}),
    )
    # Security Context
    run_as_user = forms.IntegerField(
        label='Run as UID',
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 999'}),
    )
    run_as_group = forms.IntegerField(
        label='runAsGroup',
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '1000'}),
    )
    read_only_root = forms.BooleanField(
        label='readOnlyRootFilesystem',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    privileged = forms.BooleanField(
        label='privileged',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    cap_add = forms.CharField(
        label='Add capabilities (one per line)',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control font-monospace', 'rows': 2,
            'placeholder': 'NET_ADMIN\nSYS_TIME',
        }),
    )
    cap_drop = forms.CharField(
        label='Drop capabilities (one per line)',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control font-monospace', 'rows': 2,
            'placeholder': 'NET_RAW\nMKNOD',
        }),
    )
    userns = forms.ChoiceField(
        label='User Namespace (--userns)',
        choices=USERNS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    # GPU / Hardware
    gpu_access = forms.ChoiceField(
        label='GPU / Hardware Access',
        choices=GPU_ACCESS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    gpu_count = forms.ChoiceField(
        label='GPU count',
        choices=[('1', '1'), ('2', '2'), ('4', '4'), ('all', 'all')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    custom_device = forms.CharField(
        label='Device path (host:container)',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm font-monospace',
            'placeholder': '/dev/dri/renderD128:/dev/dri/renderD128',
        }),
    )
    devices = forms.CharField(
        label='Devices',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control form-control-sm font-monospace',
            'rows': 3,
            'placeholder': '/dev/ttyUSB0\n/dev/video0:/dev/video0',
        }),
    )
    allow_privilege_escalation = forms.ChoiceField(
        label='allowPrivilegeEscalation',
        choices=[('', '— default —'), ('false', 'false (recommended)'), ('true', 'true')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    pre_stop_cmd = forms.CharField(
        label='preStop command',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm font-monospace',
            'placeholder': 'e.g. pg_ctl stop -m fast',
        }),
    )
    # Liveness Probe
    liveness_probe_type = forms.ChoiceField(
        label='Type',
        choices=PROBE_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    liveness_probe_cmd = forms.CharField(
        label='Command',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm font-monospace',
            'placeholder': 'pg_isready -U postgres',
        }),
    )
    liveness_http_path = forms.CharField(
        label='HTTP Path',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': '/health'}),
    )
    liveness_http_port = forms.IntegerField(
        label='Port',
        required=False,
        min_value=1, max_value=65535,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'placeholder': '8080'}),
    )
    liveness_tcp_port = forms.IntegerField(
        label='TCP Port',
        required=False,
        min_value=1, max_value=65535,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'placeholder': '5432'}),
    )
    liveness_initial_delay = forms.IntegerField(
        label='Initial Delay (s)',
        required=False,
        min_value=0,
        initial=30,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'placeholder': '30'}),
    )
    liveness_period = forms.IntegerField(
        label='Period (s)',
        required=False,
        min_value=1,
        initial=10,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'placeholder': '10'}),
    )
    liveness_failure_threshold = forms.IntegerField(
        label='Failure Threshold',
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'placeholder': '3'}),
    )
    # Readiness Probe
    readiness_probe_type = forms.ChoiceField(
        label='Type',
        choices=PROBE_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    readiness_probe_cmd = forms.CharField(
        label='Command',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm font-monospace',
            'placeholder': 'pg_isready -U postgres',
        }),
    )
    readiness_http_path = forms.CharField(
        label='HTTP Path',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': '/health'}),
    )
    readiness_http_port = forms.IntegerField(
        label='Port',
        required=False,
        min_value=1, max_value=65535,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'placeholder': '8080'}),
    )
    readiness_tcp_port = forms.IntegerField(
        label='TCP Port',
        required=False,
        min_value=1, max_value=65535,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'placeholder': '5432'}),
    )
    readiness_initial_delay = forms.IntegerField(
        label='Initial Delay (s)',
        required=False,
        min_value=0,
        initial=10,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'placeholder': '10'}),
    )
    readiness_period = forms.IntegerField(
        label='Period (s)',
        required=False,
        min_value=1,
        initial=10,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'placeholder': '10'}),
    )
    readiness_failure_threshold = forms.IntegerField(
        label='Failure Threshold',
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'placeholder': '3'}),
    )
    # Working Dir
    working_dir = forms.CharField(
        label='Working Directory (optional)',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '/app'}),
    )


class InitContainerForm(forms.Form):
    """Vereinfachtes Formular für Init-Container."""
    name = forms.CharField(
        label='Name',
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'init-db'}),
    )
    image = forms.CharField(
        label='Image',
        max_length=300,
        widget=forms.HiddenInput(),
    )
    command = forms.CharField(
        label='Command (overrides ENTRYPOINT)',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control font-monospace',
            'placeholder': 'sh',
        }),
    )
    args = forms.CharField(
        label='Args (overrides CMD)',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control font-monospace',
            'placeholder': '-c "until pg_isready; do sleep 1; done"',
        }),
    )
    volumes = forms.CharField(
        label='Volumes (name:/container/path)',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control font-monospace', 'rows': 2,
            'placeholder': 'mydata:/data',
        }),
    )
    env = forms.CharField(
        label='Environment variables (KEY=value)',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control font-monospace', 'rows': 2,
            'placeholder': 'DB_HOST=localhost',
        }),
    )
    run_always = forms.BooleanField(
        label='Always run (also on pod restart)',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Default: once on first start',
    )


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email address'}),
    )
    tos_accepted = forms.BooleanField(
        required=True,
        label='',
        error_messages={'required': 'You must accept the terms of service.'},
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name != 'tos_accepted':
                field.widget.attrs.setdefault('class', 'form-control')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.is_active = False
        if commit:
            user.save()
        return user


class AppPasswordResetForm(DjangoPasswordResetForm):
    """PasswordResetForm das send_app_mail statt Django-SMTP nutzt."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].widget.attrs['class'] = 'form-control'

    def send_mail(self, subject_template_name, email_template_name, context,
                  from_email, to_email, html_email_template_name=None):
        from .mail import send_app_mail, mail_password_reset
        reset_url = context.get('protocol', 'https') + '://' + context.get('domain', '') + \
                    '/password-reset/confirm/' + context['uid'] + '/' + context['token'] + '/'
        subject, html = mail_password_reset(context['user'].username, reset_url)
        send_app_mail(subject=subject, body=html, recipient_list=[to_email])
