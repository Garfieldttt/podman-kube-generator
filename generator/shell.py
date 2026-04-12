"""
Podman shell script generator.
Generates runnable podman pod create / podman run commands from the same
form data as kube.py.

Key differences from the Kube variant:
- Ports are published exclusively on the pod (podman pod create -p),
  NOT on individual podman run --pod calls.
- Init containers: --init-ctr=once|always (Podman-native, since 4.x).
- Restart policy: --restart on the container (not at pod level for simplicity).
"""
import re

_RESTART_MAP = {
    'Always': 'always',
    'OnFailure': 'on-failure',
    'Never': 'no',
}

_PULL_MAP = {
    'Always': 'always',
    'Never': 'never',
    'IfNotPresent': 'missing',
}

_DEFAULT_NETWORKS = {'', 'bridge', 'host', 'slirp4netns', 'pasta'}

# Known system files: no mkdir/chown needed
_SYSTEM_PATHS = {
    '/etc/localtime', '/etc/timezone', '/etc/hostname',
    '/etc/hosts', '/etc/resolv.conf',
    '/var/run/docker.sock', '/var/run/podman.sock',
    '/run/docker.sock', '/run/podman.sock',
}


def _lines(raw):
    return [l.strip() for l in (raw or '').splitlines() if l.strip()]


def _quote_env(val):
    """Shell-safe quoting for env values using single quotes.
    Single quotes prevent $, `, \\, and variable expansion entirely.
    Inner single quotes are escaped as '\\''."""
    return "'" + val.replace("'", "'\\''") + "'"



