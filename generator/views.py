import json
import re
import secrets
import signal
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse, Http404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import models
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from .mail import send_app_mail, mail_activation, mail_account_activated, mail_new_registration, mail_new_stack, mail_new_comment
from django_ratelimit.decorators import ratelimit

from .forms import PodForm, ContainerForm, InitContainerForm, RegistrationForm
from .kube import generate
from .shell import generate_shell
from .quadlet import generate_quadlet
from .models import SavedConfig, StackTemplate, ImpressumSettings, SiteSettings, UserStack, RegistrationSettings, UserProfile, StackLike, StackComment
from .registry import search_images, get_tags, get_hub_info, get_tag_vulns
from .presets import get_preset, fetch_registry_all
from .stacks import CONNECTION_HINTS


_VALID_USERNS = {'auto', 'keep-id', 'nomap', 'private', 'host'}
_DB_IMAGES = {'mariadb', 'mysql', 'postgres', 'postgresql', 'mongodb', 'mongo', 'redis', 'valkey'}
_DB_ENV_KEYS = {
    'mysql':    ['MYSQL_DATABASE', 'MYSQL_USER', 'MYSQL_PASSWORD'],
    'mariadb':  ['MARIADB_DATABASE', 'MARIADB_USER', 'MARIADB_PASSWORD'],
    'postgres': ['POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD'],
}


def _img_base(img):
    return (img or '').lower().split(':')[0].split('/')[-1]


def generate_env_file(form_data):
    """Collects all env vars from all containers and returns a .env file string."""
    pod_name = (form_data.get('pod_name') or 'pod').strip()
    lines = [f'# .env — {pod_name}', '']
    all_containers = list(form_data.get('init_containers', [])) + list(form_data.get('containers', []))
    seen_keys = set()
    for c in all_containers:
        cname = c.get('name', '')
        env_raw = c.get('env', '') or ''
        env_lines = [l.strip() for l in env_raw.splitlines() if l.strip() and '=' in l and not l.strip().startswith('#')]
        if not env_lines:
            continue
        lines.append(f'# --- {cname} ---')
        for line in env_lines:
            k = line.partition('=')[0].strip()
            if k not in seen_keys:
                seen_keys.add(k)
                lines.append(line)
            else:
                lines.append(f'# {line}  # duplicate key')
        lines.append('')
    if not seen_keys:
        lines.append('# No environment variables defined.')
    return '\n'.join(lines)


def _parse_env_str(raw):
    """Parst 'KEY=VALUE\\n...' → {key: value}"""
    result = {}
    for line in (raw or '').splitlines():
        line = line.strip()
        if '=' in line:
            k, _, v = line.partition('=')
            result[k.strip()] = v.strip()
    return result


