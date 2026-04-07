"""
Parses docker-compose / podman-compose YAML → stack_data format.
"""
import re
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
            src = v.get('source', '')
            tgt = v.get('target', '')
            v = f'{src}:{tgt}' if src else tgt
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

    stack_data = {
        'pod_name':       pod_name,
        'restart_policy': 'Always',
        'mode':           'rootless',
        'containers':     containers,
    }
    if init_containers:
        stack_data['init_containers'] = init_containers

    return stack_data, pod_name
