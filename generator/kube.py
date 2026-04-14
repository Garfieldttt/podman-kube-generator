"""
Kubernetes YAML Generator für podman play kube.
Reine Logik – kein Django.
"""
import re
import shlex
import yaml


def _parse_lines(raw):
    return [l.strip() for l in (raw or '').splitlines() if l.strip()]


def _parse_ports(raw):
    result = []
    for line in _parse_lines(raw):
        # Extract /udp /tcp /sctp protocol suffix
        protocol = None
        if '/' in line:
            base, proto = line.rsplit('/', 1)
            if proto.upper() in ('UDP', 'TCP', 'SCTP'):
                protocol = proto.upper()
                line = base
        if ':' in line:
            parts = line.split(':')
            # Handle IP:HOST:CONTAINER (e.g. 127.0.0.1:8888:8888)
            host_str = parts[-2] if len(parts) >= 3 else parts[0]
            container_str = parts[-1]
            try:
                host_port = int(host_str.strip())
                container_port = int(container_str.strip())
                entry = {'hostPort': host_port, 'containerPort': container_port}
                if protocol and protocol != 'TCP':
                    entry['protocol'] = protocol
                result.append(entry)
            except ValueError:
                pass
        else:
            try:
                entry = {'containerPort': int(line.strip())}
                if protocol and protocol != 'TCP':
                    entry['protocol'] = protocol
                result.append(entry)
            except ValueError:
                pass
    return result


def _parse_env(raw):
    result = []
    for line in _parse_lines(raw):
        if '=' in line:
            key, _, val = line.partition('=')
            key = key.strip()
            if key:
                result.append({'name': key, 'value': val.strip()})
    return result


def _build_env_map(env_raw):
    """KEY=VALUE → {KEY: VALUE} für Variable-Substitution."""
    env_map = {}
    for line in _parse_lines(env_raw or ''):
        if '=' in line:
            k, _, v = line.partition('=')
            env_map[k.strip()] = v.strip()
    return env_map


def _resolve_vars(s, env_map):
    """Ersetzt ${VAR} durch env_map[VAR], falls vorhanden."""
    if '${' not in s:
        return s
    return re.sub(r'\$\{([^}]+)\}', lambda m: env_map.get(m.group(1), m.group(0)), s)


def _parse_volumes(raw, global_counter, vol_map, env_raw=''):
    """
    Absolute Pfade (/host/path)   → hostPath (DirectoryOrCreate / FileOrCreate)
    Relative Pfade (./x, ../x)    → named volume (persistentVolumeClaim), Name = Basename
    Named volumes (kein Präfix)   → named volume (persistentVolumeClaim)
    vol_map: {src → vol_name} — geteilt über alle Container, verhindert doppelte Einträge.
    Gibt (mounts, new_vols, new_counter) zurück.
    """
    mounts, new_vols = [], []
    counter = global_counter
    env_map = _build_env_map(env_raw)
    _KNOWN_FILE_PATHS = {
        '/etc/localtime', '/etc/timezone', '/etc/hostname',
        '/etc/hosts', '/etc/resolv.conf',
    }
    for line in _parse_lines(raw):
        parts = line.split(':')
        if len(parts) < 2:
            continue
        src = _resolve_vars(parts[0], env_map)
        container_path = parts[1]

        # Relative Pfade → named volume; Name = vollständiger Pfad als slug
        is_absolute = src.startswith('/') or src.startswith('~')
        is_relative = src.startswith('./') or src.startswith('../')
        claim_src = src  # Schlüssel für vol_map
        if is_relative:
            # ./mysql/data → "mysql-data", ../data → "data" (kein Basename-Clash)
            claim_src = re.sub(r'^\.\.?/', '', src).rstrip('/').replace('/', '-').strip('-') or 'volume'

        if claim_src in vol_map:
            vol_name = vol_map[claim_src]
        else:
            vol_name = f'vol-{counter}'
            counter += 1
            vol_map[claim_src] = vol_name
            if is_absolute:
                last_seg = src.rstrip('/').rsplit('/', 1)[-1]
                _KNOWN_FILES_NO_EXT = {'Dockerfile', 'Makefile', 'Procfile', 'Vagrantfile', 'Jenkinsfile'}
                if src in _KNOWN_FILE_PATHS:
                    htype = 'FileOrCreate'
                elif last_seg in _KNOWN_FILES_NO_EXT:
                    htype = 'FileOrCreate'
                elif '.' in last_seg and not src.endswith('/'):
                    htype = 'FileOrCreate'
                else:
                    htype = 'DirectoryOrCreate'
                new_vols.append({'name': vol_name, 'hostPath': {'path': src, 'type': htype}})
            else:
                new_vols.append({'name': vol_name, 'persistentVolumeClaim': {'claimName': claim_src}})
        mount = {'name': vol_name, 'mountPath': container_path}
        opts = {o.strip().lower() for p in parts[2:] for o in p.split(',')}
        if 'ro' in opts:
            mount['readOnly'] = True
        mounts.append(mount)
    return mounts, new_vols, counter