def validate_form_data(form_data):
    """
    Gibt Liste von Warnungen zurück.
    Jede Warnung: {'level': 'error'|'warning', 'msg': str, 'hint': str, 'suggestion': str}
    """
    warnings = []
    containers = form_data.get('containers', [])
    mode = form_data.get('mode', 'rootless')

    def is_db(img):
        return _img_base(img) in _DB_IMAGES

    # 1. Host port conflict → pod fails to start
    host_ports = {}
    for c in containers:
        for line in (c.get('ports') or '').splitlines():
            line = line.strip()
            if ':' in line:
                try:
                    hp = int(line.split(':')[0].rsplit('.', 1)[-1])  # handle ip:port form
                    if hp in host_ports:
                        warnings.append({
                            'level': 'error',
                            'msg': f'Host port <strong>{hp}</strong> is used by both '
                                   f'<code>{host_ports[hp]}</code> and <code>{c.get("name")}</code> '
                                   f'— pod will not start',
                            'hint': f'hostPort: {hp}',
                            'suggestion': f'Change one of the host ports, e.g.:\n  hostPort: {hp + 1}',
                        })
                    else:
                        host_ports[hp] = c.get('name', '')
                    # Privileged port in rootless mode → cannot bind
                    if hp < 1024 and mode == 'rootless':
                        warnings.append({
                            'level': 'error',
                            'msg': f'<code>{c.get("name")}</code>: host port <strong>{hp}</strong> is a '
                                   f'privileged port — rootless podman cannot bind ports below 1024',
                            'hint': f'hostPort: {hp}',
                            'suggestion': (
                                f'Options:\n'
                                f'  a) Use a port ≥ 1024 (e.g. {hp + 1000})\n'
                                f'  b) Switch to rootful mode\n'
                                f'  c) Allow unprivileged binding:\n'
                                f'     echo "net.ipv4.ip_unprivileged_port_start={hp}" | sudo tee -a /etc/sysctl.conf\n'
                                f'     sudo sysctl -p'
                            ),
                        })
                except ValueError:
                    pass

    # 2. Invalid userns value → podman play kube fails
    _userns_hint = (
        'Valid values:\n'
        '  auto                      — Podman assigns a UID range\n'
        '  keep-id                   — host UID = container UID\n'
        '  keep-id:uid=1000:gid=1000 — custom UID/GID mapping\n'
        '  nomap                     — no UID mapping\n'
        '  private                   — new user namespace (default)'
    )
    userns = form_data.get('userns', '').strip()
    if userns:
        base = userns.split(':')[0]
        if base not in _VALID_USERNS:
            warnings.append({
                'level': 'error',
                'msg': f'Invalid <code>userns</code> value: <code>{userns}</code> — '
                       f'<code>podman play kube</code> will fail',
                'hint': f'io.podman.annotations.userns: {userns}',
                'suggestion': _userns_hint,
            })
    for c in containers:
        c_userns = (c.get('userns') or '').strip()
        if c_userns:
            base = c_userns.split(':')[0]
            if base not in _VALID_USERNS:
                warnings.append({
                    'level': 'error',
                    'msg': f'<code>{c.get("name")}</code>: invalid <code>userns</code> value: <code>{c_userns}</code>',
                    'hint': f'io.podman.annotations.userns/{c.get("name")}: {c_userns}',
                    'suggestion': _userns_hint,
                })

    # 3. DB type mismatch → connection fails at runtime
    _DB_IMAGE_SUGGEST = {
        'mysql':    'docker.io/mysql:latest',
        'mariadb':  'docker.io/mariadb:latest',
        'postgres': 'docker.io/postgres:latest',
    }
    db_cs  = [c for c in containers if is_db(c.get('image', ''))]
    app_cs = [c for c in containers if not is_db(c.get('image', ''))]

    for db_c in db_cs:
        db_type = _img_base(db_c.get('image', ''))
        for app_c in app_cs:
            env_keys = set(_parse_env_str(app_c.get('env', '')).keys())
            for dtype, keys in _DB_ENV_KEYS.items():
                if any(k in env_keys for k in keys) and dtype != db_type:
                    # mysql ↔ mariadb are fully compatible (same env vars, wire-compatible)
                    if {dtype, db_type} <= {'mysql', 'mariadb'}:
                        continue
                    correct_img = _DB_IMAGE_SUGGEST.get(dtype, dtype)
                    warnings.append({
                        'level': 'error',
                        'msg': f'<code>{app_c.get("name")}</code> expects '
                               f'<strong>{dtype}</strong> but <code>{db_c.get("name")}</code> '
                               f'is <strong>{db_type}</strong> — connection will fail',
                        'hint': f'image: docker.io/{db_type}',
                        'suggestion': f'Replace the DB image with:\n  image: {correct_img}',
                    })

    # 4. DB container without volume → data loss on restart
    for c in db_cs:
        vols = (c.get('volumes') or '').strip()
        if not vols:
            db_name = _img_base(c.get('image', 'db'))
            warnings.append({
                'level': 'error',
                'msg': f'<code>{c.get("name")}</code> has no volume — '
                       f'all database data will be lost on every restart',
                'hint': f'name: {c.get("name")}',
                'suggestion': (
                    f'Add a persistent volume:\n'
                    f'  volumeMounts:\n'
                    f'    - name: {db_name}-data\n'
                    f'      mountPath: /var/lib/data\n\n'
                    f'  volumes:\n'
                    f'    - name: {db_name}-data\n'
                    f'      persistentVolumeClaim:\n'
                    f'        claimName: {db_name}-data'
                ),
            })

    # 5. privileged in rootless mode → not allowed
    for c in containers:
        if c.get('privileged') and mode == 'rootless':
            warnings.append({
                'level': 'error',
                'msg': f'<code>{c.get("name")}</code>: <code>privileged: true</code> '
                       f'is not allowed in rootless mode',
                'hint': 'privileged: true',
                'suggestion': (
                    'Options:\n'
                    '  a) Switch to rootful mode\n'
                    '  b) Remove privileged and add only the\n'
                    '     capabilities the container actually needs:\n'
                    '     capabilities:\n'
                    '       add: [NET_ADMIN]'
                ),
            })


    # 7. :latest tag on DB containers → uncontrolled major version upgrades
    _DB_VERSIONS = {'mysql': '8.0', 'mariadb': '11', 'postgres': '16', 'postgresql': '16',
                    'mongodb': '7', 'mongo': '7', 'redis': '7', 'valkey': '8'}
    for c in db_cs:
        img = c.get('image', '')
        if img.endswith(':latest') or ':' not in img.split('/')[-1]:
            db_name = _img_base(img)
            stable = _DB_VERSIONS.get(db_name, 'stable')
            warnings.append({
                'level': 'warning',
                'msg': f'<code>{c.get("name")}</code>: <code>:latest</code> on a database image '
                       f'is risky — a major version upgrade can make data unreadable',
                'hint': f'image: {img}',
                'suggestion': (
                    f'Pin a specific version:\n'
                    f'  image: docker.io/{db_name}:{stable}\n\n'
                    f'Major upgrades (e.g. MySQL 8→9, PostgreSQL 15→16)\n'
                    f'require manual data migration and can permanently\n'
                    f'break the pod if pulled automatically.'
                ),
            })

    # 8. :latest on non-DB containers (skip if image is empty)
    for c in containers:
        img = c.get('image', '')
        if not img.strip():
            warnings.append({
                'level': 'error',
                'msg': f'<code>{c.get("name")}</code>: no image specified — pod will not start',
                'hint': 'image: (empty)',
                'suggestion': 'Set an image, e.g.:\n  image: docker.io/library/nginx:alpine',
            })
            continue

    # 9. ZBX_DB_TYPE set but DB connection vars missing → proxy cannot connect
    for c in containers:
        env_map = _parse_env_str(c.get('env', ''))
        db_type_val = env_map.get('ZBX_DB_TYPE', '').lower()
        if db_type_val in ('mysql', 'postgresql') :
            missing = [k for k in ('ZBX_DB_HOST', 'ZBX_DB_NAME', 'ZBX_DB_USER', 'ZBX_DB_PASSWORD')
                       if k not in env_map]
            if missing:
                warnings.append({
                    'level': 'error',
                    'msg': f'<code>{c.get("name")}</code>: <code>ZBX_DB_TYPE={db_type_val}</code> '
                           f'is set but DB connection vars are missing: '
                           f'{", ".join(f"<code>{k}</code>" for k in missing)}',
                    'hint': 'ZBX_DB_TYPE',
                    'suggestion': (
                        'Add the missing env vars:\n'
                        + '\n'.join(f'  - name: {k}\n    value: <value>' for k in missing)
                    ),
                })

    # 10. DB port exposed via hostPort — usually not needed inside pod
    _DB_PORTS = {3306, 5432, 5433, 27017, 6379, 11211, 9042, 1433, 1521}
    for c in db_cs:
        for line in (c.get('ports') or '').splitlines():
            line = line.strip()
            if ':' in line:
                try:
                    hp = int(line.split(':')[0])
                    if hp in _DB_PORTS:
                        warnings.append({
                            'level': 'warning',
                            'msg': f'<code>{c.get("name")}</code>: DB port '
                                   f'<code>{hp}</code> is exposed to the host — '
                                   f'only needed for external access',
                            'hint': f'hostPort: {hp}',
                            'suggestion': (
                                f'Within the pod all containers share localhost.\n'
                                f'Remove hostPort {hp} unless you need to access\n'
                                f'the DB from outside the pod (e.g. for migrations):\n\n'
                                f'  # Delete or comment out:\n'
                                f'  # - hostPort: {hp}\n'
                                f'  #   containerPort: {hp}'
                            ),
                        })
                except ValueError:
                    pass

    # 11. Container name used as hostname in another container's env → works, but fragile if renamed
    _NON_HOST_KEY_RE = re.compile(r'DATABASE|DB_NAME|DBNAME|_NAME$|_USER$|_DB$|PASSWORD|SECRET|KEY|TOKEN', re.IGNORECASE)
    container_names = {c.get('name', '').strip() for c in containers if c.get('name')}
    for c in containers:
        env_map = _parse_env_str(c.get('env', ''))
        for key, val in env_map.items():
            if val in container_names and val != c.get('name', '').strip() and not _NON_HOST_KEY_RE.search(key):
                warnings.append({
                    'level': 'warning',
                    'msg': f'<code>{c.get("name")}</code>: env <code>{key}={val}</code> — '
                           f'using a container name as hostname works inside the pod, '
                           f'but breaks if the container is renamed',
                    'hint': f'{key}: {val}',
                    'suggestion': (
                        f'This is fine as long as the container "{val}" keeps that name.\n'
                        f'Within a pod all containers share localhost (127.0.0.1),\n'
                        f'so the container name resolves via the pod\'s internal DNS.\n\n'
                        f'If you rename "{val}", update {key} here too.'
                    ),
                })

    # 12. Non-standard DB env var names → container will start but DB connection fails silently
    _ENV_ALIASES = {
        # MySQL / MariaDB
        'MYSQL_USERNAME':   'MYSQL_USER',
        'MYSQL_UNAME':      'MYSQL_USER',
        'MYSQL_PASS':       'MYSQL_PASSWORD',
        'MYSQL_PASSWD':     'MYSQL_PASSWORD',
        'MYSQL_HOSTNAME':   'MYSQL_HOST',
        'MYSQL_DB':         'MYSQL_DATABASE',
        'MYSQL_DBNAME':     'MYSQL_DATABASE',
        'MARIADB_USERNAME': 'MARIADB_USER',
        'MARIADB_PASS':     'MARIADB_PASSWORD',
        'MARIADB_HOSTNAME': 'MARIADB_HOST',
        'MARIADB_DB':       'MARIADB_DATABASE',
        # PostgreSQL
        'POSTGRES_USERNAME': 'POSTGRES_USER',
        'POSTGRES_PASS':     'POSTGRES_PASSWORD',
        'POSTGRES_PASSWD':   'POSTGRES_PASSWORD',
        'POSTGRES_HOSTNAME': 'POSTGRES_HOST',
        'POSTGRES_DB_NAME':  'POSTGRES_DB',
        'POSTGRES_DBNAME':   'POSTGRES_DB',
    }
    for c in containers:
        env_map = _parse_env_str(c.get('env', ''))
        for bad_key, good_key in _ENV_ALIASES.items():
            if bad_key in env_map:
                warnings.append({
                    'level': 'warning',
                    'msg': f'<code>{c.get("name")}</code>: '
                           f'<code>{bad_key}</code> is not a standard env var — '
                           f'the DB image expects <code>{good_key}</code>',
                    'hint': bad_key,
                    'suggestion': (
                        f'Rename the env var:\n'
                        f'  {bad_key}  →  {good_key}\n\n'
                        f'The container will start without error but the DB\n'
                        f'connection will fail because the image ignores unknown env vars.'
                    ),
                    'fix': json.dumps({'type': 'rename_env_key', 'old_key': bad_key, 'new_key': good_key}),
                })

    # 13. Credential symmetry — app and DB container have different values for the same credential key
    _CRED_PAIRS = [
        (['MYSQL_USER', 'MYSQL_USERNAME'],     ['MYSQL_USER'],     'mysql'),
        (['MYSQL_PASSWORD', 'MYSQL_PASS'],     ['MYSQL_PASSWORD'], 'mysql'),
        (['MYSQL_DATABASE', 'MYSQL_DB'],       ['MYSQL_DATABASE'], 'mysql'),
        (['MARIADB_USER', 'MARIADB_USERNAME'], ['MARIADB_USER'],   'mariadb'),
        (['MARIADB_PASSWORD', 'MARIADB_PASS'], ['MARIADB_PASSWORD'], 'mariadb'),
        (['MARIADB_DATABASE', 'MARIADB_DB'],   ['MARIADB_DATABASE'], 'mariadb'),
        (['POSTGRES_USER', 'POSTGRES_USERNAME'], ['POSTGRES_USER'], 'postgres'),
        (['POSTGRES_PASSWORD', 'POSTGRES_PASS'], ['POSTGRES_PASSWORD'], 'postgres'),
        (['POSTGRES_DB', 'POSTGRES_DATABASE'],   ['POSTGRES_DB'],   'postgres'),
    ]
    for db_c in db_cs:
        db_env = _parse_env_str(db_c.get('env', ''))
        db_type = _img_base(db_c.get('image', ''))
        for app_c in app_cs:
            app_env = _parse_env_str(app_c.get('env', ''))
            for app_keys, db_keys, pair_type in _CRED_PAIRS:
                if pair_type not in db_type and db_type not in pair_type:
                    continue
                app_val = next((app_env[k] for k in app_keys if k in app_env), None)
                db_val  = next((db_env[k]  for k in db_keys  if k in db_env),  None)
                if app_val is not None and db_val is not None and app_val != db_val:
                    label = db_keys[0]
                    warnings.append({
                        'level': 'error',
                        'msg': f'<code>{app_c.get("name")}</code> and <code>{db_c.get("name")}</code>: '
                               f'<code>{label}</code> mismatch — '
                               f'<code>{app_val!r}</code> vs <code>{db_val!r}</code> — '
                               f'DB connection will fail',
                        'hint': label,
                        'suggestion': (
                            f'Both containers must use the same value for {label}:\n'
                            f'  {app_c.get("name")}: {app_val!r}\n'
                            f'  {db_c.get("name")}: {db_val!r}\n\n'
                            f'Pick one and update both containers.'
                        ),
                    })

    # 14. Placeholder / weak credential values
    import re as _re
    _PLACEHOLDER_RE = _re.compile(
        r'^('
        r'changeme|change_?me|change-me|'
        r'yourpassword|your_?pass(word)?|'
        r'enter_?here|<[^>]+>|\$\{[^}]+\}|'
        r'todo|fixme|example|dummy|'
        r'password|passwd|secret|'
        r'admin|root|test|123|1234|12345|123456'
        r')$',
        _re.IGNORECASE,
    )
    _CRED_KEYS_RE = _re.compile(
        r'(password|passwd|pass|secret|token|key|api_?key|auth)',
        _re.IGNORECASE,
    )
    _UNRESOLVED_RE = _re.compile(r'\$\{[^}]+\}|\$[A-Z_]{2,}')

    for c in containers:
        env_map = _parse_env_str(c.get('env', ''))
        for key, val in env_map.items():
            if not val:
                warnings.append({
                    'level': 'warning',
                    'msg': f'<code>{c.get("name")}</code>: <code>{key}</code> is empty',
                    'hint': key,
                    'suggestion': f'Set a value for {key}.',
                })
            elif _UNRESOLVED_RE.search(val):
                warnings.append({
                    'level': 'warning',
                    'msg': f'<code>{c.get("name")}</code>: <code>{key}={val}</code> — '
                           f'unresolved shell variable, podman will use the literal string',
                    'hint': key,
                    'suggestion': (
                        f'Replace the shell variable with the actual value:\n'
                        f'  {key}={val}  →  {key}=<actual value>\n\n'
                        f'podman play kube does not expand shell variables in env values.'
                    ),
                })
            elif _PLACEHOLDER_RE.match(val) and _CRED_KEYS_RE.search(key):
                warnings.append({
                    'level': 'warning',
                    'msg': f'<code>{c.get("name")}</code>: <code>{key}={val}</code> — '
                           f'looks like a placeholder or weak credential',
                    'hint': key,
                    'suggestion': (
                        f'Replace with a strong, unique value:\n'
                        f'  {key}={val}  →  {key}=<strong secret>\n\n'
                        f'Generate a random password:\n'
                        f'  openssl rand -base64 24'
                    ),
                })

    # 15. Host-Path volumes → UID/GID-Hinweis
    _SYSTEM_PATHS = {
        '/etc/localtime', '/etc/timezone', '/etc/hostname',
        '/etc/hosts', '/etc/resolv.conf',
        '/var/run/docker.sock', '/var/run/podman.sock',
        '/run/docker.sock', '/run/podman.sock',
    }
    host_path_containers = []
    host_path_dirs = []
    seen_host_dirs = set()
    for c in containers:
        for line in (c.get('volumes') or '').splitlines():
            line = line.strip()
            if not line or ':' not in line:
                continue
            src = line.split(':')[0]
            if (src.startswith('/') or src.startswith('~')) and src not in _SYSTEM_PATHS:
                last_seg = src.rstrip('/').rsplit('/', 1)[-1]
                if '.' not in last_seg:
                    if c.get('name', '') not in host_path_containers:
                        host_path_containers.append(c.get('name', ''))
                    if src not in seen_host_dirs:
                        host_path_dirs.append(src)
                        seen_host_dirs.add(src)
    if host_path_containers:
        names = ', '.join(f'<code>{n}</code>' for n in host_path_containers)
        unshare = 'podman unshare chown' if mode == 'rootless' else 'chown'
        mkdir_lines = '\n'.join(f'  mkdir -p {p}' for p in host_path_dirs)
        chown_lines = '\n'.join(f'  {unshare} UID:GID {p}' for p in host_path_dirs)
        warnings.append({
            'level': 'warning',
            'msg': f'{names}: uses host path volume — directory must exist and UID/GID must be set',
            'hint': 'hostPath volume',
            'suggestion': (
                f'Create the directories and set permissions before starting:\n'
                f'{mkdir_lines}\n\n'
                f'Set ownership (find UID/GID with: podman run --rm <image> id):\n'
                f'{chown_lines}\n\n'
                f'Named volumes (e.g. mydata:/path) are simpler — podman creates them\n'
                f'automatically with correct permissions.'
            ),
        })

    # 16. Double registry prefix — docker.io/ghcr.io/... or docker.io/quay.io/...
    _KNOWN_REGISTRIES = ('ghcr.io', 'quay.io', 'gcr.io', 'registry.k8s.io', 'lscr.io', 'registry.gitlab.com')
    for c in containers:
        img = (c.get('image') or '').strip()
        if img.startswith('docker.io/'):
            after = img[len('docker.io/'):]
            for reg in _KNOWN_REGISTRIES:
                if after.startswith(reg + '/') or after == reg:
                    fixed = after
                    warnings.append({
                        'level': 'error',
                        'msg': f'<code>{c.get("name")}</code>: image <code>{img}</code> has a double registry prefix — '
                               f'<code>docker.io/{reg}/…</code> does not exist on Docker Hub and will fail to pull',
                        'hint': f'image: {img}',
                        'suggestion': f'Remove the docker.io/ prefix:\n  image: {fixed}',
                    })
                    break

    # 17. Init container that polls a main-container service → deadlock in kube play
    # Init containers finish BEFORE main containers start — waiting for a service
    # in the same pod will loop forever.
    init_containers = form_data.get('init_containers', [])
    _POLL_CMDS = re.compile(
        r'\b(pg_isready|mysqladmin\s+ping|redis-cli\s+ping|curl\s|wget\s|nc\s|ncat\s|wait.for|wait_for|healthcheck)\b',
        re.IGNORECASE,
    )
    for ic in init_containers:
        ic_args = (ic.get('args') or '') + ' ' + (ic.get('command') or '')
        if _POLL_CMDS.search(ic_args):
            warnings.append({
                'level': 'error',
                'msg': f'Init container <code>{ic.get("name")}</code> appears to poll a service '
                       f'— this will deadlock in <code>podman kube play</code>: '
                       f'init containers run <strong>before</strong> main containers start',
                'hint': 'initContainers: (polling loop)',
                'suggestion': (
                    'Init containers cannot wait for services in the same pod.\n'
                    'Main containers start only AFTER all init containers finish.\n\n'
                    'Options:\n'
                    '  a) Remove the wait init container — let the app retry its\n'
                    '     own DB connection on startup (most apps do this already)\n'
                    '  b) Increase liveness/readiness probe failureThreshold on the\n'
                    '     app container to tolerate a slow-starting DB\n'
                    '  c) Use an init container only for one-time setup tasks\n'
                    '     (schema migration, file creation) — not for polling'
                ),
            })

    return warnings


def index(request):
    stacks = StackTemplate.objects.filter(is_active=True).order_by('category', 'sort_order', 'label')
    community_stacks = UserStack.objects.filter(is_approved=True).select_related('user').order_by('name')
    return render(request, 'generator/builder.html', {'stacks': stacks, 'community_stacks': community_stacks})


def _auto_passwords(data_str):
    """Ersetzt changeme-Platzhalter durch echte Zufallspasswörter (konsistent pro Platzhalter)."""
    cache = {}
    def replacer(m):
        key = m.group(0)
        if key not in cache:
            cache[key] = secrets.token_urlsafe(16)
        return cache[key]
    return re.sub(r'changeme\w*', replacer, data_str)


def stack_load(request):
    """JSON: gibt Stack-Konfiguration zurück um das Formular vorzufüllen."""
    key = request.GET.get('key', '')
    try:
        stack = StackTemplate.objects.get(key=key, is_active=True)
    except StackTemplate.DoesNotExist:
        return JsonResponse({'error': 'not found'}, status=404)
    data = json.loads(_auto_passwords(json.dumps(stack.stack_data)))
    data['_meta'] = {
        'description': stack.description,
        'icon': stack.icon,
        'label': stack.label,
        'category': stack.category,
    }
    return JsonResponse(data)


