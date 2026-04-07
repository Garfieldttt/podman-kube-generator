"""
Systemd Quadlet .kube unit file generator.

A .kube Quadlet file tells systemd to manage a pod defined by a Kubernetes YAML
file via `podman play kube`. Requires Podman >= 4.4.

Rootless path: ~/.config/containers/systemd/<pod>.kube
Rootful path:  /etc/containers/systemd/<pod>.kube
"""
import re


def generate_quadlet(form_data, yaml_filename=None):
    pod_name = re.sub(r'[^a-z0-9-]', '', (form_data.get('pod_name') or 'pod').strip().lower().replace(' ', '-')) or 'pod'
    mode = form_data.get('mode', 'rootless')
    rootless = mode != 'rootful'

    if yaml_filename is None:
        yaml_filename = f'{pod_name}.yaml'

    install_dir = '~/.config/containers/systemd' if rootless else '/etc/containers/systemd'
    systemctl = 'systemctl --user' if rootless else 'sudo systemctl'
    wanted_by = 'default.target' if rootless else 'multi-user.target'

    lines = [
        '[Unit]',
        f'Description={pod_name} pod',
        'After=network-online.target',
        'Wants=network-online.target',
        '',
        '[Kube]',
        f'Yaml={yaml_filename}',
        '',
        '[Install]',
        f'WantedBy={wanted_by}',
    ]

    return '\n'.join(lines)
