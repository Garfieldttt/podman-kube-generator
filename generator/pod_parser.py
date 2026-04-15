"""
Parses Kubernetes Pod YAML (kind: Pod) → canvas-compatible builder state.
Same output format as compose_import.
"""
import re
import yaml


def _ports_from_container(c):
    lines = []
    for p in (c.get('ports') or []):
        host = p.get('hostPort')
        cont = p.get('containerPort')
        if cont is None:
            continue
        proto = (p.get('protocol') or 'TCP').upper()
        suffix = f'/{proto}' if proto not in ('TCP', '') else ''
        if host is not None:
            lines.append(f'{host}:{cont}{suffix}')
        else:
            lines.append(f'{cont}{suffix}')
    return '\n'.join(lines)


def _env_from_container(c):
    lines = []
    for e in (c.get('env') or []):
        key = e.get('name', '')
        val = e.get('value')
        if key:
            lines.append(f'{key}={val if val is not None else ""}')
    return '\n'.join(lines)


def _volumes_from_container(c, volume_map):
    """
    volume_map: {vol_name: source_string}
      PVC  → claimName   (named volume)
      host → /host/path
      emptyDir → '' (skip)
    """
    lines = []
    for vm in (c.get('volumeMounts') or []):
        name = vm.get('name', '')
        mount = vm.get('mountPath', '')
        if not mount:
            continue
        src = volume_map.get(name)
        if src is None:
            src = name  # fallback: treat as named volume
        if src == '':
            continue    # emptyDir: skip
        ro = ':ro' if vm.get('readOnly') else ''
        lines.append(f'{src}:{mount}{ro}')
    return '\n'.join(lines)


def _cmd_args(c):
    """command/args lists → space-joined strings."""
    cmd_list = c.get('command') or []
    args_list = c.get('args') or []
    command = ' '.join(str(x) for x in cmd_list) if cmd_list else ''
    args = ' '.join(str(x) for x in args_list) if args_list else ''
    return command, args


def _resources(c):
    res = c.get('resources') or {}
    limits = res.get('limits') or {}
    requests = res.get('requests') or {}
    return (
        str(limits.get('memory') or ''),
        str(limits.get('cpu') or ''),
        str(requests.get('memory') or ''),
        str(requests.get('cpu') or ''),
    )


def _parse_probe(probe):
    """Returns dict with all probe fields for builder state."""
    if not probe:
        return {
            'probe_type': 'exec', 'probe_cmd': '',
            'http_path': '/health', 'http_port': None, 'tcp_port': None,
            'initial_delay': None, 'period': None, 'failure_threshold': None,
        }
    delay = probe.get('initialDelaySeconds')
    period = probe.get('periodSeconds')
    failure = probe.get('failureThreshold')
    if probe.get('httpGet'):
        hg = probe['httpGet']
        return {
            'probe_type': 'httpGet',
            'probe_cmd': '',
            'http_path': hg.get('path') or '/',
            'http_port': hg.get('port'),
            'tcp_port': None,
            'initial_delay': delay,
            'period': period,
            'failure_threshold': failure,
        }
    if probe.get('tcpSocket'):
        ts = probe['tcpSocket']
        return {
            'probe_type': 'tcpSocket',
            'probe_cmd': '',
            'http_path': '/health',
            'http_port': None,
            'tcp_port': ts.get('port'),
            'initial_delay': delay,
            'period': period,
            'failure_threshold': failure,
        }
    exec_probe = probe.get('exec') or {}
    cmd_list = exec_probe.get('command') or []
    cmd = ' '.join(str(x) for x in cmd_list) if cmd_list else ''
    return {
        'probe_type': 'exec',
        'probe_cmd': cmd,
        'http_path': '/health',
        'http_port': None,
        'tcp_port': None,
        'initial_delay': delay,
        'period': period,
        'failure_threshold': failure,
    }


def _pull_policy(c):
    p = c.get('imagePullPolicy') or ''
    mapping = {'IfNotPresent': 'IfNotPresent', 'Always': 'Always', 'Never': 'Never'}
    return mapping.get(p, '')


def _build_volume_map(spec):
    """volumes list → {name: source_string}"""
    volume_map = {}
    for v in (spec.get('volumes') or []):
        name = v.get('name', '')
        if not name:
            continue
        if 'persistentVolumeClaim' in v:
            claim = (v['persistentVolumeClaim'] or {}).get('claimName', name)
            volume_map[name] = claim
        elif 'hostPath' in v:
            path = (v['hostPath'] or {}).get('path', '')
            volume_map[name] = path
        elif 'emptyDir' in v:
            volume_map[name] = ''  # skip
        else:
            volume_map[name] = name  # fallback
    return volume_map