def connection_hints(request):
    """JSON: gibt Verbindungs-Hints für ein bestimmtes Image zurück."""
    image = request.GET.get('image', '').lower()
    # Image-Name extrahieren
    for prefix in ('docker.io/library/', 'docker.io/', 'ghcr.io/', 'quay.io/'):
        image = image.replace(prefix, '')
    image = image.split(':')[0].split('/')[-1]
    hints = CONNECTION_HINTS.get(image, {})
    return JsonResponse(hints)


def add_container(request):
    try:
        idx = min(max(int(request.GET.get('index', 0)), 0), 50)
    except ValueError:
        idx = 0
    form = ContainerForm(prefix=f'c{idx}')
    return render(request, 'generator/partials/container_form.html', {
        'form': form,
        'index': idx,
    })


def add_init_container(request):
    try:
        idx = min(max(int(request.GET.get('index', 0)), 0), 20)
    except ValueError:
        idx = 0
    form = InitContainerForm(prefix=f'i{idx}')
    return render(request, 'generator/partials/init_container_form.html', {
        'form': form,
        'index': idx,
    })


@ratelimit(key='ip', rate='20/m', method='POST', block=True)
def generate_view(request):
    if request.method != 'POST':
        return redirect('index')

    pod_form = PodForm(request.POST)
    try:
        c_count = min(max(int(request.POST.get('container_count', 1)), 1), 50)
        i_count = min(max(int(request.POST.get('init_count', 0)), 0), 20)
    except ValueError:
        c_count, i_count = 1, 0
    container_forms = [ContainerForm(request.POST, prefix=f'c{i}') for i in range(c_count)]
    init_forms = [InitContainerForm(request.POST, prefix=f'i{i}') for i in range(i_count)]

    valid = pod_form.is_valid() and all(f.is_valid() for f in container_forms) and all(f.is_valid() for f in init_forms)
    if not valid:
        return render(request, 'generator/index.html', {
            'pod_form': pod_form,
            'container_forms': container_forms,
            'init_forms': init_forms,
            'error': True,
        })

    pd = pod_form.cleaned_data
    form_data = {
        'pod_name': pd['pod_name'],
        'restart_policy': pd['restart_policy'],
        'mode': pd['mode'],
        'host_network': pd.get('host_network', False),
        'host_pid': pd.get('host_pid', False),
        'host_ipc': pd.get('host_ipc', False),
        'hostname': pd.get('hostname', ''),
        'host_aliases': pd.get('host_aliases', ''),
        'userns': pd.get('userns', ''),
        'dns': pd.get('dns', ''),
        'network': pd.get('network', ''),
        'containers': [f.cleaned_data for f in container_forms],
        'init_containers': [f.cleaned_data for f in init_forms],
    }

    yaml_content = generate(form_data)
    shell_content = generate_shell(form_data)
    quadlet_content = generate_quadlet(form_data)
    env_file_content = generate_env_file(form_data)
    pod_name = form_data['pod_name'].strip().lower().replace(' ', '-')
    validation_warnings = validate_form_data(form_data)

    try:
        from .models import GeneratedYAML
        from .middleware import _get_ip
        images = ', '.join(
            c.get('image', '').split(':')[0].split('/')[-1]
            for c in form_data.get('containers', []) if c.get('image')
        )
        GeneratedYAML.objects.create(
            mode=form_data.get('mode', 'rootless'),
            pod_name=pod_name,
            container_count=len(form_data.get('containers', [])),
            init_count=len(form_data.get('init_containers', [])),
            images=images,
            ip=_get_ip(request),
        )
    except Exception:
        pass

    # Netzwerk-Info für Banner: Container + ihre Ports
    net_info = []
    for c in form_data['containers']:
        ports = []
        for line in (c.get('ports') or '').splitlines():
            line = line.strip()
            if ':' in line:
                try:
                    ports.append(int(line.split(':')[-1].split('/')[0]))
                except ValueError:
                    pass
        if ports:
            net_info.append({'name': c['name'], 'ports': ports})

    editing_stack_id = request.POST.get('editing_stack_id', '').strip()
    editing_stack_name = request.POST.get('editing_stack_name', '').strip()
    editing_stack_description = request.POST.get('editing_stack_description', '').strip()
    editing_stack_icon = request.POST.get('editing_stack_icon', 'bi-box').strip()
    editing_stack_category = request.POST.get('editing_stack_category', '').strip()

    return render(request, 'generator/result.html', {
        'yaml_content': yaml_content,
        'shell_content': shell_content,
        'quadlet_content': quadlet_content,
        'env_file_content': env_file_content,
        'pod_name': pod_name,
        'mode': form_data['mode'],
        'form_data_json': json.dumps(form_data),
        'net_info': net_info,
        'validation_warnings': validation_warnings,
        'editing_stack_id': editing_stack_id,
        'editing_stack_name': editing_stack_name,
        'editing_stack_description': editing_stack_description,
        'editing_stack_icon': editing_stack_icon,
        'editing_stack_category': editing_stack_category,
    })


@ratelimit(key='ip', rate='10/m', method='POST', block=True)
@ratelimit(key='ip', rate='10/h', method='POST', block=True)
def save_config(request):
    if request.method != 'POST':
        return redirect('index')

    yaml_content = request.POST.get('yaml_content', '')
    if len(yaml_content) > 200_000:
        return HttpResponse('YAML too large (max 200 KB).', status=413)
    try:
        form_data = json.loads(request.POST.get('form_data_json', '{}'))
    except (json.JSONDecodeError, ValueError):
        form_data = {}
    pod_name = form_data.get('pod_name', 'unnamed')

    config = SavedConfig.objects.create(
        name=pod_name,
        yaml_content=yaml_content,
        form_data=form_data,
    )
    from .models import SavedConfigVersion
    SavedConfigVersion.objects.create(
        config=config,
        yaml_content=yaml_content,
        form_data=form_data,
        label='Initial',
    )
    return redirect('saved_detail', uuid=config.uuid)


def saved_detail(request, uuid):
    config = get_object_or_404(SavedConfig, uuid=uuid)
    shell_content = generate_shell(config.form_data)
    quadlet_content = generate_quadlet(config.form_data)
    env_file_content = generate_env_file(config.form_data)
    return render(request, 'generator/saved_detail.html', {
        'config': config,
        'pod_name': config.name,
        'yaml_content': config.yaml_content,
        'shell_content': shell_content,
        'quadlet_content': quadlet_content,
        'env_file_content': env_file_content,
        'mode': config.form_data.get('mode', 'rootless'),
    })


@require_POST
def update_config(request, uuid):
    """Update YAML of an existing SavedConfig and create a new version."""
    from .models import SavedConfigVersion
    config = get_object_or_404(SavedConfig, uuid=uuid)
    new_yaml = request.POST.get('yaml_content', '').strip()
    label = request.POST.get('label', '').strip() or f'v{config.versions.count() + 1}'
    if not new_yaml:
        messages.error(request, 'YAML content is required.')
        return redirect('saved_detail', uuid=uuid)
    SavedConfigVersion.objects.create(
        config=config,
        yaml_content=config.yaml_content,
        form_data=config.form_data,
        label=f'Before: {label}',
    )
    config.yaml_content = new_yaml
    config.save(update_fields=['yaml_content'])
    SavedConfigVersion.objects.create(
        config=config,
        yaml_content=new_yaml,
        form_data=config.form_data,
        label=label,
    )
    messages.success(request, 'Config updated.')
    return redirect('saved_detail', uuid=uuid)


def download(request, uuid):
    config = get_object_or_404(SavedConfig, uuid=uuid)
    response = HttpResponse(config.yaml_content, content_type='application/x-yaml')
    safe_name = re.sub(r'[^\w\-]', '_', config.name)[:80] or 'config'
    response['Content-Disposition'] = f'attachment; filename="{safe_name}.yaml"'
    return response


def download_quadlet(request, uuid):
    config = get_object_or_404(SavedConfig, uuid=uuid)
    content = generate_quadlet(config.form_data)
    safe_name = re.sub(r'[^\w\-]', '_', config.name)[:80] or 'config'
    response = HttpResponse(content, content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="{safe_name}.kube"'
    return response


def download_env(request, uuid):
    config = get_object_or_404(SavedConfig, uuid=uuid)
    content = generate_env_file(config.form_data)
    safe_name = re.sub(r'[^\w\-]', '_', config.name)[:80] or 'config'
    response = HttpResponse(content, content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="{safe_name}.env"'
    return response


def config_versions(request, uuid):
    from .models import SavedConfigVersion
    import difflib
    config = get_object_or_404(SavedConfig, uuid=uuid)
    versions = config.versions.order_by('-created_at')

    diff_html = None
    v1_id = request.GET.get('v1')
    v2_id = request.GET.get('v2')
    v1 = v2 = None
    if v1_id and v2_id:
        try:
            v1 = config.versions.get(pk=v1_id)
            v2 = config.versions.get(pk=v2_id)
            diff = difflib.unified_diff(
                v2.yaml_content.splitlines(keepends=True),
                v1.yaml_content.splitlines(keepends=True),
                fromfile=f'v{v2.pk} ({v2.created_at:%Y-%m-%d %H:%M})',
                tofile=f'v{v1.pk} ({v1.created_at:%Y-%m-%d %H:%M})',
                lineterm='',
            )
            diff_html = ''.join(diff)
        except SavedConfigVersion.DoesNotExist:
            pass

    return render(request, 'generator/config_versions.html', {
        'config': config,
        'versions': versions,
        'diff_html': diff_html,
        'v1': v1,
        'v2': v2,
    })


@login_required
def collections_list(request):
    from .models import StackCollection
    collections = StackCollection.objects.filter(user=request.user).prefetch_related('items__saved_config')
    public_collections = StackCollection.objects.filter(is_public=True).exclude(user=request.user).prefetch_related('items__saved_config').select_related('user')
    return render(request, 'generator/collections.html', {
        'collections': collections,
        'public_collections': public_collections,
    })


@login_required
@require_POST
def collection_create(request):
    from .models import StackCollection
    name = request.POST.get('name', '').strip()
    if not name:
        messages.error(request, 'Name is required.')
        return redirect('collections_list')
    StackCollection.objects.create(
        user=request.user,
        name=name[:100],
        description=request.POST.get('description', '')[:300],
        is_public=request.POST.get('is_public') == 'on',
    )
    messages.success(request, f'Collection "{name}" created.')
    return redirect('collections_list')


@login_required
@require_POST
def collection_delete(request, collection_id):
    from .models import StackCollection
    col = get_object_or_404(StackCollection, pk=collection_id, user=request.user)
    col.delete()
    messages.success(request, 'Collection deleted.')
    return redirect('collections_list')


def collection_detail(request, collection_id):
    from .models import StackCollection, StackCollectionItem
    col = get_object_or_404(StackCollection, pk=collection_id)
    if not col.is_public and (not request.user.is_authenticated or col.user != request.user):
        from django.http import Http404
        raise Http404
    items = col.items.select_related('saved_config').order_by('position', 'added_at')
    return render(request, 'generator/collection_detail.html', {
        'col': col,
        'items': items,
        'is_owner': request.user.is_authenticated and col.user == request.user,
    })


@login_required
@require_POST
def collection_remove_item(request, collection_id, item_id):
    from .models import StackCollection, StackCollectionItem
    col = get_object_or_404(StackCollection, pk=collection_id, user=request.user)
    item = get_object_or_404(StackCollectionItem, pk=item_id, collection=col)
    item.delete()
    return redirect('collection_detail', collection_id=collection_id)


@login_required
@require_POST
def config_add_to_collection(request, uuid):
    """AJAX-friendly endpoint: adds a saved config to one of the user's collections."""
    from .models import StackCollection, StackCollectionItem
    config = get_object_or_404(SavedConfig, uuid=uuid)
    col_id = request.POST.get('collection_id')
    if col_id == 'new':
        name = request.POST.get('new_name', '').strip() or config.name
        col = StackCollection.objects.create(user=request.user, name=name[:100])
    else:
        col = get_object_or_404(StackCollection, pk=col_id, user=request.user)
    StackCollectionItem.objects.get_or_create(collection=col, saved_config=config)
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'ok': True, 'collection': col.name})
    messages.success(request, f'Added to "{col.name}".')
    return redirect('saved_detail', uuid=uuid)


def edit_config(request, uuid):
    config = get_object_or_404(SavedConfig, uuid=uuid)
    stacks = StackTemplate.objects.filter(is_active=True).order_by('category', 'sort_order', 'label')
    community_stacks = UserStack.objects.filter(is_approved=True).select_related('user').order_by('user__username', 'name')
    return render(request, 'generator/index.html', {
        'pod_form': PodForm(),
        'container_forms': [ContainerForm(prefix='c0')],
        'init_forms': [],
        'stacks': stacks,
        'community_stacks': community_stacks,
        'prefill_json': json.dumps(config.form_data),
    })


