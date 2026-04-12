"""
Parses docker-compose / podman-compose YAML and docker/podman run commands → stack_data format.
"""
import re
import shlex
import yaml


def _ports_to_str(ports):
    """List of ports → multiline string."""
    out = []
    for p in (ports or []):
        out.append(str(p).strip('"').strip("'"))
    return '\n'.join(out)


def _env_to_str(env):
    """env as list or dict → KEY=VALUE string."""
    out = []
    if isinstance(env, dict):
        for k, v in env.items():
            out.append(f'{k}={v}' if v is not None else k)
    elif isinstance(env, list):
        for item in env:
            out.append(str(item))
    return '\n'.join(out)


def _volumes_to_str(volumes):
    """Volume list → src:target string, relative paths → ~/..."""
    out = []
    for v in (volumes or []):
        if isinstance(v, dict):
            vtype = v.get('type', 'volume')
            if vtype == 'tmpfs':
                continue  # tmpfs hat kein persistentes Äquivalent → überspringen
            src = v.get('source', '')
            tgt = v.get('target', '')
            ro = ':ro' if v.get('read_only') else ''
            v = f'{src}:{tgt}{ro}' if src else tgt
        v = str(v)
        # Relativen Pfad zu absolutem machen
        if v.startswith('./') or v.startswith('../'):
            v = re.sub(r'^\.\.?/', '~/', v)
        out.append(v)
    return '\n'.join(out)