def parse_pod_yaml(content: str) -> dict:
    """
    Parses a Pod YAML and returns canvas-compatible state dict.
    Raises ValueError on invalid input.
    """
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as e:
        raise ValueError(f'YAML parse error: {e}')

    if not isinstance(data, dict):
        raise ValueError('Not a valid YAML document.')

    kind = str(data.get('kind') or '').strip()
    if kind != 'Pod':
        raise ValueError(f'Expected kind: Pod, got: {kind or "(missing)"}')

    metadata = data.get('metadata') or {}
    spec = data.get('spec') or {}

    pod_name = re.sub(r'[^a-z0-9-]', '', str(metadata.get('name') or 'pod').lower()).strip('-') or 'pod'

    restart_raw = str(spec.get('restartPolicy') or 'Always')
    restart_map = {'Always': 'Always', 'OnFailure': 'OnFailure', 'Never': 'Never'}
    restart_policy = restart_map.get(restart_raw, 'Always')

    host_network = bool(spec.get('hostNetwork'))
    host_pid = bool(spec.get('hostPID'))
    host_ipc = bool(spec.get('hostIPC'))

    dns_lines = []
    dns_cfg = spec.get('dnsConfig') or {}
    for ns in (dns_cfg.get('nameservers') or []):
        dns_lines.append(str(ns))

    host_aliases_lines = []
    for ha in (spec.get('hostAliases') or []):
        ip = ha.get('ip', '')
        hostnames = [str(h) for h in (ha.get('hostnames') or []) if h]
        if ip and hostnames:
            host_aliases_lines.append(f'{ip} {" ".join(hostnames)}')

    volume_map = _build_volume_map(spec)

    named_volumes = [src for src in volume_map.values()
                     if src and not src.startswith('/')]

    warnings = []
    containers = []
    x, y = 50, 50

    all_containers = list(spec.get('containers') or [])
    init_containers = list(spec.get('initContainers') or [])

    if init_containers:
        warnings.append({'msg': f'{len(init_containers)} init container(s) found — not imported into builder (add manually if needed)'})

    for c in all_containers:
        name = str(c.get('name') or f'container{len(containers)+1}')
        image = str(c.get('image') or '')

        sc = c.get('securityContext') or {}
        run_as_user = sc.get('runAsUser')
        run_as_group = sc.get('runAsGroup')
        privileged = bool(sc.get('privileged'))
        read_only_root = bool(sc.get('readOnlyRootFilesystem'))
        caps = sc.get('capabilities') or {}
        cap_add = '\n'.join(str(x) for x in (caps.get('add') or []))
        cap_drop = '\n'.join(str(x) for x in (caps.get('drop') or []))

        mem_limit, cpu_limit, mem_req, cpu_req = _resources(c)
        command, args = _cmd_args(c)
        lp = _parse_probe(c.get('livenessProbe'))
        rp = _parse_probe(c.get('readinessProbe'))

        containers.append({
            'id': f'c{len(containers)+1}',
            'name': name,
            'image': image,
            'x': x, 'y': y,
            'ports': _ports_from_container(c),
            'volumes': _volumes_from_container(c, volume_map),
            'env': _env_from_container(c),
            'command': command,
            'args': args,
            'run_as_user': run_as_user,
            'run_as_group': run_as_group,
            'privileged': privileged,
            'read_only_root': read_only_root,
            'cap_add': cap_add,
            'cap_drop': cap_drop,
            'memory_limit': mem_limit,
            'cpu_limit': cpu_limit,
            'memory_request': mem_req,
            'cpu_request': cpu_req,
            'working_dir': c.get('workingDir') or '',
            'liveness_probe_type': lp['probe_type'],
            'liveness_probe_cmd': lp['probe_cmd'],
            'liveness_http_path': lp['http_path'],
            'liveness_http_port': lp['http_port'],
            'liveness_tcp_port': lp['tcp_port'],
            'liveness_initial_delay': lp['initial_delay'],
            'liveness_period': lp['period'],
            'liveness_failure_threshold': lp['failure_threshold'],
            'readiness_probe_type': rp['probe_type'],
            'readiness_probe_cmd': rp['probe_cmd'],
            'readiness_http_path': rp['http_path'],
            'readiness_http_port': rp['http_port'],
            'readiness_tcp_port': rp['tcp_port'],
            'readiness_initial_delay': rp['initial_delay'],
            'readiness_period': rp['period'],
            'readiness_failure_threshold': rp['failure_threshold'],
            'pull_policy': _pull_policy(c),
        })
        x += 220
        if x > 700:
            x = 50
            y += 130

    if not containers:
        raise ValueError('No containers found in pod spec.')

    return {
        'ok': True,
        'pod_name': pod_name,
        'containers': containers,
        'named_volumes': named_volumes,
        'restart_policy': restart_policy,
        'host_network': host_network,
        'host_pid': host_pid,
        'host_ipc': host_ipc,
        'dns': '\n'.join(dns_lines),
        'host_aliases': '\n'.join(host_aliases_lines),
        'warnings': warnings,
    }