def stack_detail(request, key):
    stack = get_object_or_404(StackTemplate, key=key, is_active=True)
    sd = stack.stack_data
    form_data = {
        'pod_name': sd.get('pod_name', key),
        'restart_policy': sd.get('restart_policy', 'Always'),
        'mode': sd.get('mode', 'rootless'),
        'host_network': sd.get('host_network', False),
        'host_pid': False,
        'host_ipc': False,
        'hostname': '',
        'host_aliases': '',
        'userns': '',
        'dns': '',
        'containers': sd.get('containers', []),
        'init_containers': sd.get('init_containers', []),
    }
    yaml_content = generate(form_data)
    containers = form_data['containers']
    images = [c.get('image', '').split('/')[-1].split(':')[0] for c in containers]
    mode = form_data['mode']
    return render(request, 'generator/stack_detail.html', {
        'stack': stack,
        'yaml_content': yaml_content,
        'form_data_json': json.dumps(form_data),
        'images': images,
        'mode': mode,
        'containers': containers,
        'pod_name': form_data['pod_name'],
    })


def impressum(request):
    imp = ImpressumSettings.get_solo()
    if not imp.impressum_enabled:
        raise Http404
    return render(request, 'generator/impressum.html', {'imp': imp})


def datenschutz(request):
    from .models import AnalyticsSettings, CookieBannerSettings
    imp = ImpressumSettings.get_solo()
    if not imp.privacy_enabled:
        raise Http404
    return render(request, 'generator/datenschutz.html', {
        'imp': imp,
        'retention_days': AnalyticsSettings.get_solo().retention_days,
        'cookie_banner': CookieBannerSettings.get_solo(),
    })


@ratelimit(key='ip', rate='20/m', block=True)
def image_preset(request):
    """JSON: gibt Preset-Einstellungen für ein bekanntes Image zurück.
    Fallback: ExposedPorts aus der Docker Registry."""
    image = request.GET.get('image', '')
    preset = get_preset(image)
    if not preset:
        from concurrent.futures import ThreadPoolExecutor, wait as _wait
        ex = ThreadPoolExecutor(max_workers=1)
        f = ex.submit(fetch_registry_all, image)
        done, _ = _wait([f], timeout=10)
        ex.shutdown(wait=False)
        reg = f.result() if done else {}

        ports   = reg.get('ports', [])
        env     = reg.get('env', '')
        uid     = reg.get('run_as_user')
        volumes = reg.get('volumes', [])
        fallback = {'_from_registry': True}
        if ports:
            seen = set()
            port_lines = []
            for p in ports:
                port_num = p.split('/')[0]
                if port_num.isdigit() and port_num not in seen:
                    seen.add(port_num)
                    port_lines.append(f'{port_num}:{port_num}')
            if port_lines:
                fallback['ports'] = '\n'.join(port_lines)
        if env:
            fallback['env'] = env
        if uid is not None:
            fallback['run_as_user'] = uid
        if volumes:
            img_base = image.rstrip('/').split('/')[-1].split(':')[0]
            vol_lines = [f'{img_base}-{v.rstrip("/").rsplit("/", 1)[-1] or "data"}:{v}' for v in volumes]
            fallback['volumes'] = '\n'.join(vol_lines)
        elif reg:
            # Registry responded but declared no volumes
            fallback['_no_registry_volumes'] = True
        if len(fallback) > 1:
            preset = fallback
    return JsonResponse(preset)


@ratelimit(key='ip', rate='30/m', block=True)
def image_search(request):
    query = request.GET.get('q', '').strip()
    if len(query) < 2 or len(query) > 100:
        return HttpResponse('')
    registry = request.GET.get('registry', 'all')
    from concurrent.futures import ThreadPoolExecutor, wait as _wait
    ex = ThreadPoolExecutor(max_workers=1)
    f = ex.submit(search_images, query, 10, registry)
    done, _ = _wait([f], timeout=5)
    ex.shutdown(wait=False)
    results = f.result() if done else []
    return render(request, 'generator/partials/image_results.html', {'results': results, 'query': query})


_REGISTRY_NAME_RE = re.compile(r'^[a-z0-9][a-z0-9._-]{0,127}$')

@ratelimit(key='ip', rate='30/m', block=True)
def image_tags(request):
    namespace = request.GET.get('namespace', 'library')
    name = request.GET.get('name', '')
    if not name or not _REGISTRY_NAME_RE.match(name) or not _REGISTRY_NAME_RE.match(namespace):
        return HttpResponse('')
    from concurrent.futures import ThreadPoolExecutor, wait as _wait
    ex = ThreadPoolExecutor(max_workers=1)
    f = ex.submit(get_tags, namespace, name)
    done, _ = _wait([f], timeout=5)
    ex.shutdown(wait=False)
    tags = f.result() if done else []
    return render(request, 'generator/partials/tag_results.html', {
        'tags': tags,
        'namespace': namespace,
        'name': name,
    })


_IMAGE_INSPECT_RE = re.compile(r'^[a-z0-9][a-z0-9._\-/:@]{0,199}$')

@ratelimit(key='ip', rate='20/m', block=True)
def image_inspect(request):
    """
    Kombinierter Image-Inspector: Hub-Metadaten + Tags + Registry-Config + Vulnerabilities.
    GET ?image=docker.io/mysql:8.4
    """
    image = request.GET.get('image', '').strip().lower()
    if not image or not _IMAGE_INSPECT_RE.match(image):
        return JsonResponse({'error': 'invalid image'}, status=400)

    # Registry-Prefix entfernen für Hub-Lookups
    hub_img = image
    for prefix in ('docker.io/', 'index.docker.io/'):
        if hub_img.startswith(prefix):
            hub_img = hub_img[len(prefix):]

    # Tag extrahieren
    tag = 'latest'
    base = hub_img
    last_seg = hub_img.split('/')[-1]
    if ':' in last_seg:
        base = hub_img.rsplit(':', 1)[0]
        tag = hub_img.rsplit(':', 1)[1]

    # namespace/name trennen
    if '/' in base:
        namespace, name = base.rsplit('/', 1)
    else:
        namespace, name = 'library', base

    # Nur Docker Hub unterstützt Hub-Metadaten + Vulns
    is_dockerhub = not any(image.startswith(r) for r in ('ghcr.io/', 'quay.io/', 'lscr.io/'))

    from concurrent.futures import ThreadPoolExecutor, wait as _wait
    tasks = {}
    ex = ThreadPoolExecutor(max_workers=4)
    if is_dockerhub:
        tasks['hub']   = ex.submit(get_hub_info, namespace, name)
        tasks['tags']  = ex.submit(get_tags, namespace, name, 15)
        tasks['vulns'] = ex.submit(get_tag_vulns, namespace, name, tag)
    tasks['reg'] = ex.submit(fetch_registry_all, image)
    _wait(list(tasks.values()), timeout=9)
    ex.shutdown(wait=False)

    hub   = tasks['hub'].result()   if 'hub'   in tasks and tasks['hub'].done()   else {}
    tags  = tasks['tags'].result()  if 'tags'  in tasks and tasks['tags'].done()  else []
    vulns = tasks['vulns'].result() if 'vulns' in tasks and tasks['vulns'].done() else {}
    reg   = tasks['reg'].result()   if tasks['reg'].done() else {}

    # Env-Einträge aufbereiten
    env_entries = []
    for line in (reg.get('env') or '').splitlines():
        if '=' in line:
            k, _, v = line.partition('=')
            env_entries.append({'key': k.strip(), 'value': v.strip()})

    # Docker Scout URL
    if namespace == 'library':
        scout_url = f"https://scout.docker.com/image/docker.io/library/{name}:{tag}"
    else:
        scout_url = f"https://scout.docker.com/image/docker.io/{namespace}/{name}:{tag}"

    return JsonResponse({
        'hub':             hub,
        'tags':            tags,
        'ports':           reg.get('ports', []),
        'env':             env_entries,
        'volumes':         reg.get('volumes', []),
        'run_as_user':     reg.get('run_as_user'),
        'vulnerabilities': vulns,
        'scout_url':       scout_url,
        'namespace':       namespace,
        'name':            name,
        'tag':             tag,
        'is_dockerhub':    is_dockerhub,
    })


# ── Auth ──────────────────────────────────────────────────────────

def _notify_admin_new_user(user, request):
    """Admin-E-Mail bei neuer Registrierung."""
    from .models import EmailSettings
    cfg = EmailSettings.get_solo()
    if not cfg.admin_email:
        return
    admin_url = request.build_absolute_uri(f'/admin/auth/user/{user.pk}/change/')
    subject, html = mail_new_registration(user.username, user.email, admin_url)
    send_app_mail(subject=subject, body=html, recipient_list=[cfg.admin_email])


@ratelimit(key='ip', rate='10/h', method='POST', block=True)
def register(request):
    reg = RegistrationSettings.get_solo()
    if not reg.registration_enabled:
        return render(request, 'generator/register.html', {'disabled': True})
    if request.user.is_authenticated:
        return redirect('my_stacks')

    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()  # is_active=False
            _notify_admin_new_user(user, request)
            if reg.email_activation and user.email:
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)
                activation_url = request.build_absolute_uri(f'/activate/{uid}/{token}/')
                send_app_mail(
                    **dict(zip(('subject', 'body'), mail_activation(user.username, activation_url))),
                    recipient_list=[user.email],
                    from_email=reg.email_from,
                )
                return render(request, 'generator/register.html', {'sent': True, 'email': user.email})
            return render(request, 'generator/register.html', {'pending': True})
    else:
        form = RegistrationForm()
    return render(request, 'generator/register.html', {'form': form})


def activate(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    if user and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        return render(request, 'generator/activate.html', {'success': True})
    return render(request, 'generator/activate.html', {'success': False})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('my_stacks')
    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            from django.utils.http import url_has_allowed_host_and_scheme
            next_url = request.POST.get('next', '') or request.GET.get('next', '')
            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts=set(settings.ALLOWED_HOSTS)):
                return redirect(next_url)
            return redirect('my_stacks')
        error = 'Benutzername oder Passwort falsch, oder Account noch nicht freigeschaltet.'
    reg = RegistrationSettings.get_solo()
    next_url = request.GET.get('next', '')
    from django.utils.http import url_has_allowed_host_and_scheme
    if next_url and not url_has_allowed_host_and_scheme(next_url, allowed_hosts=set(settings.ALLOWED_HOSTS)):
        next_url = ''
    return render(request, 'generator/login.html', {
        'error': error,
        'password_reset_enabled': reg.password_reset_enabled,
        'next': next_url,
    })


@require_POST
def logout_view(request):
    logout(request)
    return redirect('index')


# ── Community Stacks ──────────────────────────────────────────────

@login_required(login_url='/login/')
def my_stacks(request):
    private_qs = UserStack.objects.filter(user=request.user, is_private=True).order_by('-created_at')
    community_qs = UserStack.objects.filter(user=request.user, is_private=False).order_by('-created_at')
    private_paginator = Paginator(private_qs, 10)
    community_paginator = Paginator(community_qs, 10)
    private_page = private_paginator.get_page(request.GET.get('private_page'))
    community_page = community_paginator.get_page(request.GET.get('community_page'))
    return render(request, 'generator/my_stacks.html', {
        'private_page': private_page,
        'community_page': community_page,
    })


@login_required(login_url='/login/')
def view_user_stack(request, stack_id):
    stack = get_object_or_404(UserStack, pk=stack_id, user=request.user)
    form_data = stack.form_data
    yaml_content = generate(form_data)
    shell_content = generate_shell(form_data)
    pod_name = form_data.get('pod_name', stack.name).strip().lower().replace(' ', '-')
    net_info = []
    for c in form_data.get('containers', []):
        ports = []
        for line in (c.get('ports') or '').splitlines():
            line = line.strip()
            if ':' in line:
                try:
                    ports.append(int(line.split(':')[-1].split('/')[0]))
                except ValueError:
                    pass
        if ports:
            net_info.append({'name': c['name'], 'ports': ports})
    validation_warnings = validate_form_data(form_data)
    return render(request, 'generator/result.html', {
        'yaml_content': yaml_content,
        'shell_content': shell_content,
        'pod_name': pod_name,
        'mode': form_data.get('mode', 'rootless'),
        'form_data_json': json.dumps(form_data),
        'net_info': net_info,
        'validation_warnings': validation_warnings,
        'editing_stack_id': stack.pk,
        'editing_stack_name': stack.name,
        'editing_stack_description': stack.description or '',
        'editing_stack_icon': stack.icon or 'bi-box',
        'editing_stack_category': stack.category or '',
    })


_VALID_ICON = re.compile(r'^bi-[\w-]+$')

def _clean_icon(value):
    v = value.strip()[:60]
    return v if _VALID_ICON.match(v) else 'bi-box'