def _parse_host_aliases(raw):
    result = []
    for line in _parse_lines(raw):
        parts = line.split()
        if len(parts) >= 2:
            result.append({'ip': parts[0], 'hostnames': parts[1:]})
    return result


_DB_IMAGES = ('postgres', 'postgresql', 'mariadb', 'mysql', 'mongo', 'mongodb', 'redis')


def _is_db_image(image):
    # Strip tag first, then registry/repo prefix
    # Handles: postgres:15, registry.io:5000/postgres:15, myrepo/postgres
    name = (image or '').strip().lower()
    name = name.rsplit(':', 1)[0] if ':' in name.split('/')[-1] else name
    base = name.split('/')[-1]
    return any(k in base for k in _DB_IMAGES)


def _build_security_context(c, skip_user=False):
    sc = {}
    user_explicit = c.get('run_as_user') is not None and c.get('run_as_user') != ''
    if not skip_user or user_explicit:
        if user_explicit:
            sc['runAsUser'] = int(c['run_as_user'])
        if c.get('run_as_group') is not None and c.get('run_as_group') != '':
            sc['runAsGroup'] = int(c['run_as_group'])
    if c.get('read_only_root'):
        sc['readOnlyRootFilesystem'] = True
    if c.get('privileged'):
        sc['privileged'] = True
    caps = {}
    add = [cap.strip() for line in _parse_lines(c.get('cap_add', '')) for cap in line.split(',') if cap.strip()]
    drop = [cap.strip() for line in _parse_lines(c.get('cap_drop', '')) for cap in line.split(',') if cap.strip()]
    if add:
        caps['add'] = add
    if drop:
        caps['drop'] = drop
    if caps:
        sc['capabilities'] = caps
    return sc or None


def _split(s):
    try:
        return shlex.split(s)
    except ValueError:
        return s.split()


_SHELL_OPS = re.compile(r'[|&;<>]|\$\(|\bif\b|\bwhile\b|\bfor\b')

def _build_probe(c):
    cmd = (c.get('liveness_probe_cmd') or '').strip()
    if not cmd:
        return None
    if _SHELL_OPS.search(cmd):
        command = ['/bin/sh', '-c', cmd]
    else:
        command = _split(cmd)
    return {
        'exec': {'command': command},
        'initialDelaySeconds': int(c['liveness_initial_delay']) if c.get('liveness_initial_delay') not in (None, '') else 30,
        'periodSeconds': int(c['liveness_period']) if c.get('liveness_period') not in (None, '') else 10,
    }


def _build_resources(c):
    limits, requests = {}, {}
    if c.get('memory_limit'):
        limits['memory'] = c['memory_limit']
    if c.get('cpu_limit'):
        limits['cpu'] = str(c['cpu_limit'])
    if c.get('memory_request'):
        requests['memory'] = c['memory_request']
    if c.get('cpu_request'):
        requests['cpu'] = str(c['cpu_request'])
    res = {}
    if limits:
        res['limits'] = limits
    if requests:
        res['requests'] = requests
    return res or None


