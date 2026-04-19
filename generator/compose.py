"""
Docker Compose YAML generator from form_data.
"""
import yaml

_RESTART_MAP = {
    'Always':    'always',
    'OnFailure': 'on-failure',
    'Never':     'no',
}

_DB_IMAGES = ('postgres', 'postgresql', 'mariadb', 'mysql', 'mongo', 'mongodb', 'redis', 'valkey')


def _img_base(image):
    return (image or '').split('/')[-1].split(':')[0].lower()


def _is_db(image):
    b = _img_base(image)
    return any(k in b for k in _DB_IMAGES)


def _parse_lines(raw):
    return [l.strip() for l in (raw or '').splitlines() if l.strip()]


def _split_caps(raw):
    caps = []
    for line in _parse_lines(raw):
        for cap in line.split(','):
            cap = cap.strip()
            if cap:
                caps.append(cap)
    return caps


def _build_service(c, restart, init_names, db_names, host_network, network, is_init=False):
    svc = {'image': (c.get('image') or '').strip()}

    svc['restart'] = 'no' if is_init else restart

    ports = _parse_lines(c.get('ports', ''))
    if ports:
        svc['ports'] = ports

    env = _parse_lines(c.get('env', ''))
    if env:
        svc['environment'] = env

    if c.get('working_dir'):
        svc['working_dir'] = c['working_dir'].strip()

    raw_ep = (c.get('command') or '').strip()
    raw_cmd = (c.get('args') or '').strip()
    if raw_ep:
        svc['entrypoint'] = raw_ep
    if raw_cmd:
        svc['command'] = raw_cmd

    uid = c.get('run_as_user')
    gid = c.get('run_as_group')
    if uid not in (None, ''):
        user = str(uid)
        if gid not in (None, ''):
            user += f':{gid}'
        svc['user'] = user

    if c.get('privileged'):
        svc['privileged'] = True
    if c.get('read_only_root'):
        svc['read_only'] = True

    cap_add = _split_caps(c.get('cap_add', ''))
    cap_drop = _split_caps(c.get('cap_drop', ''))
    if cap_add:
        svc['cap_add'] = cap_add
    if cap_drop:
        svc['cap_drop'] = cap_drop

    mem = (c.get('memory_limit') or '').strip()
    cpu = c.get('cpu_limit')
    if mem or cpu:
        limits = {}
        if mem:
            limits['memory'] = mem
        if cpu:
            limits['cpus'] = str(cpu)
        svc['deploy'] = {'resources': {'limits': limits}}

    if not is_init:
        depends = {}
        for iname in init_names:
            depends[iname] = {'condition': 'service_completed_successfully'}
        if not _is_db(c.get('image', '')):
            for dname in db_names:
                if dname not in depends:
                    depends[dname] = {'condition': 'service_started'}
        if depends:
            svc['depends_on'] = depends

    if not is_init:
        if host_network:
            svc['network_mode'] = 'host'
        elif network:
            svc['networks'] = [network]

    return svc


def generate_compose(form_data):
    restart = _RESTART_MAP.get(form_data.get('restart_policy', 'Always'), 'always')
    host_network = form_data.get('host_network', False)
    network = (form_data.get('network') or '').strip()

    containers = form_data.get('containers', [])
    init_containers = form_data.get('init_containers', [])

    def svc_name(c):
        return (c.get('name') or 'container').strip().lower().replace(' ', '-')

    init_names = [svc_name(ic) for ic in init_containers]
    db_names   = [svc_name(c)  for c in containers if _is_db(c.get('image', ''))]

    services = {}
    named_volumes = {}

    def collect_volumes(c, svc):
        vols = _parse_lines(c.get('volumes', ''))
        if vols:
            svc['volumes'] = vols
            for v in vols:
                src = v.split(':')[0]
                if not (src.startswith('/') or src.startswith('~') or
                        src.startswith('./') or src.startswith('../')):
                    named_volumes[src] = None

    for ic in init_containers:
        name = svc_name(ic)
        svc = _build_service(ic, restart, [], [], host_network, network, is_init=True)
        collect_volumes(ic, svc)
        services[name] = svc

    for c in containers:
        name = svc_name(c)
        svc = _build_service(c, restart, init_names, db_names, host_network, network)
        collect_volumes(c, svc)
        services[name] = svc

    compose = {'services': services}
    if named_volumes:
        compose['volumes'] = named_volumes
    if network and not host_network:
        compose['networks'] = {network: None}

    return yaml.dump(compose, default_flow_style=False, allow_unicode=True, sort_keys=False)