@login_required(login_url='/login/')
def edit_user_stack(request, stack_id):
    stack = get_object_or_404(UserStack, pk=stack_id, user=request.user)
    if stack.is_approved and not stack.is_private:
        return redirect('my_stacks')
    stacks = StackTemplate.objects.filter(is_active=True).order_by('category', 'sort_order', 'label')
    community_stacks = UserStack.objects.filter(is_approved=True).select_related('user').order_by('user__username', 'name')
    return render(request, 'generator/index.html', {
        'pod_form': PodForm(),
        'container_forms': [ContainerForm(prefix='c0')],
        'init_forms': [],
        'stacks': stacks,
        'community_stacks': community_stacks,
        'prefill_json': json.dumps(stack.form_data),
        'editing_stack_id': stack.pk,
        'editing_stack_name': stack.name,
        'editing_stack_description': stack.description,
        'editing_stack_icon': stack.icon or 'bi-box',
        'editing_stack_category': stack.category or '',
    })


@login_required(login_url='/login/')
@ratelimit(key='user', rate='20/h', method='POST', block=True)
def update_user_stack(request, stack_id):
    if request.method != 'POST':
        return redirect('my_stacks')
    stack = get_object_or_404(UserStack, pk=stack_id, user=request.user)
    if stack.is_approved and not stack.is_private:
        return redirect('my_stacks')
    name = request.POST.get('name', '').strip() or stack.name
    description = request.POST.get('description', '').strip()
    form_data_json = request.POST.get('form_data_json', '')
    if not form_data_json:
        return redirect('my_stacks')
    stack.name = name
    stack.description = description[:300]
    stack.icon = _clean_icon(request.POST.get('icon', 'bi-box'))
    stack.category = request.POST.get('category', '').strip()[:50]
    try:
        stack.form_data = json.loads(form_data_json)
    except (json.JSONDecodeError, ValueError):
        return redirect('my_stacks')
    stack.is_approved = False
    stack.save()
    return redirect('my_stacks')


@login_required(login_url='/login/')
@require_POST
def update_stack_meta(request, stack_id):
    """Update name, description, icon, category only — does not reset approval."""
    stack = get_object_or_404(UserStack, pk=stack_id, user=request.user)
    stack.name = request.POST.get('name', '').strip()[:100] or stack.name
    stack.description = request.POST.get('description', '').strip()[:300]
    stack.icon = _clean_icon(request.POST.get('icon', 'bi-box'))
    stack.category = request.POST.get('category', '').strip()[:50]
    stack.save(update_fields=['name', 'description', 'icon', 'category'])
    return redirect('my_stacks')


def _extract_images(form_data):
    """Gibt normalisierte Image-Namen (ohne Tag) aus form_data zurück."""
    images = set()
    for c in form_data.get('containers', []) + form_data.get('init_containers', []):
        img = c.get('image', '').strip().lower().split(':')[0]
        if img:
            images.add(img)
    return images


@ratelimit(key='ip', rate='30/m', method='GET', block=True)
def check_duplicate(request):
    """Gibt vorhandene Community Stacks zurück die dieselben Images nutzen."""
    try:
        form_data = json.loads(request.GET.get('form_data_json', '{}'))
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'duplicates': []})
    images = _extract_images(form_data)
    if not images:
        return JsonResponse({'duplicates': []})
    duplicates = []
    for stack in UserStack.objects.filter(is_approved=True).select_related('user'):
        existing_images = _extract_images(stack.form_data)
        overlap = images & existing_images
        if overlap:
            duplicates.append({
                'name': stack.name,
                'user': stack.user.username,
                'overlap': sorted(overlap),
            })
    return JsonResponse({'duplicates': duplicates})


@login_required(login_url='/login/')
@ratelimit(key='user', rate='1/10m', method='POST', block=False)
def submit_stack(request):
    if request.method != 'POST':
        return redirect('index')
    if getattr(request, 'limited', False):
        return JsonResponse({'error': 'ratelimit', 'message': 'You can only submit one stack every 10 minutes. Please wait a moment.'}, status=429)
    name = request.POST.get('name', '').strip()
    form_data_json = request.POST.get('form_data_json', '')
    if not name or not form_data_json:
        return JsonResponse({'error': 'missing'}, status=400)
    try:
        form_data = json.loads(form_data_json)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'invalid'}, status=400)
    is_private = request.POST.get('is_private') == '1'
    images = _extract_images(form_data)
    if images and not is_private:
        # Eigener Stack mit identischen Images bereits vorhanden?
        for existing in UserStack.objects.filter(user=request.user, is_private=False):
            if _extract_images(existing.form_data) == images:
                return JsonResponse({'error': 'duplicate', 'message': 'You already submitted a stack with the same images.'}, status=409)
        # Approved Stack eines anderen Users mit exakt denselben Images?
        for existing in UserStack.objects.filter(is_approved=True).exclude(user=request.user):
            if _extract_images(existing.form_data) == images:
                return JsonResponse({'error': 'duplicate', 'message': f'An identical stack already exists in the community ("{existing.name}" by {existing.user.username}).'}, status=409)

    description = request.POST.get('description', '').strip()[:300]
    stack = UserStack.objects.create(
        user=request.user,
        name=name,
        description=description,
        icon=_clean_icon(request.POST.get('icon', 'bi-box')),
        category=request.POST.get('category', '').strip()[:50],
        form_data=form_data,
        is_private=is_private,
        is_approved=is_private,  # private stacks need no approval
    )
    if not is_private:
        from .models import EmailSettings
        admin_email = EmailSettings.get_solo().admin_email
        if admin_email:
            site_url = getattr(settings, 'SITE_URL', '')
            admin_url = f'{site_url}/admin/generator/userstack/{stack.pk}/change/'
            subject, html = mail_new_stack(request.user.username, name, description, admin_url)
            send_app_mail(subject=subject, body=html, recipient_list=[admin_email])
    return JsonResponse({'ok': True})


@login_required(login_url='/login/')
@require_POST
def delete_user_stack(request, stack_id):
    stack = get_object_or_404(UserStack, pk=stack_id, user=request.user)
    stack.delete()
    return redirect('my_stacks')


@ratelimit(key='ip', rate='30/m', method='GET', block=True)
def community_stack_load(request):
    stack_id = request.GET.get('id', '')
    try:
        stack = UserStack.objects.select_related('user').get(pk=stack_id, is_approved=True)
    except UserStack.DoesNotExist:
        return JsonResponse({'error': 'not found'}, status=404)
    data = json.loads(_auto_passwords(json.dumps(stack.form_data)))
    data['_meta'] = {
        'description': stack.description or f'Community stack by {stack.user.username}',
        'icon': 'bi-people',
        'label': stack.name,
        'category': stack.user.username,
    }
    return JsonResponse(data)


# ── User Profile ──────────────────────────────────────────────────

@login_required(login_url='/login/')
@ratelimit(key='user', rate='20/h', method='POST', block=True)
def profile_edit(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        profile.bio = request.POST.get('bio', '').strip()[:300]
        avatar_url = request.POST.get('avatar_url', '').strip()
        profile.avatar_url = avatar_url if avatar_url.startswith('https://') or avatar_url.startswith('http://') else ''
        website = request.POST.get('website', '').strip()
        profile.website = website if website.startswith('http://') or website.startswith('https://') else ''
        profile.github = request.POST.get('github', '').strip()[:100]
        profile.twitter = request.POST.get('twitter', '').strip().lstrip('@')[:100]
        profile.mastodon = request.POST.get('mastodon', '').strip()[:200]
        profile.linkedin = request.POST.get('linkedin', '').strip()[:100]
        profile.save()
        messages.success(request, 'Profil gespeichert.')
        return redirect('profile_edit')
    return render(request, 'generator/profile_edit.html', {'profile': profile})


@login_required(login_url='/login/')
@ratelimit(key='user', rate='10/h', method='POST', block=True)
def avatar_upload(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'method not allowed'}, status=405)

    # Avatar entfernen
    if request.POST.get('remove'):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        if profile.avatar:
            from django.conf import settings as _s
            try:
                (_s.MEDIA_ROOT / profile.avatar).unlink(missing_ok=True)
            except Exception:
                pass
            profile.avatar = ''
            profile.save()
        return JsonResponse({'ok': True})

    f = request.FILES.get('avatar')
    if not f:
        return JsonResponse({'error': 'No file.'}, status=400)
    if f.size > 5 * 1024 * 1024:
        return JsonResponse({'error': 'File too large (max. 5 MB).'}, status=400)

    from PIL import Image
    import io
    from django.conf import settings as _s
    import os

    try:
        img = Image.open(f)
        img.verify()
        f.seek(0)
        img = Image.open(f)
        img = img.convert('RGB')
        # Center-crop auf Quadrat
        w, h = img.size
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        img = img.crop((left, top, left + side, top + side))
        img = img.resize((256, 256), Image.LANCZOS)
    except Exception:
        return JsonResponse({'error': 'Invalid image.'}, status=400)

    avatar_dir = _s.MEDIA_ROOT / 'avatars'
    avatar_dir.mkdir(parents=True, exist_ok=True)

    # Altes Avatar löschen
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if profile.avatar:
        old_path = _s.MEDIA_ROOT / profile.avatar
        try:
            old_path.unlink(missing_ok=True)
        except Exception:
            pass

    filename = f'avatars/{request.user.pk}.jpg'
    out_path = _s.MEDIA_ROOT / filename
    img.save(out_path, 'JPEG', quality=88, optimize=True)

    profile.avatar = filename
    profile.save()
    return JsonResponse({'url': f'/media/{filename}?v={secrets.token_hex(4)}'})


@login_required(login_url='/login/')
def delete_account(request):
    if request.method != 'POST':
        return redirect('profile_edit')
    password = request.POST.get('password', '')
    user = authenticate(username=request.user.username, password=password)
    if user is None:
        messages.error(request, 'Wrong password — account was not deleted.')
        return redirect('profile_edit')
    logout(request)
    user.delete()
    return redirect('/?account_deleted=1')


def profile_public(request, username):
    user = get_object_or_404(User, username=username, is_active=True)
    profile, _ = UserProfile.objects.get_or_create(user=user)
    qs = UserStack.objects.filter(user=user, is_approved=True).order_by('-created_at')
    paginator = Paginator(qs, 10)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'generator/profile_public.html', {
        'profile_user': user,
        'profile': profile,
        'page_obj': page,
    })


def community_stack_detail(request, stack_id):
    stack = get_object_or_404(UserStack, pk=stack_id, is_approved=True)
    # View-Counter erhöhen (einfach, ohne Deduplizierung)
    UserStack.objects.filter(pk=stack_id).update(view_count=models.F('view_count') + 1)
    stack.refresh_from_db(fields=['view_count'])

    yaml_content = generate(stack.form_data)
    like_count = stack.likes.count()
    user_liked = request.user.is_authenticated and stack.likes.filter(user=request.user).exists()
    comments = stack.comments.filter(is_approved=True).select_related('user', 'user__profile')

    return render(request, 'generator/community_stack_detail.html', {
        'stack': stack,
        'yaml_content': yaml_content,
        'like_count': like_count,
        'user_liked': user_liked,
        'comments': comments,
    })