def _build_container(c, mounts):
    """Baut Container-Spec. Mounts werden von außen übergeben (globaler Zähler)."""
    spec = {
        'name': c['name'].strip().lower().replace(' ', '-').strip('-') or 'container',
        'image': c['image'].strip(),
    }
    is_db = _is_db_image(c.get('image', ''))
    if c.get('pull_policy'):
        spec['imagePullPolicy'] = c['pull_policy']
    ports = _parse_ports(c.get('ports', ''))
    if ports:
        spec['ports'] = ports
    env = _parse_env(c.get('env', ''))
    if env:
        spec['env'] = env
    if mounts:
        spec['volumeMounts'] = mounts
    cmd = (c.get('command') or '').strip()
    if cmd:
        spec['command'] = _split(cmd)
    args = (c.get('args') or '').strip()
    if args:
        spec['args'] = _split(args)
    if c.get('working_dir'):
        spec['workingDir'] = c['working_dir'].strip()
    sc = _build_security_context(c, skip_user=is_db)
    if sc:
        spec['securityContext'] = sc
    probe = _build_probe(c)
    if probe:
        spec['livenessProbe'] = probe
    res = _build_resources(c)
    if res:
        spec['resources'] = res
    return spec


def generate(form_data):
    pod_name = re.sub(r'[^a-z0-9-]', '', (form_data.get('pod_name') or 'pod').strip().lower().replace(' ', '-')) or 'pod'
    containers_spec = []
    init_containers_spec = []
    all_volumes = []
    annotations = {}
    vol_counter = 0  # globaler Zähler — garantiert eindeutige Vol-Namen
    vol_map = {}     # src → vol_name, verhindert doppelte Volume-Einträge

    # Pod-weites userns (Fallback, falls kein Container eigenes hat)
    if form_data.get('userns'):
        annotations['io.podman.annotations.userns'] = form_data['userns']

    # Init-Container
    for ic in form_data.get('init_containers', []):
        ic_mounts, ic_vols, vol_counter = _parse_volumes(ic.get('volumes', ''), vol_counter, vol_map, ic.get('env', ''))
        all_volumes.extend(ic_vols)
        if ic.get('run_always'):
            cname = re.sub(r'[^a-z0-9-]', '', (ic.get('name') or 'init').strip().lower())
            annotations[f'io.podman.annotations.init.container.type/{cname}'] = 'always'
        if ic.get('userns'):
            cname = re.sub(r'[^a-z0-9-]', '', (ic.get('name') or 'init').strip().lower())
            annotations[f'io.podman.annotations.userns/{cname}'] = ic['userns']
        init_containers_spec.append(_build_container(ic, ic_mounts))

    # Hauptcontainer
    for c in form_data.get('containers', []):
        mounts, vols, vol_counter = _parse_volumes(c.get('volumes', ''), vol_counter, vol_map, c.get('env', ''))
        all_volumes.extend(vols)
        if c.get('userns'):
            cname = re.sub(r'[^a-z0-9-]', '', (c.get('name') or 'container').strip().lower())
            annotations[f'io.podman.annotations.userns/{cname}'] = c['userns']
        containers_spec.append(_build_container(c, mounts))

    pod_spec = {
        'restartPolicy': form_data.get('restart_policy', 'Always'),
        'containers': containers_spec,
    }
    if init_containers_spec:
        pod_spec['initContainers'] = init_containers_spec
    if form_data.get('host_network'):
        pod_spec['hostNetwork'] = True
    if form_data.get('host_pid'):
        pod_spec['hostPID'] = True
    if form_data.get('host_ipc'):
        pod_spec['hostIPC'] = True
    if form_data.get('hostname'):
        pod_spec['hostname'] = form_data['hostname'].strip()

    host_aliases = _parse_host_aliases(form_data.get('host_aliases', ''))
    if host_aliases:
        pod_spec['hostAliases'] = host_aliases

    dns_lines = _parse_lines(form_data.get('dns', ''))
    if dns_lines:
        pod_spec['dnsConfig'] = {'nameservers': dns_lines}

    if all_volumes:
        pod_spec['volumes'] = all_volumes

    pod = {
        'apiVersion': 'v1',
        'kind': 'Pod',
        'metadata': {'name': pod_name, 'labels': {'app': pod_name}},
        'spec': pod_spec,
    }
    if annotations:
        pod['metadata']['annotations'] = annotations

    return yaml.dump(pod, default_flow_style=False, allow_unicode=True, sort_keys=False)
