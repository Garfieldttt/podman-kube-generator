"""
Systemd Quadlet .kube unit file generator.

A .kube Quadlet file tells systemd to manage a pod defined by a Kubernetes YAML
file via `podman play kube`. Requires Podman >= 4.4.

Rootless path: ~/.config/containers/systemd/<pod>.kube
Rootful path:  /etc/containers/systemd/<pod>.kube
"""
import re

_RESTART_MAP = {
    'Always':    'always',
    'OnFailure': 'on-failure',
    'Never':     'no',
}


def generate_quadlet(form_data, yaml_filename=None):
    pod_name = re.sub(r'[^a-z0-9-]', '', (form_data.get('pod_name') or 'pod').strip().lower().replace(' ', '-')).strip('-') or 'pod'
    mode = form_data.get('mode', 'rootless')
    rootless = mode != 'rootful'

    if yaml_filename is None:
        yaml_filename = f'{pod_name}.yaml'

    # Absolute YAML path — must match the path shown in the deployment instructions
    if rootless:
        yaml_path = f'%h/.config/containers/{yaml_filename}'
    else:
        yaml_path = f'/etc/containers/{yaml_filename}'

    install_dir = '~/.config/containers/systemd' if rootless else '/etc/containers/systemd'
    systemctl = 'systemctl --user' if rootless else 'sudo systemctl'
    wanted_by = 'default.target' if rootless else 'multi-user.target'

    restart_policy = form_data.get('restart_policy', 'Always')
    network = (form_data.get('network') or '').strip()
    auto_update = (form_data.get('quadlet_auto_update') or '').strip()
    log_driver = (form_data.get('quadlet_log_driver') or '').strip()
    exit_code_propagation = (form_data.get('quadlet_exit_code_propagation') or '').strip()
    kube_down_force = form_data.get('quadlet_kube_down_force', False)
    timeout_start = form_data.get('quadlet_timeout_start')

    unit_lines = [
        '[Unit]',
        f'Description={pod_name} pod',
        'After=network-online.target',
        'Wants=network-online.target',
    ]

    kube_lines = [
        '[Kube]',
        f'Yaml={yaml_path}',
    ]
    if network:
        kube_lines.append(f'Network={network}')
    if auto_update:
        kube_lines.append(f'AutoUpdate={auto_update}')
    if log_driver:
        kube_lines.append(f'LogDriver={log_driver}')
    if exit_code_propagation:
        kube_lines.append(f'ExitCodePropagation={exit_code_propagation}')
    if kube_down_force:
        kube_lines.append('KubeDownForce=yes')

    service_lines = ['[Service]']
    systemd_restart = _RESTART_MAP.get(restart_policy, 'always')
    service_lines.append(f'Restart={systemd_restart}')
    if timeout_start:
        service_lines.append(f'TimeoutStartSec={timeout_start}')

    install_lines = [
        '[Install]',
        f'WantedBy={wanted_by}',
    ]

    sections = [unit_lines, kube_lines, service_lines, install_lines]
    return '\n\n'.join('\n'.join(s) for s in sections)