@login_required(login_url='/login/')
@ratelimit(key='user', rate='60/h', method='POST', block=True)
def stack_like(request, stack_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    stack = get_object_or_404(UserStack, pk=stack_id, is_approved=True)
    like, created = StackLike.objects.get_or_create(user=request.user, stack=stack)
    if not created:
        like.delete()
        liked = False
    else:
        liked = True
    return JsonResponse({'liked': liked, 'count': stack.likes.count()})


@login_required(login_url='/login/')
@ratelimit(key='user', rate='20/h', method='POST', block=True)
def stack_comment(request, stack_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    stack = get_object_or_404(UserStack, pk=stack_id, is_approved=True)
    body = request.POST.get('body', '').strip()
    if not body:
        return JsonResponse({'error': 'empty'}, status=400)
    body = body[:1000]
    comment = StackComment.objects.create(user=request.user, stack=stack, body=body)

    # E-Mail an Stack-Besitzer (nicht an sich selbst)
    if stack.user != request.user and stack.user.email:
        stack_url = request.build_absolute_uri(f'/community/{stack_id}/')
        subject, html = mail_new_comment(
            stack.user.username, request.user.username, stack.name, body, stack_url
        )
        send_app_mail(subject=subject, body=html, recipient_list=[stack.user.email])

    try:
        avatar = comment.user.profile.get_avatar_url()
    except Exception:
        avatar = ''

    return JsonResponse({
        'ok': True,
        'comment': {
            'username': comment.user.username,
            'body': comment.body,
            'avatar': avatar,
            'created_at': comment.created_at.strftime('%d.%m.%Y %H:%M'),
        }
    })


def community(request):
    from django.db.models import Count, Max

    # Filter-Parameter
    active_category = request.GET.get('cat', '').strip()
    active_sort = request.GET.get('sort', 'new')  # new | likes | views

    # Rangliste: User mit mind. 1 freigegebenem Stack, sortiert nach Anzahl desc, dann neuestes Stack
    leaderboard_qs = (
        UserStack.objects.filter(is_approved=True)
        .values('user')
        .annotate(stack_count=Count('id'), latest=Max('created_at'))
        .order_by('-stack_count', '-latest')[:20]
    )
    user_ids = [e['user'] for e in leaderboard_qs]
    users_map = {
        u.pk: u
        for u in User.objects.filter(pk__in=user_ids).select_related('profile')
    }
    leaderboard = []
    for entry in leaderboard_qs:
        u = users_map.get(entry['user'])
        if u:
            try:
                avatar = u.profile.avatar_url or ''
            except Exception:
                avatar = ''
            leaderboard.append({
                'user': u,
                'stack_count': entry['stack_count'],
                'latest': entry['latest'],
                'avatar_url': avatar,
                'initial': (u.username[0] if u.username else '?').upper(),
            })

    # Kategorien für Filter
    categories = list(
        UserStack.objects.filter(is_approved=True)
        .exclude(category='')
        .values_list('category', flat=True)
        .distinct()
        .order_by('category')
    )

    # Stacks filtern + sortieren
    stacks_qs = UserStack.objects.filter(is_approved=True).select_related('user', 'user__profile')
    if active_category and active_category in categories:
        stacks_qs = stacks_qs.filter(category=active_category)
    if active_sort == 'likes':
        stacks_qs = stacks_qs.annotate(like_count=Count('likes')).order_by('-like_count', '-created_at')
    elif active_sort == 'views':
        stacks_qs = stacks_qs.order_by('-view_count', '-created_at')
    else:
        active_sort = 'new'
        stacks_qs = stacks_qs.order_by('-created_at')
    recent_stacks = stacks_qs[:24]

    # Gesamtstatistiken
    total_stacks = UserStack.objects.filter(is_approved=True).count()
    total_contributors = len(leaderboard_qs)

    return render(request, 'generator/community.html', {
        'leaderboard': leaderboard,
        'recent_stacks': recent_stacks,
        'total_stacks': total_stacks,
        'total_contributors': total_contributors,
        'categories': categories,
        'active_category': active_category,
        'active_sort': active_sort,
    })


# ── Visual Pod Builder ──────────────────────────────────────────────

def builder_view(request):
    stacks = StackTemplate.objects.filter(is_active=True).order_by('category', 'sort_order', 'label')
    community_stacks = UserStack.objects.filter(is_approved=True).select_related('user').order_by('name')
    return render(request, 'generator/builder.html', {'stacks': stacks, 'community_stacks': community_stacks})


@ratelimit(key='ip', rate='20/m', method='POST', block=True)
def builder_generate(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    content_type = request.content_type or ''

    if 'application/json' in content_type:
        # AJAX path — return JSON
        try:
            form_data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'error': 'invalid JSON'}, status=400)
        return JsonResponse({
            'yaml': generate(form_data),
            'shell': generate_shell(form_data),
            'warnings': validate_form_data(form_data),
        })
    else:
        # Form-POST path — render result page (same as generate_view)
        try:
            form_data = json.loads(request.POST.get('form_data_json', '{}'))
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'error': 'invalid form data'}, status=400)

        yaml_content = generate(form_data)
        shell_content = generate_shell(form_data)
        quadlet_content = generate_quadlet(form_data)
        env_file_content = generate_env_file(form_data)
        pod_name = form_data.get('pod_name', 'unnamed').strip().lower().replace(' ', '-')
        validation_warnings = validate_form_data(form_data)

        try:
            from .models import GeneratedYAML
            from .middleware import _get_ip
            images = ', '.join(
                c.get('image', '').split(':')[0].split('/')[-1]
                for c in form_data.get('containers', []) if c.get('image')
            )
            GeneratedYAML.objects.create(
                mode=form_data.get('mode', 'rootless'),
                pod_name=pod_name,
                container_count=len(form_data.get('containers', [])),
                init_count=len(form_data.get('init_containers', [])),
                images=images,
                ip=_get_ip(request),
            )
        except Exception:
            pass

        net_info = []
        for c in form_data.get('containers', []):
            ports = []
            for line in (c.get('ports') or '').splitlines():
                line = line.strip()
                if ':' in line:
                    try:
                        ports.append(int(line.split(':')[-1].split('/')[0]))
                    except ValueError:
                        pass
            if ports:
                net_info.append({'name': c.get('name', ''), 'ports': ports})

        return render(request, 'generator/result.html', {
            'yaml_content': yaml_content,
            'shell_content': shell_content,
            'quadlet_content': quadlet_content,
            'env_file_content': env_file_content,
            'pod_name': pod_name,
            'mode': form_data.get('mode', 'rootless'),
            'form_data_json': json.dumps(form_data),
            'net_info': net_info,
            'validation_warnings': validation_warnings,
            'editing_stack_id': '',
            'editing_stack_name': '',
            'editing_stack_description': '',
            'editing_stack_icon': 'bi-box',
            'editing_stack_category': '',
        })