def generate_shell(form_data):
    pod_name = re.sub(r'[^a-z0-9-]', '', (form_data.get('pod_name') or 'pod').strip().lower().replace(' ', '-')) or 'pod'
    restart = _RESTART_MAP.get(form_data.get('restart_policy', 'Always'), 'always')
    mode = form_data.get('mode', 'rootless')
    sudo = 'sudo ' if mode == 'rootful' else ''

    containers = form_data.get('containers', [])
    init_containers = form_data.get('init_containers', [])

    network = (form_data.get('network') or '').strip()

    out = ['#!/bin/bash', 'set -e', '']

    # ── Build pod args ─────────────────────────────────────────────
    pod_args = [f'{sudo}podman pod create \\', f'--name {pod_name} \\']

    # Collect ports from ALL containers → publish only at pod level
    for c in containers:
        for line in _lines(c.get('ports', '')):
            pod_args.append(f'-p {line} \\')

    if form_data.get('host_network'):
        pod_args.append('--network host \\')
    elif network:
        pod_args.append(f'--network {network} \\')
    if form_data.get('host_pid'):
        pod_args.append('--pid host \\')
    if form_data.get('host_ipc'):
        pod_args.append('--ipc host \\')
    if form_data.get('hostname'):
        pod_args.append(f'--hostname {form_data["hostname"].strip()} \\')
    if form_data.get('userns'):
        pod_args.append(f'--userns {form_data["userns"].strip()} \\')
    for dns in _lines(form_data.get('dns', '')):
        pod_args.append(f'--dns {dns} \\')
    for alias in _lines(form_data.get('host_aliases', '')):
        parts = alias.split()
        if len(parts) >= 2:
            for hostname in parts[1:]:
                pod_args.append(f'--add-host {hostname}:{parts[0]} \\')

    # Last argument has no backslash
    pod_args[-1] = pod_args[-1].rstrip(' \\')

    # ── Create network ────────────────────────────────────────────
    if network and network not in _DEFAULT_NETWORKS:
        out.append('# ── Create network ' + '─' * 48)
        out.append(f'{sudo}podman network create {network} 2>/dev/null || true')
        out.append('')

    # ── Create named volumes ───────────────────────────────────────
    seen_volumes = set()
    named_volumes = []
    for c in list(init_containers) + list(containers):
        for vol in _lines(c.get('volumes', '')):
            parts = vol.split(':')
            if len(parts) >= 2:
                src = parts[0]
                if not src.startswith('/') and not src.startswith('~') and src not in seen_volumes:
                    seen_volumes.add(src)
                    named_volumes.append(src)
    if named_volumes:
        out.append('# ── Create named volumes ' + '─' * 43)
        out.append('# Named volumes are created automatically — no UID/GID permission adjustment needed.')
        for v in named_volumes:
            out.append(f'{sudo}podman volume create {v}')
        out.append('')

    # ── Create host paths ──────────────────────────────────────────
    seen_host_paths = set()
    host_paths = []
    for c in list(init_containers) + list(containers):
        for vol in _lines(c.get('volumes', '')):
            parts = vol.split(':')
            if len(parts) >= 2:
                src = parts[0]
                if (src.startswith('/') or src.startswith('~')) and src not in _SYSTEM_PATHS and src not in seen_host_paths:
                    # Directories only (no files with extension in last segment)
                    last_seg = src.rstrip('/').rsplit('/', 1)[-1]
                    if '.' not in last_seg:
                        seen_host_paths.add(src)
                        host_paths.append(src)
    if host_paths:
        out.append('# ── Create host paths ' + '─' * 46)
        out.append('# Note: The container process needs write access to these paths.')
        out.append('# Rootless — set UID/GID in the container namespace:')
        out.append('#   podman unshare chown UID:GID /path')
        out.append('# Rootful:')
        out.append('#   chown UID:GID /path')
        out.append('# Find UID/GID: podman run --rm <image> id')
        for p in host_paths:
            out.append(f'mkdir -p {p}')
            out.append(f'# {sudo.strip() or "podman unshare "}chown 0:0 {p}   # adjust UID:GID!')
        out.append('')

    out.append('# ── Create pod ' + '─' * 53)
    # Indentation: first arg without indent, rest with 2 spaces
    out.append(pod_args[0])
    for a in pod_args[1:]:
        out.append('  ' + a)
    out.append('')

    # ── Init containers ────────────────────────────────────────────
    for ic in init_containers:
        name = ic.get('name', 'init').strip().lower().replace(' ', '-')
        image = ic.get('image', '').strip()
        ctr_type = 'always' if ic.get('run_always') else 'once'

        args = [f'{sudo}podman run \\']
        args += [
            f'--pod {pod_name} \\',
            f'--name {name} \\',
            f'--init-ctr={ctr_type} \\',
        ]
        for line in _lines(ic.get('env', '')):
            if '=' in line:
                k, _, v = line.partition('=')
                args.append(f'-e {k.strip()}={_quote_env(v)} \\')
        for vol in _lines(ic.get('volumes', '')):
            args.append(f'-v {vol} \\')
        cmd = (ic.get('command') or '').strip()
        ctr_args = (ic.get('args') or '').strip()
        has_extra = cmd or ctr_args
        args.append(image + (' \\' if has_extra else ''))
        if cmd:
            args.append(cmd + (' \\' if ctr_args else ''))
        if ctr_args:
            args.append(ctr_args)

        args[-1] = args[-1].rstrip(' \\')

        out.append(f'# ── Init container: {name} ' + '─' * 40)
        out.append(args[0])
        for a in args[1:]:
            out.append('  ' + a)
        out.append('')

    # ── Regular containers ─────────────────────────────────────────
    for c in containers:
        name = c.get('name', 'container').strip().lower().replace(' ', '-')
        image = c.get('image', '').strip()

        args = [f'{sudo}podman run -d \\']
        args += [
            f'--pod {pod_name} \\',
            f'--name {name} \\',
            f'--restart {restart} \\',
        ]

        pull = c.get('pull_policy', '')
        if pull and pull != 'IfNotPresent':
            args.append(f'--pull {_PULL_MAP.get(pull, "missing")} \\')

        for line in _lines(c.get('env', '')):
            if '=' in line:
                k, _, v = line.partition('=')
                args.append(f'-e {k.strip()}={_quote_env(v)} \\')

        for vol in _lines(c.get('volumes', '')):
            args.append(f'-v {vol} \\')

        if c.get('memory_limit'):
            args.append(f'--memory {c["memory_limit"]} \\')
        if c.get('cpu_limit'):
            args.append(f'--cpus {c["cpu_limit"]} \\')

        if c.get('run_as_user') is not None and c.get('run_as_user') != '':
            user = str(c['run_as_user'])
            if c.get('run_as_group') is not None and c.get('run_as_group') != '':
                user += f':{c["run_as_group"]}'
            args.append(f'--user {user} \\')

        if c.get('working_dir'):
            args.append(f'--workdir {c["working_dir"].strip()} \\')
        if c.get('read_only_root'):
            args.append('--read-only \\')
        if c.get('privileged'):
            args.append('--privileged \\')

        for cap in _lines(c.get('cap_add', '')):
            for cap_item in cap.split(','):
                cap_item = cap_item.strip()
                if cap_item:
                    args.append(f'--cap-add {cap_item} \\')
        for cap in _lines(c.get('cap_drop', '')):
            for cap_item in cap.split(','):
                cap_item = cap_item.strip()
                if cap_item:
                    args.append(f'--cap-drop {cap_item} \\')

        cmd = (c.get('command') or '').strip()
        ctr_args = (c.get('args') or '').strip()
        has_extra = cmd or ctr_args
        args.append(image + (' \\' if has_extra else ''))
        if cmd:
            args.append(cmd + (' \\' if ctr_args else ''))
        if ctr_args:
            args.append(ctr_args)

        args[-1] = args[-1].rstrip(' \\')

        out.append(f'# ── Container: {name} ' + '─' * 45)
        out.append(args[0])
        for a in args[1:]:
            out.append('  ' + a)
        out.append('')

    # ── Stop & clean up ───────────────────────────────────────────
    out.append('# ── Stop & clean up ' + '─' * 47)
    out.append(f'# {sudo}podman pod stop {pod_name}')
    out.append(f'# {sudo}podman pod rm {pod_name}')

    return '\n'.join(out)