def _slug(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def parse_compose(content: str, filename: str = 'compose') -> dict:
    """
    Parses docker-compose YAML and returns stack_data.
    Raises ValueError on invalid format.
    """
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as e:
        raise ValueError(f'Invalid YAML: {e}')

    if not isinstance(data, dict):
        raise ValueError('Not a valid Compose file.')

    services = data.get('services') or {}
    if not services:
        raise ValueError('No services found in Compose file.')

    # Pod-Name aus Dateiname ableiten
    pod_name = _slug(re.sub(r'\.(ya?ml)$', '', filename, flags=re.I) or 'myapp')
    if pod_name in ('docker-compose', 'compose', 'podman-compose'):
        pod_name = _slug(next(iter(services)))

    containers = []
    init_containers = []

    for svc_name, svc in services.items():
        if not isinstance(svc, dict):
            continue

        raw_cmd = svc.get('command')
        raw_ep = svc.get('entrypoint')
        c = {
            'name':    svc_name,
            'image':   svc.get('image', ''),
            'ports':   _ports_to_str(svc.get('ports', [])),
            'env':     _env_to_str(svc.get('environment') or svc.get('env', [])),
            'volumes': _volumes_to_str(svc.get('volumes', [])),
            # entrypoint → command (overrides ENTRYPOINT), command → args (overrides CMD)
            'command': (' '.join(raw_ep) if isinstance(raw_ep, list) else (raw_ep or '')),
            'args':    (' '.join(raw_cmd) if isinstance(raw_cmd, list) else (raw_cmd or '')),
        }

        # Ressourcen
        deploy = svc.get('deploy', {}) or {}
        resources = (deploy.get('resources') or {}).get('limits') or {}
        mem = svc.get('mem_limit') or resources.get('memory', '')
        cpu = svc.get('cpus') or resources.get('cpus', '')
        if mem:
            c['memory_limit'] = str(mem).upper().replace('B', '').replace(' ', '')
        if cpu:
            c['cpu_limit'] = str(cpu)

        # User
        user = str(svc.get('user', '') or '')
        if ':' in user:
            uid, gid = user.split(':', 1)
            if uid.isdigit():
                c['run_as_user'] = int(uid)
            if gid.isdigit():
                c['run_as_group'] = int(gid)
        elif user.isdigit():
            c['run_as_user'] = int(user)

        # Privileged
        if svc.get('privileged'):
            c['privileged'] = True

        # Init-Container erkennen
        if svc.get('x-init') or 'init' in svc_name.lower():
            init_containers.append(c)
        else:
            containers.append(c)

    if not containers and init_containers:
        containers = init_containers
        init_containers = []

    # Rootful erforderlich wenn Docker/Podman-Socket gemountet wird
    all_vols = ' '.join(
        c.get('volumes', '') for c in containers + init_containers
    )
    needs_rootful = '/var/run/docker.sock' in all_vols or '/run/podman/podman.sock' in all_vols

    stack_data = {
        'pod_name':       pod_name,
        'restart_policy': 'Always',
        'mode':           'rootful' if needs_rootful else 'rootless',
        'containers':     containers,
    }
    if init_containers:
        stack_data['init_containers'] = init_containers

    return stack_data, pod_name


# ── docker run / podman run parser ────────────────────────────────────────────

_RESTART_MAP = {
    'always': 'Always',
    'unless-stopped': 'Always',
    'on-failure': 'OnFailure',
    'no': 'Never',
    'never': 'Never',
}

_KNOWN_REGISTRIES = ('docker.io/', 'ghcr.io/', 'quay.io/', 'registry.')

def _norm_image(img):
    if not img:
        return img
    known = ('docker.io/', 'ghcr.io/', 'quay.io/', 'registry.')
    if any(img.startswith(r) for r in known):
        return img
    name_part = img.split(':')[0].split('@')[0]
    first = name_part.split('/')[0]
    if '.' in first or first == 'localhost':
        return img
    if '/' not in name_part:
        return f'docker.io/{img}' if ':' in img else f'docker.io/{img}:latest'
    return f'docker.io/{img}'


def parse_docker_run(command: str) -> tuple:
    """
    Parses a docker run / podman run command string → (stack_data, pod_name).
    Raises ValueError on invalid input.
    """
    # Normalize: join backslash-newline continuations, collapse whitespace
    command = re.sub(r'\\\s*\n', ' ', command)
    command = re.sub(r'\s+', ' ', command).strip()
    try:
        tokens = shlex.split(command)
    except ValueError as e:
        raise ValueError(f'Cannot parse command: {e}')

    # Strip leading sudo / env vars
    while tokens and (tokens[0] == 'sudo' or '=' in tokens[0]):
        tokens.pop(0)

    # Expect: docker run ... / podman run ...
    if len(tokens) < 2:
        raise ValueError('No docker/podman run command found.')
    if tokens[0].lower() not in ('docker', 'podman'):
        raise ValueError(f'Expected "docker" or "podman", got "{tokens[0]}".')
    if tokens[1].lower() != 'run':
        raise ValueError(f'Expected "run" subcommand, got "{tokens[1]}".')
    tokens = tokens[2:]

    # Flags with a value argument
    _VALUE_FLAGS = {
        '--name', '--publish', '-p', '--volume', '-v', '--env', '-e',
        '--restart', '--user', '-u', '--memory', '-m', '--cpus',
        '--entrypoint', '--workdir', '-w', '--cap-add', '--cap-drop',
        '--hostname', '-h', '--network', '--label', '-l',
        '--health-cmd', '--health-interval', '--health-retries',
        '--health-start-period', '--health-timeout',
        '--log-driver', '--log-opt', '--dns', '--add-host',
        '--ulimit', '--tmpfs', '--device', '--pid', '--ipc',
        '--env-file', '--pull', '--platform', '--stop-signal',
        '--stop-timeout', '--runtime', '--security-opt',
        '--pod',
    }

    name = ''
    image = ''
    ports = []
    volumes = []
    env = []
    restart = 'Always'
    run_as_user = None
    run_as_group = None
    memory_limit = ''
    cpu_limit = ''
    command_val = ''
    args_val = ''
    working_dir = ''
    cap_add = []
    cap_drop = []
    privileged = False
    read_only = False
    host_network = False
    host_pid = False
    host_ipc = False
    hostname = ''
    dns_servers = []
    add_hosts = []
    warnings = []

    i = 0
    while i < len(tokens):
        tok = tokens[i]

        # -- Image + CMD args (first non-flag token)
        if not tok.startswith('-'):
            image = tok
            # Everything after image = args to container
            rest = tokens[i+1:]
            if rest:
                args_val = ' '.join(shlex.quote(a) for a in rest)
            break

        # --flag=value form
        val = None
        if '=' in tok:
            tok, val = tok.split('=', 1)

        # Boolean flags
        if tok in ('--privileged',):
            privileged = True
            i += 1
            continue
        if tok in ('--read-only', '--read-only-root-filesystem'):
            read_only = True
            i += 1
            continue
        if tok in ('--detach', '-d', '--rm', '--tty', '-t', '--interactive', '-i',
                   '--sig-proxy', '--no-healthcheck', '--init',
                   '--oom-kill-disable', '--disable-content-trust'):
            i += 1
            continue

        # Flags that require a value
        if tok in _VALUE_FLAGS:
            if val is None:
                i += 1
                if i >= len(tokens):
                    break
                val = tokens[i]

            if tok == '--name':
                name = val
            elif tok in ('--publish', '-p'):
                ports.append(val)
            elif tok in ('--volume', '-v'):
                v = val
                if v.startswith('./') or v.startswith('../'):
                    v = re.sub(r'^\.\.?/', '~/', v)
                volumes.append(v)
            elif tok in ('--env', '-e'):
                env.append(val)
            elif tok == '--restart':
                restart = _RESTART_MAP.get(val.lower(), 'Always')
            elif tok in ('--user', '-u'):
                u = str(val)
                if ':' in u:
                    uid, gid = u.split(':', 1)
                    if uid.isdigit(): run_as_user = int(uid)
                    if gid.isdigit(): run_as_group = int(gid)
                elif u.isdigit():
                    run_as_user = int(u)
                else:
                    warnings.append(f'Non-numeric user "{u}" — skipped.')
            elif tok in ('--memory', '-m'):
                memory_limit = val.upper().replace('B', '').replace(' ', '')
            elif tok == '--cpus':
                cpu_limit = val
            elif tok == '--entrypoint':
                command_val = val
            elif tok in ('--workdir', '-w'):
                working_dir = val
            elif tok == '--cap-add':
                cap_add.append(val)
            elif tok == '--cap-drop':
                cap_drop.append(val)
            elif tok in ('--hostname', '-h'):
                hostname = val
            elif tok == '--pid':
                if val == 'host':
                    host_pid = True
            elif tok == '--ipc':
                if val == 'host':
                    host_ipc = True
            elif tok == '--dns':
                dns_servers.append(val)
            elif tok == '--add-host':
                # format: host:ip → "ip hostname" for host_aliases
                if ':' in val:
                    h, ip = val.split(':', 1)
                    add_hosts.append(f'{ip} {h}')
                else:
                    add_hosts.append(val)
            elif tok == '--network':
                if val == 'host':
                    host_network = True
                elif val not in ('bridge', 'none', 'default'):
                    warnings.append(f'Network "{val}" ignored — not supported in pod mode.')

        i += 1

    if not image:
        raise ValueError('No image found in docker run command.')

    image = _norm_image(image)
    container_name = name or _slug(image.split('/')[-1].split(':')[0])
    pod_name = _slug(name) if name else _slug(image.split('/')[-1].split(':')[0])

    all_vols = '\n'.join(volumes)
    needs_rootful = '/var/run/docker.sock' in all_vols or '/run/podman/podman.sock' in all_vols

    container = {
        'id': 'c1',
        'name': container_name,
        'image': image,
        'x': 50, 'y': 50,
        'ports': '\n'.join(ports),
        'volumes': all_vols,
        'env': '\n'.join(env),
        'command': command_val,
        'args': args_val,
        'run_as_user': run_as_user,
        'run_as_group': run_as_group,
        'privileged': privileged,
        'read_only_root': read_only,
        'cap_add': '\n'.join(cap_add),
        'cap_drop': '\n'.join(cap_drop),
        'memory_limit': memory_limit,
        'cpu_limit': cpu_limit,
        'memory_request': '',
        'cpu_request': '',
        'working_dir': working_dir,
        'liveness_probe_cmd': '',
        'liveness_initial_delay': None,
        'liveness_period': None,
        'pull_policy': '',
    }

    named_volumes = []
    for v in volumes:
        src = v.split(':')[0]
        is_named = not (src.startswith('/') or src.startswith('~') or
                        src.startswith('./') or src.startswith('../'))
        if is_named and src not in named_volumes:
            named_volumes.append(src)

    host_aliases_str = '\n'.join(add_hosts)

    return {
        'ok': True,
        'containers': [container],
        'named_volumes': named_volumes,
        'restart_policy': restart,
        'host_network': host_network,
        'host_pid': host_pid,
        'host_ipc': host_ipc,
        'dns': '\n'.join(dns_servers),
        'host_aliases': host_aliases_str,
        'warnings': [{'msg': w} for w in warnings],
        'env_file_svcs': [],
        'mode': 'rootful' if needs_rootful else 'rootless',
    }, pod_name


def is_docker_run_command(text: str) -> bool:
    """Returns True if text looks like a docker/podman run command."""
    t = text.strip().lstrip('sudo').strip()
    return bool(re.match(r'^(docker|podman)\s+run\b', t, re.I))