@ratelimit(key='user_or_ip', rate='10/m', method='POST', block=False)
def compose_import(request):
    """Parse a docker-compose.yml and return canvas-compatible container state."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    if getattr(request, 'limited', False):
        return JsonResponse({'error': 'Rate limit reached — max 10 imports per minute.'}, status=429)
    try:
        body = json.loads(request.body)
        compose_text = body.get('compose', '')
        extra_env = body.get('env_vars') or {}
        if not isinstance(extra_env, dict):
            extra_env = {}
    except Exception:
        return JsonResponse({'error': 'Invalid request body'}, status=400)

    if not compose_text.strip():
        return JsonResponse({'error': 'Empty input'}, status=400)
    if len(compose_text) > 100_000:
        return JsonResponse({'error': 'Input too large (max 100 KB)'}, status=400)

    # Auto-detect: docker run / podman run command
    from .compose_parser import is_docker_run_command, parse_docker_run
    if is_docker_run_command(compose_text):
        try:
            result, _ = parse_docker_run(compose_text.strip())
            return JsonResponse(result)
        except ValueError as e:
            return JsonResponse({'error': str(e)}, status=400)

    import yaml as _yaml
    try:
        data = _yaml.safe_load(compose_text)
    except Exception as e:
        return JsonResponse({'error': f'YAML parse error: {e}'}, status=400)

    if not isinstance(data, dict) or 'services' not in data:
        return JsonResponse({'error': 'No "services" key found — is this a docker-compose.yml?'}, status=400)

    _site = SiteSettings.get_solo()
    _timeout = _site.compose_import_timeout
    if _timeout > 0:
        def _handle_alarm(signum, frame):
            raise TimeoutError()
        _old_handler = signal.signal(signal.SIGALRM, _handle_alarm)
        signal.alarm(_timeout)
    try:
        containers = []
        named_volumes = []
        x, y = 50, 50
        all_service_names = set((data.get('services') or {}).keys())
        _udp_ports_by_svc = {}   # svc_name → [port strings]
        _net_aliases_by_svc = {} # svc_name → [alias strings]
        _expose_by_svc = {}      # svc_name → [port strings]
        _user_name_warnings = {} # svc_name → username string (non-numeric user:)
    
        def _resolve_compose_vars(s):
            """Resolve ${VAR:-default} → .env value or default; ${VAR} → .env value or CHANGE_ME."""
            s = str(s)
            def _sub(m):
                full = m.group(0)
                # Extract var name (before :- or :?)
                inner = full[2:-1]  # strip ${ and }
                colon_pos = inner.find(':')
                var_name = inner[:colon_pos] if colon_pos != -1 else inner
                if var_name in extra_env:
                    return str(extra_env[var_name])
                # fallback: use default after :- or bare -
                dm = re.match(r'[^:]+:-([^}]*)', inner) or re.match(r'[^-]+-([^}]*)', inner)
                if dm:
                    return dm.group(1)
                return 'CHANGE_ME'
            s = re.sub(r'\$\{[^}]+\}', _sub, s)
            return s
    
        def _norm_image(img, svc_name):
            if not img:
                return f'docker.io/{svc_name}:latest'
            img = _resolve_compose_vars(img)
            known_registries = ('docker.io/', 'ghcr.io/', 'quay.io/', 'registry.')
            if any(img.startswith(r) for r in known_registries):
                return img
            # Check only the name segment (before the tag) for a dot → treat as registry
            name_part = img.split(':')[0]  # strip tag first
            first = name_part.split('/')[0]
            if '.' in first or first == 'localhost':
                return img  # already has registry (e.g. my.registry.com/img)
            # host:port/image pattern (e.g. registry:5000/img) — colon in first path segment
            if '/' in img and ':' in img.split('/')[0]:
                return img
            # Official library image (no slash) → add docker.io/
            if '/' not in name_part:
                return f'docker.io/{img}' if ':' in img else f'docker.io/{img}:latest'
            return f'docker.io/{img}'
    
        for svc_name, svc in (data.get('services') or {}).items():
            if not isinstance(svc, dict):
                continue
    
            image = _norm_image(svc.get('image', ''), svc_name)
    
            ports_lines = []
            seen_ports = set()
            udp_ports = []
            for p in (svc.get('ports') or []):
                try:
                    if isinstance(p, dict):
                        # Long-form: {target: 80, published: 8080, protocol: tcp}
                        if not p.get('target'):
                            continue
                        cp    = int(p['target'])
                        hp    = int(p.get('published') or cp)
                        proto = str(p.get('protocol') or '').lower()
                    else:
                        p = _resolve_compose_vars(str(p))
                        parts = p.split(':')
                        if len(parts) < 2:
                            # bare port "8080" → map 1:1
                            port_str = parts[0].split('/')[0].strip()
                            if port_str.isdigit():
                                cp = hp = int(port_str)
                                key = f'{hp}:{cp}'
                                if key not in seen_ports:
                                    seen_ports.add(key)
                                    ports_lines.append(key)
                            continue
                        # May be "ip:host:container" → last two
                        hp = int(parts[-2].rsplit('.', 1)[-1])
                        proto = ''
                        last = parts[-1]
                        if '/' in last:
                            port_str, proto = last.rsplit('/', 1)
                        else:
                            port_str = last
                        cp = int(port_str)
                    if proto == 'udp':
                        _udp_ports_by_svc.setdefault(svc_name, []).append(f'{hp}:{cp}/udp')
                        key = f'{hp}:{cp}/udp'
                    else:
                        key = f'{hp}:{cp}'
                    if key not in seen_ports:
                        seen_ports.add(key)
                        ports_lines.append(key)
                except (ValueError, IndexError, TypeError):
                    pass
    
            # expose: ports are pod-internal only — no mapping needed (all containers share localhost in a pod)
            for ep in (svc.get('expose') or []):
                try:
                    cp = int(str(ep).split('/')[0])
                    _expose_by_svc.setdefault(svc_name, []).append(str(cp))
                except (ValueError, TypeError):
                    pass
    
            env_lines = []
            env_sec = svc.get('environment') or []
            if isinstance(env_sec, dict):
                for k, v in env_sec.items():
                    v_str = _resolve_compose_vars(v) if v is not None else ''
                    v_str = v_str.strip('"\'')
                    env_lines.append(f'{k}={v_str}')
            elif isinstance(env_sec, list):
                for item in env_sec:
                    s = _resolve_compose_vars(str(item).strip())
                    if '=' in s:
                        ek, ev = s.split('=', 1)
                        s = f'{ek}={ev.strip(chr(34) + chr(39))}'
                    env_lines.append(s if '=' in s else f'{s}=')
            # Service-Namen in Env-Werten → localhost (Pod-Networking: kein DNS für Service-Namen)
            # Nur bei Keys die auf Hostname/Verbindung hindeuten (nicht DB-Name, User, Passwort etc.)
            _HOST_KEY_RE     = re.compile(r'HOST|ADDR|SERVER|ENDPOINT|DSN|CONN|URI|URL', re.IGNORECASE)
            _NON_HOST_KEY_RE = re.compile(r'PASSWORD|PASSWD|SECRET|TOKEN|KEY|USER|DATABASE|DB_NAME|DBNAME|_NAME$|_DB$', re.IGNORECASE)
            # Connection-string keys ending in _URL/_URI/_DSN/_CONN are always host keys
            # even if they contain DATABASE (e.g. DATABASE_URL)
            _CONN_KEY_RE     = re.compile(r'_URL$|_URI$|_DSN$|_CONN$', re.IGNORECASE)
            resolved_env_lines = []
            for line in env_lines:
                if '=' in line:
                    ek, ev = line.split('=', 1)
                    is_host_key = (bool(_HOST_KEY_RE.search(ek)) and not bool(_NON_HOST_KEY_RE.search(ek))) \
                                  or bool(_CONN_KEY_RE.search(ek))
                    if ev.strip() in all_service_names and is_host_key:
                        # Ganzer Wert ist ein Service-Name (z.B. PAPERLESS_DBHOST=db)
                        line = f'{ek}=localhost'
                    else:
                        for sn in all_service_names:
                            # URL ohne Auth: redis://broker:6379 → redis://localhost:6379
                            # Negative Lookahead verhindert Ersetzen des Usernamens in Auth-URLs
                            # (z.B. postgresql://user:pass@host → user bleibt, host wird ersetzt)
                            ev = re.sub(
                                r'(://)' + re.escape(sn) + r'(?!:[^@\s/]*@)(?=[:/@?#]|$)',
                                r'\1localhost',
                                ev,
                            )
                            # Auth-URL: Hostname nach @ ersetzen
                            # postgresql://user:pass@postgres:5432 → @localhost:5432
                            ev = re.sub(
                                r'(@)' + re.escape(sn) + r'(?=[:/@?#]|$)',
                                r'\1localhost',
                                ev,
                            )
                            # DSN-Format: @(db:3306) → @(localhost:3306)
                            ev = re.sub(
                                r'@\(' + re.escape(sn) + r'(:\d+)\)',
                                r'@(localhost\1)',
                                ev,
                            )
                            # host:port ohne Schema: db:3306 → localhost:3306 (nur bei HOST-Keys)
                            if is_host_key:
                                ev = re.sub(
                                    r'(?<![/\w@])' + re.escape(sn) + r'(:\d+)',
                                    r'localhost\1',
                                    ev,
                                )
                        line = f'{ek}={ev}'
                resolved_env_lines.append(line)
            env_lines = resolved_env_lines
    
            # build env lookup for volume var substitution
            _svc_env = {}
            for el in env_lines:
                if '=' in el:
                    ek, ev = el.split('=', 1)
                    _svc_env[ek.strip()] = ev.strip()
    
            def _resolve_vol_src(s):
                import re as _re
                def _sub(m):
                    key = m.group(1)
                    return _svc_env.get(key) or extra_env.get(key) or m.group(0)
                return _re.sub(r'\$\{([^}]+)\}', _sub, s)
    
            vols_lines = []
            for v in (svc.get('volumes') or []):
                if isinstance(v, dict):
                    # Long-form volume syntax
                    vtype   = str(v.get('type') or 'volume').lower()
                    if vtype == 'tmpfs':
                        continue  # tmpfs volumes: not supported, caught in warnings
                    src     = _resolve_vol_src(str(v.get('source') or ''))
                    target  = str(v.get('target') or '')
                    ro_flag = bool(v.get('read_only') or v.get('readonly'))
                    if not target:
                        continue
                else:
                    v = str(v)
                    if ':' in v:
                        src, rest = v.split(':', 1)
                        parts = rest.split(':')
                        target = parts[0]
                        ro_flag = any(p.lower() == 'ro' for p in parts[1:])
                        src = _resolve_vol_src(src)
                    elif v.startswith('/') or v.startswith('~') or v.startswith('./') or v.startswith('../'):
                        # Anonymous/bare path → derive named volume
                        anon_name = re.sub(r'^\.\.?/', '', v).strip('/').replace('/', '-').strip('-') or (svc_name + '-data')
                        anon_name = re.sub(r'^[~/]', '', anon_name).strip('/').replace('/', '-') or (svc_name + '-data')
                        if anon_name not in named_volumes:
                            named_volumes.append(anon_name)
                        vols_lines.append(f'{anon_name}:{v.split(":")[0]}')
                        continue
                    else:
                        continue
                # Relative path → named volume
                if src.startswith('./') or src.startswith('../'):
                    src = re.sub(r'^\.\.?/', '', src).replace('/', '-').strip('-') or (svc_name + '-data')
                # Track named volumes (not absolute, not home, not unresolved var)
                if src and not src.startswith('/') and not src.startswith('~') and not src.startswith('${'):
                    if src not in named_volumes:
                        named_volumes.append(src)
                entry = f'{src}:{target}' if src else target
                if ro_flag:
                    entry += ':ro'
                vols_lines.append(entry)
    
            command = ''
            args_val = ''
            ep = svc.get('entrypoint')
            if ep:
                command = _resolve_compose_vars(
                    ' '.join(str(x) for x in ep) if isinstance(ep, list) else str(ep)
                )
            cmd = svc.get('command')
            if cmd:
                args_val = _resolve_compose_vars(
                    ' '.join(str(x) for x in cmd) if isinstance(cmd, list) else str(cmd)
                )
    
            memory_limit = cpu_limit = ''
            limits = ((svc.get('deploy') or {}).get('resources') or {}).get('limits') or {}
            if limits.get('memory'):
                m = str(limits['memory']).upper().replace(' ', '')
                m = re.sub(r'([MG])$', r'\1i', m)
                memory_limit = m
            if limits.get('cpus'):
                cpu_limit = str(limits['cpus'])
    
            # user: root / 1000 / 1000:1000
            run_as_user = run_as_group = None
            user_raw = str(svc.get('user', '') or '').strip()
            if user_raw:
                if ':' in user_raw:
                    uid_s, gid_s = user_raw.split(':', 1)
                    if uid_s.isdigit():
                        run_as_user = int(uid_s)
                    elif uid_s.lower() == 'root':
                        run_as_user = 0
                    if gid_s.isdigit():
                        run_as_group = int(gid_s)
                elif user_raw.isdigit():
                    run_as_user = int(user_raw)
                elif user_raw.lower() == 'root':
                    run_as_user = 0
                else:
                    # username string (e.g. "postgres") — cannot resolve without image
                    _user_name_warnings.setdefault(svc_name, user_raw)
    
            # DB-Image ohne expliziten user + hostPath-Volume → runAsUser: 0
            # In rootless podman mappt UID 0 auf den Host-User; das Image re-execed intern als DB-User.
            if run_as_user is None and _img_base(image) in _DB_IMAGES:
                for v in (svc.get('volumes') or []):
                    src = str(v.get('source') or '') if isinstance(v, dict) else (str(v).split(':')[0] if ':' in str(v) else '')
                    if src.startswith('/') or src.startswith('./') or src.startswith('~') or src.startswith('../') or src.startswith('${'):
                        run_as_user = 0
                        break
    
            # cap_add / cap_drop
            cap_add_list = [str(c).strip() for c in (svc.get('cap_add') or []) if c]
            cap_drop_list = [str(c).strip() for c in (svc.get('cap_drop') or []) if c]
    
            containers.append({
                'id': f'c{len(containers) + 1}',
                'name': svc_name,
                'image': image,
                'x': x, 'y': y,
                'ports': '\n'.join(ports_lines),
                'volumes': '\n'.join(vols_lines),
                'env': '\n'.join(env_lines),
                'command': command,
                'args': args_val,
                'run_as_user': run_as_user,
                'run_as_group': run_as_group,
                'privileged': bool(svc.get('privileged')),
                'read_only_root': bool(svc.get('read_only')),
                'cap_add': '\n'.join(cap_add_list),
                'cap_drop': '\n'.join(cap_drop_list),
                'memory_limit': memory_limit,
                'cpu_limit': cpu_limit,
                'memory_request': '',
                'cpu_request': '',
                'working_dir': svc.get('working_dir', '') or svc.get('working_directory', '') or '',
                'liveness_probe_cmd': '',
                'liveness_initial_delay': None,
                'liveness_period': None,
                'pull_policy': '',
            })
            # network aliases
            for net_cfg in (svc.get('networks') or {}).values():
                if isinstance(net_cfg, dict):
                    for alias in (net_cfg.get('aliases') or []):
                        _net_aliases_by_svc.setdefault(svc_name, []).append(str(alias))
    
            x += 220
            if x > 700:
                x = 50
                y += 130
    
        def _parse_duration(s):
            """'30s' → 30, '1m' → 60, '1m30s' → 90. Returns int seconds or None."""
            if not s:
                return None
            total = 0
            for val, unit in re.findall(r'(\d+)([smh])', str(s)):
                total += int(val) * {'s': 1, 'm': 60, 'h': 3600}[unit]
            return total if (total or re.search(r'\d', str(s))) else None
    
        # Collect warnings for unsupported fields
        warnings = []
        all_services = data.get('services') or {}
    
        # env_file + unresolved ${VAR} in images/volumes → single .env warning
        env_file_svcs = [s for s, c in all_services.items() if isinstance(c, dict) and c.get('env_file')]
        unresolved_svcs = []
        for s, c in all_services.items():
            if not isinstance(c, dict):
                continue
            img = str(c.get('image', '') or '')
            vols = [str(v) for v in (c.get('volumes') or [])]
            if '${' in img or any('${' in v for v in vols):
                unresolved_svcs.append(s)
        dotenv_svcs = sorted(set(env_file_svcs) | set(unresolved_svcs))
        if dotenv_svcs and not extra_env:
            warnings.append({
                'msg': f"env_file / variables: {', '.join(dotenv_svcs)} use .env variables — paste your .env file so image tags and volume paths are filled in correctly",
                'fix_type': 'env_file',
                'fix_data': dotenv_svcs,
                'fix_label': 'Paste .env…',
            })
        elif env_file_svcs and extra_env:
            # .env was provided but env_file services may still have missing vars
            pass
    
        # relative volume paths (./x or ../x) or ${VAR} that resolved to relative → became PVC not hostPath
        rel_vol_svcs = []
        rel_vol_fixes = []  # [{svc, named, target}]
        for s, c in all_services.items():
            if not isinstance(c, dict):
                continue
            svc_has_rel = False
            for v in (c.get('volumes') or []):
                if isinstance(v, dict):
                    src    = str(v.get('source') or '')
                    target = str(v.get('target') or '')
                else:
                    parts  = str(v).split(':')
                    src    = parts[0] if parts else ''
                    target = parts[1] if len(parts) > 1 else ''
                # literal relative path in compose OR ${VAR} that resolved to relative
                resolved_src = _resolve_compose_vars(src) if src else ''
                orig = resolved_src if (src.startswith('${') and resolved_src) else src
                if src.startswith('./') or src.startswith('../') or (
                    src.startswith('${') and (resolved_src.startswith('./') or resolved_src.startswith('../'))
                ):
                    named = re.sub(r'^\.\.?/', '', orig).replace('/', '-').strip('-') or (s + '-data')
                    rel_vol_fixes.append({'svc': s, 'named': named, 'target': target})
                    svc_has_rel = True
            if svc_has_rel:
                rel_vol_svcs.append(s)
        if rel_vol_svcs:
            warnings.append({
                'msg': f"Relative volume paths in {', '.join(rel_vol_svcs)} were converted to named volumes (PVC). "
                       f"For host-path mounts use absolute paths in your .env (e.g. UPLOAD_LOCATION=/srv/immich/library)",
                'fix_type': 'rel_vol_hostpath',
                'fix_data': rel_vol_fixes,
                'fix_label': 'Use host path instead',
            })
    
        # shm_size — no auto-fix
        shm_svcs = [s for s, c in all_services.items() if isinstance(c, dict) and c.get('shm_size')]
        if shm_svcs:
            warnings.append({
                'msg': f"shm_size: ignored for {', '.join(shm_svcs)} — not supported in podman play kube YAML",
            })
    
        # healthcheck → livenessProbe fix
        health_fix_data = []
        for s, c in all_services.items():
            if not isinstance(c, dict):
                continue
            hc = c.get('healthcheck')
            if not hc or hc.get('disable'):
                continue
            test = hc.get('test', [])
            if test in (['NONE'], 'NONE'):
                continue
            if isinstance(test, list) and len(test) >= 2 and test[0] in ('CMD', 'CMD-SHELL'):
                cmd = ' '.join(str(t) for t in test[1:])
            elif isinstance(test, list) and test:
                cmd = ' '.join(str(t) for t in test)
            elif isinstance(test, str):
                cmd = test
            else:
                cmd = ''
            if cmd:
                health_fix_data.append({
                    'svc': s,
                    'cmd': cmd,
                    'initial_delay': _parse_duration(hc.get('start_period')) or 30,
                    'period': _parse_duration(hc.get('interval')) or 10,
                })
        if health_fix_data:
            svcs = ', '.join(d['svc'] for d in health_fix_data)
            warnings.append({
                'msg': f"healthcheck: detected for {svcs} — apply fix to convert to livenessProbe",
                'fix_type': 'healthcheck',
                'fix_data': health_fix_data,
                'fix_label': 'Apply as livenessProbe',
            })
    
        # build: without image → placeholder fix
        build_fix_data = [
            {'svc': s, 'image': f'{s}:latest'}
            for s, c in all_services.items()
            if isinstance(c, dict) and c.get('build') and not c.get('image')
        ]
        if build_fix_data:
            svcs = ', '.join(d['svc'] for d in build_fix_data)
            warnings.append({
                'msg': f"build: not supported for {svcs} — apply fix to set placeholder image (<name>:latest)",
                'fix_type': 'build_placeholder',
                'fix_data': build_fix_data,
                'fix_label': 'Set placeholder image',
            })
    
        # secrets: warning (not supported in podman play kube)
        secrets_svcs = [s for s, c in all_services.items() if isinstance(c, dict) and c.get('secrets')]
        if secrets_svcs:
            warnings.append({
                'msg': f"secrets: not supported for {', '.join(secrets_svcs)} — pass secrets as env vars instead",
            })
    
        # tmpfs: (key or long-form volume type)
        tmpfs_svcs = []
        for s, c in all_services.items():
            if not isinstance(c, dict):
                continue
            if c.get('tmpfs'):
                tmpfs_svcs.append(s)
            elif any(isinstance(v, dict) and str(v.get('type', '')).lower() == 'tmpfs'
                     for v in (c.get('volumes') or [])):
                tmpfs_svcs.append(s)
        if tmpfs_svcs:
            warnings.append({
                'msg': f"tmpfs: not supported in podman play kube for {', '.join(tmpfs_svcs)} — use an emptyDir volume instead",
            })

        # devices: (GPU, /dev/dri, etc.)
        devices_svcs = [s for s, c in all_services.items()
                        if isinstance(c, dict) and c.get('devices')]
        if devices_svcs:
            warnings.append({
                'msg': f"devices: not supported in podman play kube for {', '.join(devices_svcs)} — configure device access via annotations or quadlet options after deploy",
            })

        # sysctls: / ulimits:
        sysctls_svcs = [s for s, c in all_services.items() if isinstance(c, dict) and c.get('sysctls')]
        ulimits_svcs = [s for s, c in all_services.items() if isinstance(c, dict) and c.get('ulimits')]
        if sysctls_svcs:
            warnings.append({
                'msg': f"sysctls: ignored for {', '.join(sysctls_svcs)} — set kernel parameters on the host or via quadlet options",
            })
        if ulimits_svcs:
            warnings.append({
                'msg': f"ulimits: ignored for {', '.join(ulimits_svcs)} — not supported in podman play kube YAML",
            })

        # ipc: host / pid: host
        ipc_svcs = [s for s, c in all_services.items()
                    if isinstance(c, dict) and str(c.get('ipc') or '').lower() == 'host']
        pid_svcs = [s for s, c in all_services.items()
                    if isinstance(c, dict) and str(c.get('pid') or '').lower() == 'host']
        has_host_ipc = bool(ipc_svcs)
        has_host_pid = bool(pid_svcs)
        if ipc_svcs:
            warnings.append({
                'msg': f"ipc: host set for {', '.join(ipc_svcs)} — applied as pod-level hostIPC",
            })
        if pid_svcs:
            warnings.append({
                'msg': f"pid: host set for {', '.join(pid_svcs)} — applied as pod-level hostPID",
            })

        # volumes_from: (legacy)
        vols_from_svcs = [s for s, c in all_services.items() if isinstance(c, dict) and c.get('volumes_from')]
        if vols_from_svcs:
            warnings.append({
                'msg': f"volumes_from: not supported for {', '.join(vols_from_svcs)} — share data via named volumes instead",
            })

        # init: true
        init_svcs = [s for s, c in all_services.items() if isinstance(c, dict) and c.get('init')]
        if init_svcs:
            warnings.append({
                'msg': f"init: true ignored for {', '.join(init_svcs)} — no init process in podman play kube pods; use tini as entrypoint if needed",
            })

        # profiles: (services scoped to specific compose profiles)
        profile_svcs = [s for s, c in all_services.items() if isinstance(c, dict) and c.get('profiles')]
        if profile_svcs:
            warnings.append({
                'msg': f"profiles: all services imported regardless of profile — {', '.join(profile_svcs)} have profiles defined",
            })

        # depends_on: (ordering not supported in pods)
        depends_svcs = [s for s, c in all_services.items() if isinstance(c, dict) and c.get('depends_on')]
        if depends_svcs:
            warnings.append({
                'msg': f"depends_on: ignored for {', '.join(depends_svcs)} — pod containers start in parallel; use liveness/readiness probes or init containers for ordering",
            })

        # stdin_open / tty (interactive mode not supported)
        interactive_svcs = [s for s, c in all_services.items()
                            if isinstance(c, dict) and (c.get('stdin_open') or c.get('tty'))]
        if interactive_svcs:
            warnings.append({
                'msg': f"stdin_open/tty: ignored for {', '.join(interactive_svcs)} — interactive mode not supported in podman play kube",
            })

        # links: (legacy, DNS handled by pod localhost)
        links_svcs = [s for s, c in all_services.items() if isinstance(c, dict) and c.get('links')]
        if links_svcs:
            warnings.append({
                'msg': f"links: ignored for {', '.join(links_svcs)} — all containers in a pod share localhost, no DNS aliases needed",
            })

        # dns: → pod-level dnsConfig.nameservers
        seen_dns = []
        for s, c in all_services.items():
            if not isinstance(c, dict):
                continue
            dns_val = c.get('dns') or []
            if isinstance(dns_val, str):
                dns_val = [dns_val]
            for entry in dns_val:
                entry = str(entry).strip()
                if entry and entry not in seen_dns:
                    seen_dns.append(entry)
        if seen_dns:
            warnings.append({
                'msg': f"dns: applied as pod-level DNS nameservers: {', '.join(seen_dns)}",
            })

        # container_name: (overrides service name — lost on import)
        renamed_svcs = [(s, c['container_name']) for s, c in all_services.items()
                        if isinstance(c, dict) and c.get('container_name') and c['container_name'] != s]
        if renamed_svcs:
            parts = ', '.join(f'{s}→{n}' for s, n in renamed_svcs)
            warnings.append({
                'msg': f"container_name: ignored — service name used instead ({parts})",
            })

        # network_mode: host → set pod hostNetwork; other modes warn
        has_host_network = False
        net_mode_svcs = []
        for s, c in all_services.items():
            if not isinstance(c, dict):
                continue
            nm = str(c.get('network_mode', '') or '').lower().strip()
            if nm == 'host':
                has_host_network = True
            elif nm and nm not in ('', 'bridge'):
                net_mode_svcs.append(s)
        if net_mode_svcs:
            warnings.append({
                'msg': f"network_mode: ignored for {', '.join(net_mode_svcs)} — all containers share pod localhost",
            })
    
        # UDP ports — info that protocol: UDP will be set in YAML
        if _udp_ports_by_svc:
            parts = [f"{s}: {', '.join(p)}" for s, p in _udp_ports_by_svc.items()]
            warnings.append({
                'msg': f"UDP ports detected — will be mapped with protocol: UDP in the generated YAML: {'; '.join(parts)}",
            })
    
        # expose: ports — inform that no mapping is needed in a pod
        if _expose_by_svc:
            parts = [f"{s}: {', '.join(p)}" for s, p in _expose_by_svc.items()]
            warnings.append({
                'msg': f"expose: ports not mapped — in a Podman pod all containers share localhost, so {'; '.join(parts)} are reachable pod-internally without any port mapping",
            })
    
        # network aliases — warn that they are dropped
        if _net_aliases_by_svc:
            parts = [f"{s}: {', '.join(a)}" for s, a in _net_aliases_by_svc.items()]
            warnings.append({
                'msg': f"Network aliases dropped — not supported in pod networking. "
                       f"Add them manually as host aliases if containers reference these hostnames: {'; '.join(parts)}",
            })
    
        # extra_hosts → pod-level host_aliases (ip hostname format)
        seen_host_entries = set()
        host_aliases_lines = []
        for svc in all_services.values():
            if not isinstance(svc, dict):
                continue
            extra_hosts = svc.get('extra_hosts') or {}
            if isinstance(extra_hosts, list):
                for entry in extra_hosts:
                    entry = str(entry)
                    sep = ':' if ':' in entry else ('=' if '=' in entry else None)
                    if sep:
                        hostname, ip = entry.split(sep, 1)
                        key = f'{ip.strip()} {hostname.strip()}'
                        if key not in seen_host_entries:
                            seen_host_entries.add(key)
                            host_aliases_lines.append(key)
            elif isinstance(extra_hosts, dict):
                for hostname, ip in extra_hosts.items():
                    key = f'{str(ip).strip()} {str(hostname).strip()}'
                    if key not in seen_host_entries:
                        seen_host_entries.add(key)
                        host_aliases_lines.append(key)
    
        # password/secret fields → offer to generate secure values
        _PWD_KEY_RE     = re.compile(r'PASSWORD|PASSWD|SECRET|TOKEN', re.IGNORECASE)
        _PWD_EXCL_RE    = re.compile(r'_FILE$|_PATH$|_ALGO$|_HASH$|_TYPE$|_SALT$|_PEPPER$|_ENCODING$', re.IGNORECASE)
        pwd_fix_data = []
        for ctr in containers:
            for line in (ctr.get('env') or '').splitlines():
                if '=' in line:
                    ek, ev = line.split('=', 1)
                    ek, ev = ek.strip(), ev.strip()
                    if ev and _PWD_KEY_RE.search(ek) and not _PWD_EXCL_RE.search(ek):
                        pwd_fix_data.append({'svc': ctr['name'], 'key': ek, 'value': ev})
        if pwd_fix_data:
            n = len(pwd_fix_data)
            warnings.append({
                'msg': f"{n} password/secret field{'s' if n > 1 else ''} imported from compose — review or generate secure values before deploying",
                'fix_type': 'passwords',
                'fix_data': pwd_fix_data,
                'fix_label': 'Set passwords…',
            })
    
        # user: with non-numeric username → silently dropped
        if _user_name_warnings:
            parts = ', '.join(f'{s} ({u!r})' for s, u in _user_name_warnings.items())
            warnings.append({
                'msg': f"user: username strings ignored for {parts} — only numeric UIDs or 'root' are supported; check the image docs for the correct UID",
            })

        # extends: (service inheritance — not resolved)
        extends_svcs = [s for s, c in all_services.items() if isinstance(c, dict) and c.get('extends')]
        if extends_svcs:
            warnings.append({
                'msg': f"extends: not resolved for {', '.join(extends_svcs)} — service inheritance is not supported; merge fields manually",
            })

        # deploy.replicas: (swarm scaling — not supported)
        replicas_svcs = [s for s, c in all_services.items()
                         if isinstance(c, dict) and (c.get('deploy') or {}).get('replicas')]
        if replicas_svcs:
            warnings.append({
                'msg': f"deploy.replicas: ignored for {', '.join(replicas_svcs)} — pod scaling not supported in podman play kube; use a Deployment resource instead",
            })

        # service-level hostname: (different from pod hostname)
        svc_hostnames = [s for s, c in all_services.items() if isinstance(c, dict) and c.get('hostname')]
        if svc_hostnames:
            warnings.append({
                'msg': f"hostname: ignored for {', '.join(svc_hostnames)} — per-container hostnames not supported; all containers share the pod hostname",
            })

        # labels: (silently dropped)
        labels_svcs = [s for s, c in all_services.items() if isinstance(c, dict) and c.get('labels')]
        if labels_svcs:
            warnings.append({
                'msg': f"labels: ignored for {', '.join(labels_svcs)} — add as pod annotations manually if needed",
            })

        # mixed restart policies across services
        restart_policies = set()
        for svc in all_services.values():
            if isinstance(svc, dict) and 'restart' in svc:
                val = svc['restart']
                if val is False:
                    val = 'no'
                restart_policies.add(str(val).lower())
        pod_restart = 'Always'
        if restart_policies == {'no'}:
            pod_restart = 'Never'
        elif 'on-failure' in restart_policies and 'always' not in restart_policies and 'unless-stopped' not in restart_policies:
            pod_restart = 'OnFailure'
        if len(restart_policies) > 1:
            warnings.append({
                'msg': f"mixed restart policies ({', '.join(sorted(restart_policies))}) — pods use a single policy; using '{pod_restart}'",
            })
    
        return JsonResponse({
            'ok': True,
            'containers': containers,
            'named_volumes': named_volumes,
            'restart_policy': pod_restart,
            'host_network': has_host_network,
            'host_pid': has_host_pid,
            'host_ipc': has_host_ipc,
            'dns': '\n'.join(seen_dns),
            'host_aliases': '\n'.join(host_aliases_lines),
            'warnings': warnings,
            'env_file_svcs': env_file_svcs,
        })
    except TimeoutError:
        return JsonResponse({'error': f'Import timed out ({_timeout}s)'}, status=408)
    finally:
        if _timeout > 0:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, _old_handler)


@ratelimit(key='ip', rate='20/m', method='POST', block=True)
def pod_yaml_import(request):
    """Parse a Pod YAML and return canvas-compatible container state."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    if getattr(request, 'limited', False):
        return JsonResponse({'error': 'Rate limit reached.'}, status=429)
    try:
        body = json.loads(request.body)
        yaml_text = body.get('yaml', '')
    except Exception:
        return JsonResponse({'error': 'Invalid request body'}, status=400)

    if not yaml_text.strip():
        return JsonResponse({'error': 'Empty input'}, status=400)
    if len(yaml_text) > 100_000:
        return JsonResponse({'error': 'Input too large (max 100 KB)'}, status=400)

    from .pod_parser import parse_pod_yaml
    try:
        result = parse_pod_yaml(yaml_text)
        return JsonResponse(result)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
