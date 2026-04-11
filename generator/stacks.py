"""
Vordefinierte Multi-Container-Stacks mit korrekten localhost-Verbindungen.
Alle Env-Vars und Ports sind gegen die offiziellen Docker Hub Images geprüft.
"""

STACKS = {

    # ── CMS / Blog ────────────────────────────────────────────────
    'wordpress-mariadb': {
        'label': 'WordPress',
        'description': 'CMS-Plattform für Blogs und Websites mit MariaDB-Datenbank',
        'description_en': 'CMS platform for blogs and websites with MariaDB database',
        'icon': 'bi-globe',
        'category': 'CMS',
        'pod_name': 'wordpress',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'wordpress',
                'image': 'docker.io/wordpress:latest',
                'ports': '8080:80',
                'env': (
                    'WORDPRESS_DB_HOST=127.0.0.1:3306\n'
                    'WORDPRESS_DB_USER=wordpress\n'
                    'WORDPRESS_DB_PASSWORD=changeme\n'
                    'WORDPRESS_DB_NAME=wordpress'
                ),
                'volumes': 'wordpress-html:/var/www/html:Z',
            },
            {
                'name': 'mariadb',
                'image': 'docker.io/mariadb:11',
                'env': (
                    'MARIADB_ROOT_PASSWORD=changeme_root\n'
                    'MARIADB_USER=wordpress\n'
                    'MARIADB_PASSWORD=changeme\n'
                    'MARIADB_DATABASE=wordpress'
                ),
                'volumes': 'wordpress-db:/var/lib/mysql:Z',
                'run_as_user': 999,
                'run_as_group': 999,
            },
        ],
        'db_variants': {
            'replace': 'mariadb',
            'options': [
                {
                    'key': 'mariadb',
                    'label': 'MariaDB 11',
                    'icon': 'bi-database',
                    'container': {
                        'name': 'mariadb',
                        'image': 'docker.io/mariadb:11',
                        'env': (
                            'MARIADB_ROOT_PASSWORD=changeme_root\n'
                            'MARIADB_USER=wordpress\n'
                            'MARIADB_PASSWORD=changeme\n'
                            'MARIADB_DATABASE=wordpress'
                        ),
                        'volumes': 'wordpress-db:/var/lib/mysql:Z',
                        'run_as_user': 999,
                        'run_as_group': 999,
                    },
                },
                {
                    'key': 'mysql',
                    'label': 'MySQL 8',
                    'icon': 'bi-database-fill',
                    'container': {
                        'name': 'mysql',
                        'image': 'docker.io/mysql:8',
                        'env': (
                            'MYSQL_ROOT_PASSWORD=changeme_root\n'
                            'MYSQL_USER=wordpress\n'
                            'MYSQL_PASSWORD=changeme\n'
                            'MYSQL_DATABASE=wordpress'
                        ),
                        'volumes': 'wordpress-db:/var/lib/mysql:Z',
                        'run_as_user': 999,
                        'run_as_group': 999,
                    },
                    'app_env': (
                        'WORDPRESS_DB_HOST=127.0.0.1:3306\n'
                        'WORDPRESS_DB_USER=wordpress\n'
                        'WORDPRESS_DB_PASSWORD=changeme\n'
                        'WORDPRESS_DB_NAME=wordpress'
                    ),
                },
            ],
        },
    },

    # ── Cloud Storage ─────────────────────────────────────────────
    'nextcloud-postgres': {
        'label': 'Nextcloud',
        'description': 'Private Cloud-Speicherlösung mit Kalender, Kontakten und mehr',
        'description_en': 'Private cloud storage solution with calendar, contacts and more',
        'icon': 'bi-cloud',
        'category': 'Cloud',
        'pod_name': 'nextcloud',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'nextcloud',
                'image': 'docker.io/nextcloud:29',
                'ports': '8080:80',
                'env': (
                    'POSTGRES_HOST=127.0.0.1\n'
                    'POSTGRES_DB=nextcloud\n'
                    'POSTGRES_USER=nextcloud\n'
                    'POSTGRES_PASSWORD=changeme\n'
                    'NEXTCLOUD_ADMIN_USER=admin\n'
                    'NEXTCLOUD_ADMIN_PASSWORD=changeme\n'
                    'NEXTCLOUD_TRUSTED_DOMAINS=localhost'
                ),
                'volumes': 'nextcloud-html:/var/www/html:Z',
            },
            {
                'name': 'postgres',
                'image': 'docker.io/postgres:16',
                'env': (
                    'POSTGRES_USER=nextcloud\n'
                    'POSTGRES_PASSWORD=changeme\n'
                    'POSTGRES_DB=nextcloud'
                ),
                'volumes': 'nextcloud-db:/var/lib/postgresql/data:Z',
                'run_as_user': 999,
                'run_as_group': 999,
            },
        ],
        'db_variants': {
            'replace': 'postgres',
            'options': [
                {
                    'key': 'postgres',
                    'label': 'PostgreSQL 16',
                    'icon': 'bi-elephant',
                    'container': {
                        'name': 'postgres',
                        'image': 'docker.io/postgres:16',
                        'env': (
                            'POSTGRES_USER=nextcloud\n'
                            'POSTGRES_PASSWORD=changeme\n'
                            'POSTGRES_DB=nextcloud'
                        ),
                        'volumes': 'nextcloud-db:/var/lib/postgresql/data:Z',
                        'run_as_user': 999,
                        'run_as_group': 999,
                    },
                },
                {
                    'key': 'mariadb',
                    'label': 'MariaDB 11',
                    'icon': 'bi-database',
                    'container': {
                        'name': 'mariadb',
                        'image': 'docker.io/mariadb:11',
                        'env': (
                            'MARIADB_USER=nextcloud\n'
                            'MARIADB_PASSWORD=changeme\n'
                            'MARIADB_ROOT_PASSWORD=changeme_root\n'
                            'MARIADB_DATABASE=nextcloud'
                        ),
                        'volumes': 'nextcloud-db:/var/lib/mysql:Z',
                        'run_as_user': 999,
                        'run_as_group': 999,
                    },
                    'app_env': (
                        'MYSQL_HOST=127.0.0.1\n'
                        'MYSQL_DATABASE=nextcloud\n'
                        'MYSQL_USER=nextcloud\n'
                        'MYSQL_PASSWORD=changeme\n'
                        'NEXTCLOUD_ADMIN_USER=admin\n'
                        'NEXTCLOUD_ADMIN_PASSWORD=changeme\n'
                        'NEXTCLOUD_TRUSTED_DOMAINS=localhost'
                    ),
                },
            ],
        },
    },

    # ── Git ───────────────────────────────────────────────────────
    'gitea-postgres': {
        'label': 'Gitea',
        'description': 'Leichtgewichtiger self-hosted Git-Server mit Web-UI',
        'description_en': 'Lightweight self-hosted Git server with web UI',
        'icon': 'bi-git',
        'category': 'Git',
        'pod_name': 'gitea',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'gitea',
                'image': 'docker.io/gitea/gitea:latest',
                'ports': '3000:3000\n2222:22',
                'env': (
                    'GITEA__database__DB_TYPE=postgres\n'
                    'GITEA__database__HOST=127.0.0.1:5432\n'
                    'GITEA__database__NAME=gitea\n'
                    'GITEA__database__USER=gitea\n'
                    'GITEA__database__PASSWD=changeme\n'
                    'GITEA__server__ROOT_URL=http://localhost:3000\n'
                    'GITEA__server__SSH_PORT=2222'
                ),
                'volumes': 'gitea-data:/data:Z',
            },
            {
                'name': 'postgres',
                'image': 'docker.io/postgres:16',
                'env': (
                    'POSTGRES_USER=gitea\n'
                    'POSTGRES_PASSWORD=changeme\n'
                    'POSTGRES_DB=gitea'
                ),
                'volumes': 'gitea-db:/var/lib/postgresql/data:Z',
                'run_as_user': 999,
                'run_as_group': 999,
            },
        ],
        'db_variants': {
            'replace': 'postgres',
            'options': [
                {
                    'key': 'postgres',
                    'label': 'PostgreSQL 16',
                    'icon': 'bi-elephant',
                    'container': {
                        'name': 'postgres',
                        'image': 'docker.io/postgres:16',
                        'env': (
                            'POSTGRES_USER=gitea\n'
                            'POSTGRES_PASSWORD=changeme\n'
                            'POSTGRES_DB=gitea'
                        ),
                        'volumes': 'gitea-db:/var/lib/postgresql/data:Z',
                        'run_as_user': 999,
                        'run_as_group': 999,
                    },
                },
                {
                    'key': 'mysql',
                    'label': 'MySQL 8',
                    'icon': 'bi-database-fill',
                    'container': {
                        'name': 'mysql',
                        'image': 'docker.io/mysql:8',
                        'env': (
                            'MYSQL_USER=gitea\n'
                            'MYSQL_PASSWORD=changeme\n'
                            'MYSQL_DATABASE=gitea\n'
                            'MYSQL_ROOT_PASSWORD=changeme_root'
                        ),
                        'volumes': 'gitea-db:/var/lib/mysql:Z',
                        'run_as_user': 999,
                        'run_as_group': 999,
                    },
                    'app_env': (
                        'GITEA__database__DB_TYPE=mysql\n'
                        'GITEA__database__HOST=127.0.0.1:3306\n'
                        'GITEA__database__NAME=gitea\n'
                        'GITEA__database__USER=gitea\n'
                        'GITEA__database__PASSWD=changeme\n'
                        'GITEA__server__ROOT_URL=http://localhost:3000\n'
                        'GITEA__server__SSH_PORT=2222'
                    ),
                },
            ],
        },
        'sqlite_option': True,
        'sqlite_env': (
            'GITEA__database__DB_TYPE=sqlite3\n'
            'GITEA__database__PATH=/data/gitea/gitea.db\n'
            'GITEA__server__ROOT_URL=http://localhost:3000\n'
            'GITEA__server__SSH_PORT=2222'
        ),
    },

    # ── Monitoring ────────────────────────────────────────────────
    'grafana-influxdb': {
        'label': 'Grafana + InfluxDB',
        'description': 'Zeitreihendatenbank mit Grafana-Dashboard für Metriken',
        'description_en': 'Time series database with Grafana dashboard for metrics',
        'icon': 'bi-bar-chart-line',
        'category': 'Monitoring',
        'pod_name': 'monitoring',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'grafana',
                'image': 'docker.io/grafana/grafana:latest',
                'ports': '3000:3000',
                'env': (
                    'GF_SECURITY_ADMIN_USER=admin\n'
                    'GF_SECURITY_ADMIN_PASSWORD=changeme\n'
                    'GF_USERS_ALLOW_SIGN_UP=false\n'
                    'GF_SERVER_ROOT_URL=http://localhost:3000'
                ),
                'volumes': 'monitoring-grafana:/var/lib/grafana:Z',
                'run_as_user': 0,
                'run_as_group': 0,
            },
            {
                'name': 'influxdb',
                'image': 'docker.io/influxdb:2',
                'ports': '8086:8086',
                'env': (
                    'DOCKER_INFLUXDB_INIT_MODE=setup\n'
                    'DOCKER_INFLUXDB_INIT_USERNAME=admin\n'
                    'DOCKER_INFLUXDB_INIT_PASSWORD=changeme123\n'
                    'DOCKER_INFLUXDB_INIT_ORG=myorg\n'
                    'DOCKER_INFLUXDB_INIT_BUCKET=metrics\n'
                    'DOCKER_INFLUXDB_INIT_ADMIN_TOKEN=mytoken'
                ),
                'volumes': 'monitoring-influxdb:/var/lib/influxdb2:Z',
            },
        ],
    },

    'prometheus-grafana': {
        'label': 'Prometheus + Grafana',
        'description': 'Monitoring-Stack mit Prometheus-Scraping und Grafana-Visualisierung',
        'description_en': 'Monitoring stack with Prometheus scraping and Grafana visualization',
        'icon': 'bi-graph-up',
        'category': 'Monitoring',
        'pod_name': 'monitoring',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'prometheus',
                'image': 'docker.io/prom/prometheus:latest',
                'ports': '9090:9090',
                'volumes': 'monitoring-prometheus:/etc/prometheus:Z\nmonitoring-prometheus-data:/prometheus:Z',
                'args': '--config.file=/etc/prometheus/prometheus.yml --storage.tsdb.path=/prometheus --web.console.libraries=/usr/share/prometheus/console_libraries --web.console.templates=/usr/share/prometheus/consoles',
                'run_as_user': 0,
                'run_as_group': 0,
            },
            {
                'name': 'grafana',
                'image': 'docker.io/grafana/grafana:latest',
                'ports': '3000:3000',
                'env': (
                    'GF_SECURITY_ADMIN_USER=admin\n'
                    'GF_SECURITY_ADMIN_PASSWORD=changeme\n'
                    'GF_USERS_ALLOW_SIGN_UP=false'
                ),
                'volumes': 'monitoring-grafana:/var/lib/grafana:Z',
                'run_as_user': 0,
                'run_as_group': 0,
            },
        ],
    },

    # ── Security ──────────────────────────────────────────────────
    'vaultwarden': {
        'label': 'Vaultwarden',
        'description': 'Bitwarden-kompatibler Passwort-Manager, ressourcenschonend',
        'description_en': 'Bitwarden-compatible password manager with low resource usage',
        'icon': 'bi-shield-lock',
        'category': 'Security',
        'pod_name': 'vaultwarden',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'vaultwarden',
                'image': 'docker.io/vaultwarden/server:latest',
                'ports': '8080:80',
                'env': (
                    'ADMIN_TOKEN=changeme_token\n'
                    'SIGNUPS_ALLOWED=false\n'
                    'DOMAIN=https://vaultwarden.example.com\n'
                    'WEBSOCKET_ENABLED=true'
                ),
                'volumes': 'vaultwarden-data:/data:Z',
            },
        ],
    },

    'keycloak-postgres': {
        'label': 'Keycloak',
        'description': 'Identity- und Access-Management mit SSO, OAuth2 und SAML',
        'description_en': 'Identity and access management with SSO, OAuth2 and SAML',
        'icon': 'bi-person-badge',
        'category': 'Security',
        'pod_name': 'keycloak',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'keycloak',
                'image': 'quay.io/keycloak/keycloak:latest',
                'ports': '8080:8080',
                'env': (
                    'KC_DB=postgres\n'
                    'KC_DB_URL=jdbc:postgresql://127.0.0.1:5432/keycloak\n'
                    'KC_DB_USERNAME=keycloak\n'
                    'KC_DB_PASSWORD=changeme\n'
                    'KEYCLOAK_ADMIN=admin\n'
                    'KEYCLOAK_ADMIN_PASSWORD=changeme\n'
                    'KC_HOSTNAME=localhost'
                ),
                'args': 'start-dev',
            },
            {
                'name': 'postgres',
                'image': 'docker.io/postgres:16',
                'env': (
                    'POSTGRES_USER=keycloak\n'
                    'POSTGRES_PASSWORD=changeme\n'
                    'POSTGRES_DB=keycloak'
                ),
                'volumes': 'keycloak-db:/var/lib/postgresql/data:Z',
                'run_as_user': 999,
                'run_as_group': 999,
            },
        ],
        'db_variants': {
            'replace': 'postgres',
            'options': [
                {
                    'key': 'postgres',
                    'label': 'PostgreSQL 16',
                    'icon': 'bi-elephant',
                    'container': {
                        'name': 'postgres',
                        'image': 'docker.io/postgres:16',
                        'env': (
                            'POSTGRES_USER=keycloak\n'
                            'POSTGRES_PASSWORD=changeme\n'
                            'POSTGRES_DB=keycloak'
                        ),
                        'volumes': 'keycloak-db:/var/lib/postgresql/data:Z',
                        'run_as_user': 999,
                        'run_as_group': 999,
                    },
                },
                {
                    'key': 'mariadb',
                    'label': 'MariaDB 11',
                    'icon': 'bi-database',
                    'container': {
                        'name': 'mariadb',
                        'image': 'docker.io/mariadb:11',
                        'env': (
                            'MARIADB_USER=keycloak\n'
                            'MARIADB_PASSWORD=changeme\n'
                            'MARIADB_ROOT_PASSWORD=changeme_root\n'
                            'MARIADB_DATABASE=keycloak'
                        ),
                        'volumes': 'keycloak-db:/var/lib/mysql:Z',
                        'run_as_user': 999,
                        'run_as_group': 999,
                    },
                    'app_env': (
                        'KC_DB=mariadb\n'
                        'KC_DB_URL=jdbc:mariadb://127.0.0.1:3306/keycloak\n'
                        'KC_DB_USERNAME=keycloak\n'
                        'KC_DB_PASSWORD=changeme\n'
                        'KEYCLOAK_ADMIN=admin\n'
                        'KEYCLOAK_ADMIN_PASSWORD=changeme\n'
                        'KC_HOSTNAME=localhost'
                    ),
                },
            ],
        },
    },

    # ── Proxy ─────────────────────────────────────────────────────
    'nginx-proxy-manager': {
        'label': 'Nginx Proxy Manager',
        'description': 'Reverse Proxy mit Web-UI, Let\'s Encrypt SSL und Weiterleitungen',
        'description_en': 'Reverse proxy with web UI, Let\'s Encrypt SSL and redirections',
        'icon': 'bi-shuffle',
        'category': 'Proxy',
        'pod_name': 'nginx-proxy-manager',
        'restart_policy': 'Always',
        'mode': 'rootful',
        'containers': [
            {
                'name': 'nginx-proxy-manager',
                'image': 'docker.io/jc21/nginx-proxy-manager:latest',
                'ports': '80:80\n443:443\n81:81',
                'volumes': (
                    'nginx-proxy-manager-data:/data:Z\n'
                    'nginx-proxy-manager-letsencrypt:/etc/letsencrypt:Z'
                ),
            },
        ],
    },

    'zoraxy': {
        'label': 'Zoraxy',
        'description': 'Einfacher Reverse Proxy und statisches Web-Hosting mit HTTPS',
        'description_en': 'Simple reverse proxy and static web hosting with HTTPS',
        'icon': 'bi-arrow-left-right',
        'category': 'Proxy',
        'pod_name': 'zoraxy',
        'restart_policy': 'Always',
        'mode': 'rootful',
        'containers': [
            {
                'name': 'zoraxy',
                'image': 'ghcr.io/tobychui/zoraxy:latest',
                'ports': '80:80\n443:443\n8000:8000',
                'volumes': 'zoraxy-config:/opt/zoraxy/config:Z',
            },
        ],
    },

    # ── Uptime / Status ───────────────────────────────────────────
    'uptime-kuma': {
        'label': 'Uptime Kuma',
        'description': 'Self-hosted Monitoring-Tool für Websites, Dienste und Ports',
        'description_en': 'Self-hosted monitoring tool for websites, services and ports',
        'icon': 'bi-activity',
        'category': 'Monitoring',
        'pod_name': 'uptime-kuma',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'uptime-kuma',
                'image': 'docker.io/louislam/uptime-kuma:latest',
                'ports': '3001:3001',
                'volumes': 'uptime-kuma-data:/app/data:Z',
            },
        ],
    },

    'zabbix-server-postgres': {
        'label': 'Zabbix Server + Web + PostgreSQL',
        'description': 'Enterprise-Monitoring-Plattform für Infrastruktur und Netzwerk',
        'description_en': 'Enterprise monitoring platform for infrastructure and network',
        'icon': 'bi-graph-up-arrow',
        'category': 'Monitoring',
        'pod_name': 'zabbix',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'zabbix-server',
                'image': 'docker.io/zabbix/zabbix-server-pgsql:latest',
                'ports': '10051:10051',
                'env': (
                    'DB_SERVER_HOST=127.0.0.1\n'
                    'POSTGRES_USER=zabbix\n'
                    'POSTGRES_PASSWORD=changeme\n'
                    'POSTGRES_DB=zabbix'
                ),
                'run_as_user': 1997,
                'run_as_group': 1997,
            },
            {
                'name': 'zabbix-web',
                'image': 'docker.io/zabbix/zabbix-web-nginx-pgsql:latest',
                'ports': '8080:8080',
                'env': (
                    'ZBX_SERVER_HOST=127.0.0.1\n'
                    'DB_SERVER_HOST=127.0.0.1\n'
                    'POSTGRES_USER=zabbix\n'
                    'POSTGRES_PASSWORD=changeme\n'
                    'POSTGRES_DB=zabbix\n'
                    'PHP_TZ=Europe/Vienna'
                ),
                'run_as_user': 1997,
                'run_as_group': 1997,
            },
            {
                'name': 'postgres',
                'image': 'docker.io/postgres:16',
                'env': (
                    'POSTGRES_USER=zabbix\n'
                    'POSTGRES_PASSWORD=changeme\n'
                    'POSTGRES_DB=zabbix'
                ),
                'volumes': 'zabbix-db:/var/lib/postgresql/data:Z',
                'run_as_user': 999,
                'run_as_group': 999,
            },
        ],
    },

    'zabbix-proxy-sqlite': {
        'label': 'Zabbix Proxy (SQLite)',
        'description': 'Zabbix Proxy mit SQLite für verteiltes Monitoring',
        'description_en': 'Zabbix proxy with SQLite for distributed monitoring',
        'icon': 'bi-hdd-network',
        'category': 'Monitoring',
        'pod_name': 'zabbix-proxy',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'zabbix-proxy',
                'image': 'docker.io/zabbix/zabbix-proxy-sqlite3:latest',
                'ports': '10051:10051',
                'env': (
                    'ZBX_SERVER_HOST=changeme\n'
                    'ZBX_HOSTNAME=proxy-hostname\n'
                    'ZBX_PROXYMODE=0'
                ),
                'volumes': 'zabbix-proxy-db:/var/lib/zabbix/db_data:Z',
                'run_as_user': 0,
                'run_as_group': 0,
            },
        ],
    },

    # ── Media ─────────────────────────────────────────────────────
    'audiobookshelf': {
        'label': 'Audiobookshelf',
        'description': 'Self-hosted Hörbuch- und Podcast-Server mit App-Unterstützung',
        'description_en': 'Self-hosted audiobook and podcast server with app support',
        'icon': 'bi-headphones',
        'category': 'Media',
        'pod_name': 'audiobookshelf',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'audiobookshelf',
                'image': 'ghcr.io/advplyr/audiobookshelf:latest',
                'ports': '13378:80',
                'env': 'TZ=Europe/Vienna',
                'volumes': (
                    'audiobookshelf-config:/config:Z\n'
                    'audiobookshelf-metadata:/metadata:Z\n'
                    '/audiobooks:/audiobooks:ro\n'
                    '/podcasts:/podcasts:ro'
                ),
            },
        ],
    },

    'jellyfin': {
        'label': 'Jellyfin',
        'description': 'Freier Media-Server für Filme, Serien, Musik und Fotos',
        'description_en': 'Free media server for movies, series, music and photos',
        'icon': 'bi-play-circle',
        'category': 'Media',
        'pod_name': 'jellyfin',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'jellyfin',
                'image': 'docker.io/jellyfin/jellyfin:latest',
                'ports': '8096:8096',
                'env': 'JELLYFIN_PublishedServerUrl=http://localhost:8096',
                'volumes': (
                    'jellyfin-config:/config:Z\n'
                    'jellyfin-cache:/cache:Z\n'
                    '/media:/media:ro'
                ),
            },
        ],
    },

    'immich-redis-postgres': {
        'label': 'Immich + Redis + PostgreSQL',
        'description': 'Hochperformante Foto- und Video-Backup-Lösung mit KI-Erkennung',
        'description_en': 'High-performance photo and video backup solution with AI recognition',
        'icon': 'bi-images',
        'category': 'Media',
        'pod_name': 'immich',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'immich-server',
                'image': 'ghcr.io/immich-app/immich-server:release',
                'ports': '2283:2283',
                'env': (
                    'DB_HOSTNAME=127.0.0.1\n'
                    'DB_PORT=5432\n'
                    'DB_DATABASE_NAME=immich\n'
                    'DB_USERNAME=immich\n'
                    'DB_PASSWORD=changeme\n'
                    'REDIS_HOSTNAME=127.0.0.1\n'
                    'UPLOAD_LOCATION=/usr/src/app/upload'
                ),
                'volumes': 'immich-upload:/usr/src/app/upload:Z',
            },
            {
                'name': 'redis',
                'image': 'docker.io/redis:7-alpine',
                'command': 'redis-server --appendonly yes',
                'volumes': 'immich-redis:/data:Z',
            },
            {
                'name': 'postgres',
                'image': 'docker.io/tensorchord/pgvecto-rs:pg16-v0.2.0',
                'env': (
                    'POSTGRES_USER=immich\n'
                    'POSTGRES_PASSWORD=changeme\n'
                    'POSTGRES_DB=immich'
                ),
                'volumes': 'immich-db:/var/lib/postgresql/data:Z',
                'run_as_user': 999,
                'run_as_group': 999,
            },
        ],
    },

    'photoprism': {
        'label': 'PhotoPrism',
        'description': 'KI-gestützte Fotoverwaltung mit automatischer Kategorisierung',
        'description_en': 'AI-powered photo management with automatic categorization',
        'icon': 'bi-camera',
        'category': 'Media',
        'pod_name': 'photoprism',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'photoprism',
                'image': 'docker.io/photoprism/photoprism:latest',
                'ports': '2342:2342',
                'env': (
                    'PHOTOPRISM_ADMIN_USER=admin\n'
                    'PHOTOPRISM_ADMIN_PASSWORD=changeme\n'
                    'PHOTOPRISM_SITE_URL=http://localhost:2342/\n'
                    'PHOTOPRISM_DATABASE_DRIVER=mysql\n'
                    'PHOTOPRISM_DATABASE_SERVER=127.0.0.1:3306\n'
                    'PHOTOPRISM_DATABASE_NAME=photoprism\n'
                    'PHOTOPRISM_DATABASE_USER=photoprism\n'
                    'PHOTOPRISM_DATABASE_PASSWORD=changeme\n'
                    'TZ=Europe/Vienna'
                ),
                'volumes': (
                    'photoprism-originals:/photoprism/originals:Z\n'
                    'photoprism-storage:/photoprism/storage:Z'
                ),
            },
            {
                'name': 'mariadb',
                'image': 'docker.io/mariadb:11',
                'env': (
                    'MARIADB_ROOT_PASSWORD=changeme_root\n'
                    'MARIADB_USER=photoprism\n'
                    'MARIADB_PASSWORD=changeme\n'
                    'MARIADB_DATABASE=photoprism'
                ),
                'volumes': 'photoprism-db:/var/lib/mysql:Z',
                'run_as_user': 999,
                'run_as_group': 999,
            },
        ],
    },

    'sonarr': {
        'label': 'Sonarr',
        'description': 'Automatischer Download-Manager für TV-Serien',
        'description_en': 'Automatic download manager for TV series',
        'icon': 'bi-tv',
        'category': 'Media',
        'pod_name': 'sonarr',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'sonarr',
                'image': 'lscr.io/linuxserver/sonarr:latest',
                'ports': '8989:8989',
                'env': (
                    'PUID=1000\n'
                    'PGID=1000\n'
                    'TZ=Europe/Vienna'
                ),
                'volumes': (
                    'sonarr-config:/config:Z\n'
                    '/tv:/tv\n'
                    '/downloads:/downloads'
                ),
            },
        ],
    },

    'radarr': {
        'label': 'Radarr',
        'description': 'Automatischer Download-Manager für Filme',
        'description_en': 'Automatic download manager for movies',
        'icon': 'bi-film',
        'category': 'Media',
        'pod_name': 'radarr',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'radarr',
                'image': 'lscr.io/linuxserver/radarr:latest',
                'ports': '7878:7878',
                'env': (
                    'PUID=1000\n'
                    'PGID=1000\n'
                    'TZ=Europe/Vienna'
                ),
                'volumes': (
                    'radarr-config:/config:Z\n'
                    '/movies:/movies\n'
                    '/downloads:/downloads'
                ),
            },
        ],
    },

    'prowlarr': {
        'label': 'Prowlarr',
        'description': 'Indexer-Manager für Sonarr, Radarr und andere *arr-Apps',
        'description_en': 'Indexer manager for Sonarr, Radarr and other *arr apps',
        'icon': 'bi-search',
        'category': 'Media',
        'pod_name': 'prowlarr',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'prowlarr',
                'image': 'lscr.io/linuxserver/prowlarr:latest',
                'ports': '9696:9696',
                'env': (
                    'PUID=1000\n'
                    'PGID=1000\n'
                    'TZ=Europe/Vienna'
                ),
                'volumes': 'prowlarr-config:/config:Z',
            },
        ],
    },

    # ── Dokumente ─────────────────────────────────────────────────
    'paperless-redis-postgres': {
        'label': 'Paperless-ngx + Redis + PostgreSQL',
        'description': 'Dokumenten-Management-System mit OCR und automatischer Verschlagwortung',
        'description_en': 'Document management system with OCR and automatic tagging',
        'icon': 'bi-file-earmark-text',
        'category': 'Dokumente',
        'pod_name': 'paperless',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'paperless',
                'image': 'ghcr.io/paperless-ngx/paperless-ngx:latest',
                'ports': '8000:8000',
                'env': (
                    'PAPERLESS_REDIS=redis://127.0.0.1:6379\n'
                    'PAPERLESS_DBHOST=127.0.0.1\n'
                    'PAPERLESS_DBPORT=5432\n'
                    'PAPERLESS_DBNAME=paperless\n'
                    'PAPERLESS_DBUSER=paperless\n'
                    'PAPERLESS_DBPASS=changeme\n'
                    'PAPERLESS_ADMIN_USER=admin\n'
                    'PAPERLESS_ADMIN_PASSWORD=changeme\n'
                    'PAPERLESS_SECRET_KEY=changeme_secret_key_min_50_chars_long_here'
                ),
                'volumes': (
                    'paperless-data:/usr/src/paperless/data:Z\n'
                    'paperless-media:/usr/src/paperless/media:Z\n'
                    'paperless-export:/usr/src/paperless/export:Z\n'
                    'paperless-consume:/usr/src/paperless/consume:Z'
                ),
                'run_as_user': 0,
                'run_as_group': 0,
            },
            {
                'name': 'redis',
                'image': 'docker.io/redis:7-alpine',
                'command': 'redis-server --appendonly yes',
                'volumes': 'paperless-redis:/data:Z',
            },
            {
                'name': 'postgres',
                'image': 'docker.io/postgres:16',
                'env': (
                    'POSTGRES_USER=paperless\n'
                    'POSTGRES_PASSWORD=changeme\n'
                    'POSTGRES_DB=paperless'
                ),
                'volumes': 'paperless-db:/var/lib/postgresql/data:Z',
                'run_as_user': 999,
                'run_as_group': 999,
            },
        ],
    },

    # ── Kommunikation ─────────────────────────────────────────────
    'mattermost-postgres': {
        'label': 'Mattermost',
        'description': 'Self-hosted Team-Chat als Slack-Alternative mit Channels und Bots',
        'description_en': 'Self-hosted team chat as Slack alternative with channels and bots',
        'icon': 'bi-chat-dots',
        'category': 'Kommunikation',
        'pod_name': 'mattermost',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'mattermost',
                'image': 'docker.io/mattermost/mattermost-team-edition:latest',
                'ports': '8065:8065',
                'env': (
                    'MM_SQLSETTINGS_DRIVERNAME=postgres\n'
                    'MM_SQLSETTINGS_DATASOURCE=postgres://mattermost:changeme@127.0.0.1:5432/mattermost?sslmode=disable\n'
                    'MM_SERVICESETTINGS_SITEURL=http://localhost:8065'
                ),
                'volumes': (
                    'mattermost-data:/mattermost/data:Z\n'
                    'mattermost-logs:/mattermost/logs:Z\n'
                    'mattermost-config:/mattermost/config:Z\n'
                    'mattermost-plugins:/mattermost/plugins:Z'
                ),
                'run_as_user': 0,
                'run_as_group': 0,
            },
            {
                'name': 'postgres',
                'image': 'docker.io/postgres:16',
                'env': (
                    'POSTGRES_USER=mattermost\n'
                    'POSTGRES_PASSWORD=changeme\n'
                    'POSTGRES_DB=mattermost'
                ),
                'volumes': 'mattermost-db:/var/lib/postgresql/data:Z',
                'run_as_user': 999,
                'run_as_group': 999,
            },
        ],
        'db_variants': {
            'replace': 'postgres',
            'options': [
                {
                    'key': 'postgres',
                    'label': 'PostgreSQL 16',
                    'icon': 'bi-elephant',
                    'container': {
                        'name': 'postgres',
                        'image': 'docker.io/postgres:16',
                        'env': (
                            'POSTGRES_USER=mattermost\n'
                            'POSTGRES_PASSWORD=changeme\n'
                            'POSTGRES_DB=mattermost'
                        ),
                        'volumes': 'mattermost-db:/var/lib/postgresql/data:Z',
                        'run_as_user': 999,
                        'run_as_group': 999,
                    },
                },
                {
                    'key': 'mysql',
                    'label': 'MySQL 8',
                    'icon': 'bi-database-fill',
                    'container': {
                        'name': 'mysql',
                        'image': 'docker.io/mysql:8',
                        'env': (
                            'MYSQL_USER=mattermost\n'
                            'MYSQL_PASSWORD=changeme\n'
                            'MYSQL_DATABASE=mattermost\n'
                            'MYSQL_ROOT_PASSWORD=changeme_root'
                        ),
                        'volumes': 'mattermost-db:/var/lib/mysql:Z',
                        'run_as_user': 999,
                        'run_as_group': 999,
                    },
                    'app_env': (
                        'MM_SQLSETTINGS_DRIVERNAME=mysql\n'
                        'MM_SQLSETTINGS_DATASOURCE=mattermost:changeme@tcp(127.0.0.1:3306)/mattermost?charset=utf8mb4,utf8&readTimeout=30s&writeTimeout=30s\n'
                        'MM_SERVICESETTINGS_SITEURL=http://localhost:8065'
                    ),
                },
            ],
        },
    },

    # ── RSS / Feed ────────────────────────────────────────────────
    'miniflux-postgres': {
        'label': 'Miniflux + PostgreSQL',
        'description': 'Minimalistischer RSS-Reader mit Weboberfläche und API',
        'description_en': 'Minimalist RSS reader with web interface and API',
        'icon': 'bi-rss',
        'category': 'RSS',
        'pod_name': 'miniflux',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'miniflux',
                'image': 'docker.io/miniflux/miniflux:latest',
                'ports': '8080:8080',
                'env': (
                    'DATABASE_URL=postgres://miniflux:changeme@127.0.0.1/miniflux?sslmode=disable\n'
                    'RUN_MIGRATIONS=1\n'
                    'CREATE_ADMIN=1\n'
                    'ADMIN_USERNAME=admin\n'
                    'ADMIN_PASSWORD=changeme'
                ),
            },
            {
                'name': 'postgres',
                'image': 'docker.io/postgres:16',
                'env': (
                    'POSTGRES_USER=miniflux\n'
                    'POSTGRES_PASSWORD=changeme\n'
                    'POSTGRES_DB=miniflux'
                ),
                'volumes': 'miniflux-db:/var/lib/postgresql/data:Z',
                'run_as_user': 999,
                'run_as_group': 999,
            },
        ],
    },

    # ── Ansible ───────────────────────────────────────────────────
    'semaphore-postgres': {
        'label': 'Semaphore',
        'description': 'Web-UI für Ansible-Playbooks mit Inventar- und Task-Verwaltung',
        'description_en': 'Web UI for Ansible playbooks with inventory and task management',
        'icon': 'bi-play-btn',
        'category': 'DevOps',
        'pod_name': 'semaphore',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'semaphore',
                'image': 'docker.io/semaphoreui/semaphore:latest',
                'ports': '3000:3000',
                'env': (
                    'SEMAPHORE_DB_DIALECT=postgres\n'
                    'SEMAPHORE_DB_HOST=127.0.0.1\n'
                    'SEMAPHORE_DB_PORT=5432\n'
                    'SEMAPHORE_DB_USER=semaphore\n'
                    'SEMAPHORE_DB_PASS=changeme\n'
                    'SEMAPHORE_DB=semaphore\n'
                    'SEMAPHORE_PLAYBOOK_PATH=/tmp/semaphore\n'
                    'SEMAPHORE_ADMIN=admin\n'
                    'SEMAPHORE_ADMIN_PASSWORD=changeme\n'
                    'SEMAPHORE_ADMIN_EMAIL=admin@example.com'
                ),
                'volumes': 'semaphore-data:/home/semaphore:Z',
            },
            {
                'name': 'postgres',
                'image': 'docker.io/postgres:16',
                'env': (
                    'POSTGRES_USER=semaphore\n'
                    'POSTGRES_PASSWORD=changeme\n'
                    'POSTGRES_DB=semaphore'
                ),
                'volumes': 'semaphore-db:/var/lib/postgresql/data:Z',
                'run_as_user': 999,
                'run_as_group': 999,
            },
        ],
        'db_variants': {
            'replace': 'postgres',
            'options': [
                {
                    'key': 'postgres',
                    'label': 'PostgreSQL 16',
                    'icon': 'bi-elephant',
                    'container': {
                        'name': 'postgres',
                        'image': 'docker.io/postgres:16',
                        'env': (
                            'POSTGRES_USER=semaphore\n'
                            'POSTGRES_PASSWORD=changeme\n'
                            'POSTGRES_DB=semaphore'
                        ),
                        'volumes': 'semaphore-db:/var/lib/postgresql/data:Z',
                        'run_as_user': 999,
                        'run_as_group': 999,
                    },
                },
                {
                    'key': 'mysql',
                    'label': 'MySQL 8',
                    'icon': 'bi-database-fill',
                    'container': {
                        'name': 'mysql',
                        'image': 'docker.io/mysql:8',
                        'env': (
                            'MYSQL_USER=semaphore\n'
                            'MYSQL_PASSWORD=changeme\n'
                            'MYSQL_DATABASE=semaphore\n'
                            'MYSQL_ROOT_PASSWORD=changeme_root'
                        ),
                        'volumes': 'semaphore-db:/var/lib/mysql:Z',
                        'run_as_user': 999,
                        'run_as_group': 999,
                    },
                    'app_env': (
                        'SEMAPHORE_DB_DIALECT=mysql\n'
                        'SEMAPHORE_DB_HOST=127.0.0.1\n'
                        'SEMAPHORE_DB_PORT=3306\n'
                        'SEMAPHORE_DB_USER=semaphore\n'
                        'SEMAPHORE_DB_PASS=changeme\n'
                        'SEMAPHORE_DB=semaphore\n'
                        'SEMAPHORE_PLAYBOOK_PATH=/tmp/semaphore\n'
                        'SEMAPHORE_ADMIN=admin\n'
                        'SEMAPHORE_ADMIN_PASSWORD=changeme\n'
                        'SEMAPHORE_ADMIN_EMAIL=admin@example.com'
                    ),
                },
            ],
        },
    },

    # ── Web App Template ──────────────────────────────────────────
    'nginx-app-postgres': {
        'label': 'Nginx + App + PostgreSQL',
        'description': 'Vorlagen-Stack: Nginx + eigene App + PostgreSQL-Datenbank',
        'description_en': 'Template stack: Nginx + custom app + PostgreSQL database',
        'icon': 'bi-stack',
        'category': 'Web',
        'pod_name': 'webapp',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'nginx',
                'image': 'docker.io/nginx:stable',
                'ports': '8080:80',
                'volumes': 'webapp-nginx:/etc/nginx/conf.d:Z',
            },
            {
                'name': 'app',
                'image': 'docker.io/python:3.12-slim',
                'ports': '8000:8000',
                'env': 'DATABASE_URL=postgresql://appuser:changeme@127.0.0.1:5432/appdb',
                'volumes': 'webapp-app:/app:Z',
                'command': 'python -m http.server 8000 --directory /app',
            },
            {
                'name': 'postgres',
                'image': 'docker.io/postgres:16',
                'env': (
                    'POSTGRES_USER=appuser\n'
                    'POSTGRES_PASSWORD=changeme\n'
                    'POSTGRES_DB=appdb'
                ),
                'volumes': 'webapp-db:/var/lib/postgresql/data:Z',
                'run_as_user': 999,
                'run_as_group': 999,
            },
        ],
    },

    # ── Backup ────────────────────────────────────────────────────
    'minio': {
        'label': 'MinIO (S3-compatible)',
        'description': 'S3-kompatibler Objekt-Speicher für self-hosted Cloud-Storage',
        'description_en': 'S3-compatible object storage for self-hosted cloud storage',
        'icon': 'bi-bucket',
        'category': 'Storage',
        'pod_name': 'minio',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'minio',
                'image': 'docker.io/minio/minio:latest',
                'ports': '9000:9000\n9001:9001',
                'env': (
                    'MINIO_ROOT_USER=admin\n'
                    'MINIO_ROOT_PASSWORD=changeme123'
                ),
                'volumes': 'minio-data:/data:Z',
                'args': 'server /data --console-address :9001',
            },
        ],
    },

    # ── Storage (Sync) ────────────────────────────────────────────
    'syncthing': {
        'label': 'Syncthing',
        'description': 'Dezentrale Datei-Synchronisierung zwischen Geräten ohne Server',
        'description_en': 'Decentralized file synchronization between devices without a server',
        'icon': 'bi-arrow-repeat',
        'category': 'Storage',
        'pod_name': 'syncthing',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'syncthing',
                'image': 'docker.io/syncthing/syncthing:latest',
                'ports': '8384:8384\n22000:22000',
                'env': (
                    'PUID=1000\n'
                    'PGID=1000\n'
                    'TZ=Europe/Vienna'
                ),
                'volumes': (
                    'syncthing-config:/var/syncthing/config:Z\n'
                    'syncthing-data:/var/syncthing/data:Z'
                ),
            },
        ],
    },

    # ── Home Automation ───────────────────────────────────────────
    'home-assistant': {
        'label': 'Home Assistant',
        'description': 'Heimautomatisierungs-Plattform für Smart-Home-Geräte und Automatisierungen',
        'description_en': 'Home automation platform for smart home devices and automations',
        'icon': 'bi-house-gear',
        'category': 'Home',
        'pod_name': 'homeassistant',
        'restart_policy': 'Always',
        'mode': 'rootful',
        'host_network': True,
        'containers': [
            {
                'name': 'homeassistant',
                'image': 'ghcr.io/home-assistant/home-assistant:stable',
                'env': 'TZ=Europe/Vienna',
                'volumes': 'homeassistant-config:/config:Z',
            },
        ],
    },

    # ── Automation ────────────────────────────────────────────────
    'n8n-postgres': {
        'label': 'n8n',
        'description': 'Low-Code-Workflow-Automatisierung mit 400+ Integrationen',
        'description_en': 'Low-code workflow automation with 400+ integrations',
        'icon': 'bi-diagram-3',
        'category': 'Automation',
        'pod_name': 'n8n',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'n8n',
                'image': 'docker.io/n8nio/n8n:latest',
                'ports': '5678:5678',
                'env': (
                    'DB_TYPE=postgresdb\n'
                    'DB_POSTGRESDB_HOST=127.0.0.1\n'
                    'DB_POSTGRESDB_PORT=5432\n'
                    'DB_POSTGRESDB_DATABASE=n8n\n'
                    'DB_POSTGRESDB_USER=n8n\n'
                    'DB_POSTGRESDB_PASSWORD=changeme\n'
                    'N8N_HOST=localhost\n'
                    'N8N_PORT=5678\n'
                    'N8N_PROTOCOL=http\n'
                    'WEBHOOK_URL=http://localhost:5678/\n'
                    'GENERIC_TIMEZONE=Europe/Vienna'
                ),
                'volumes': 'n8n-data:/home/node/.n8n:Z',
                'run_as_user': 0,
                'run_as_group': 0,
            },
            {
                'name': 'postgres',
                'image': 'docker.io/postgres:16',
                'env': (
                    'POSTGRES_USER=n8n\n'
                    'POSTGRES_PASSWORD=changeme\n'
                    'POSTGRES_DB=n8n'
                ),
                'volumes': 'n8n-db:/var/lib/postgresql/data:Z',
                'run_as_user': 999,
                'run_as_group': 999,
            },
        ],
        'db_variants': {
            'replace': 'postgres',
            'options': [
                {
                    'key': 'postgres',
                    'label': 'PostgreSQL 16',
                    'icon': 'bi-elephant',
                    'container': {
                        'name': 'postgres',
                        'image': 'docker.io/postgres:16',
                        'env': (
                            'POSTGRES_USER=n8n\n'
                            'POSTGRES_PASSWORD=changeme\n'
                            'POSTGRES_DB=n8n'
                        ),
                        'volumes': 'n8n-db:/var/lib/postgresql/data:Z',
                        'run_as_user': 999,
                        'run_as_group': 999,
                    },
                },
                {
                    'key': 'mysql',
                    'label': 'MySQL 8',
                    'icon': 'bi-database-fill',
                    'container': {
                        'name': 'mysql',
                        'image': 'docker.io/mysql:8',
                        'env': (
                            'MYSQL_USER=n8n\n'
                            'MYSQL_PASSWORD=changeme\n'
                            'MYSQL_DATABASE=n8n\n'
                            'MYSQL_ROOT_PASSWORD=changeme_root'
                        ),
                        'volumes': 'n8n-db:/var/lib/mysql:Z',
                        'run_as_user': 999,
                        'run_as_group': 999,
                    },
                    'app_env': (
                        'DB_TYPE=mysqldb\n'
                        'DB_MYSQLDB_HOST=127.0.0.1\n'
                        'DB_MYSQLDB_PORT=3306\n'
                        'DB_MYSQLDB_DATABASE=n8n\n'
                        'DB_MYSQLDB_USER=n8n\n'
                        'DB_MYSQLDB_PASSWORD=changeme\n'
                        'N8N_HOST=localhost\n'
                        'N8N_PORT=5678\n'
                        'N8N_PROTOCOL=http\n'
                        'WEBHOOK_URL=http://localhost:5678/\n'
                        'GENERIC_TIMEZONE=Europe/Vienna'
                    ),
                },
            ],
        },
        'sqlite_option': True,
        'sqlite_env': (
            'DB_TYPE=sqlite\n'
            'N8N_HOST=localhost\n'
            'N8N_PORT=5678\n'
            'N8N_PROTOCOL=http\n'
            'WEBHOOK_URL=http://localhost:5678/\n'
            'GENERIC_TIMEZONE=Europe/Vienna'
        ),
    },

    # ── VPN / Network ─────────────────────────────────────────────
    'headscale': {
        'label': 'Headscale',
        'description': 'Self-hosted Tailscale-Control-Server für ein privates WireGuard-Mesh-VPN',
        'description_en': 'Self-hosted Tailscale control server for a private WireGuard mesh VPN',
        'icon': 'bi-hdd-network',
        'category': 'VPN',
        'pod_name': 'headscale',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'headscale',
                'image': 'ghcr.io/juanfont/headscale:latest',
                'ports': '8080:8080\n9090:9090',
                'volumes': (
                    'headscale-config:/etc/headscale:Z\n'
                    'headscale-data:/var/lib/headscale:Z'
                ),
                'command': '/ko-app/headscale serve',
            },
        ],
    },

    'wg-easy': {
        'label': 'WireGuard Easy',
        'description': 'WireGuard VPN-Server mit einfacher Web-Oberfläche zur Verwaltung',
        'description_en': 'WireGuard VPN server with simple web interface for management',
        'icon': 'bi-shield-lock',
        'category': 'VPN',
        'pod_name': 'wg-easy',
        'restart_policy': 'Always',
        'mode': 'rootful',
        'containers': [
            {
                'name': 'wg-easy',
                'image': 'ghcr.io/wg-easy/wg-easy:latest',
                'ports': '51820:51820\n51821:51821',
                'env': (
                    'WG_HOST=changeme\n'
                    'PASSWORD_HASH=changeme\n'
                    'WG_PORT=51820\n'
                    'WG_DEFAULT_DNS=1.1.1.1\n'
                    'WG_ALLOWED_IPS=0.0.0.0/0'
                ),
                'volumes': 'wg-easy-data:/etc/wireguard:Z',
                'cap_add': 'NET_ADMIN\nSYS_MODULE',
            },
        ],
    },

    # ── Tools ─────────────────────────────────────────────────────
    'stirling-pdf': {
        'label': 'Stirling PDF',
        'description': 'Lokales PDF-Werkzeug: Zusammenführen, Teilen, Konvertieren und mehr',
        'description_en': 'Local PDF tool: merge, split, convert and more',
        'icon': 'bi-file-earmark-pdf',
        'category': 'Tools',
        'pod_name': 'stirling-pdf',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'stirling-pdf',
                'image': 'docker.io/stirlingtools/stirling-pdf:latest',
                'ports': '8080:8080',
                'env': 'DOCKER_ENABLE_SECURITY=false\nLANGS=de_DE',
                'volumes': 'stirling-pdf-data:/usr/share/tessdata:Z\nstirling-pdf-config:/configs:Z',
            },
        ],
    },

    'changedetection': {
        'label': 'changedetection.io',
        'description': 'Web-Änderungsüberwachung mit Push-Benachrichtigungen per HTTP',
        'description_en': 'Web change detection with push notifications via HTTP',
        'icon': 'bi-eye',
        'category': 'Tools',
        'pod_name': 'changedetection',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'changedetection',
                'image': 'ghcr.io/dgtlmoon/changedetection.io:latest',
                'ports': '5000:5000',
                'volumes': 'changedetection-data:/datastore:Z',
                'env': 'PLAYWRIGHT_DRIVER_URL=ws://localhost:3000/?stealth=1&--disable-web-security=true',
            },
            {
                'name': 'playwright-chrome',
                'image': 'ghcr.io/dgtlmoon/sockpuppetbrowser:latest',
                'env': 'SCREEN_WIDTH=1920\nSCREEN_HEIGHT=1024\nSCREEN_DEPTH=16\nMAX_CONCURRENT_CHROME_PROCESSES=10',
            },
        ],
    },

    'rustdesk-server': {
        'label': 'RustDesk Server',
        'description': 'Self-hosted Remote-Desktop-Server als TeamViewer-Alternative',
        'description_en': 'Self-hosted remote desktop server as TeamViewer alternative',
        'icon': 'bi-display',
        'category': 'Tools',
        'pod_name': 'rustdesk-server',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'hbbs',
                'image': 'docker.io/rustdesk/rustdesk-server:latest',
                'ports': '21115:21115\n21116:21116\n21118:21118',
                'volumes': 'rustdesk-data:/root:Z',
                'args': 'hbbs',
            },
            {
                'name': 'hbbr',
                'image': 'docker.io/rustdesk/rustdesk-server:latest',
                'ports': '21117:21117\n21119:21119',
                'volumes': 'rustdesk-data:/root:Z',
                'args': 'hbbr',
            },
        ],
    },

    # ── Productivity ──────────────────────────────────────────────
    'linkding': {
        'label': 'Linkding',
        'description': 'Minimaler self-hosted Lesezeichen-Manager mit Browser-Extension',
        'description_en': 'Minimal self-hosted bookmark manager with browser extension',
        'icon': 'bi-bookmark',
        'category': 'Productivity',
        'pod_name': 'linkding',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'linkding',
                'image': 'docker.io/sissbruecker/linkding:latest',
                'ports': '9090:9090',
                'env': (
                    'LD_SUPERUSER_NAME=admin\n'
                    'LD_SUPERUSER_PASSWORD=changeme'
                ),
                'volumes': 'linkding-data:/etc/linkding/data:Z',
            },
        ],
    },

    'vikunja': {
        'label': 'Vikunja',
        'description': 'Self-hosted Aufgabenverwaltung und Projektmanagement',
        'description_en': 'Self-hosted task management and project management',
        'icon': 'bi-kanban',
        'category': 'Productivity',
        'pod_name': 'vikunja',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'vikunja',
                'image': 'docker.io/vikunja/vikunja:latest',
                'ports': '3456:3456',
                'env': (
                    'VIKUNJA_DATABASE_TYPE=postgres\n'
                    'VIKUNJA_DATABASE_HOST=127.0.0.1\n'
                    'VIKUNJA_DATABASE_DATABASE=vikunja\n'
                    'VIKUNJA_DATABASE_USER=vikunja\n'
                    'VIKUNJA_DATABASE_PASSWORD=changeme\n'
                    'VIKUNJA_SERVICE_JWTSECRET=changeme\n'
                    'VIKUNJA_SERVICE_FRONTENDURL=http://localhost:3456\n'
                    'VIKUNJA_SERVICE_PUBLICURL=http://localhost:3456'
                ),
                'volumes': 'vikunja-files:/app/vikunja/files:Z',
                'run_as_user': 0,
                'run_as_group': 0,
            },
            {
                'name': 'postgres',
                'image': 'docker.io/postgres:16',
                'env': (
                    'POSTGRES_USER=vikunja\n'
                    'POSTGRES_PASSWORD=changeme\n'
                    'POSTGRES_DB=vikunja'
                ),
                'volumes': 'vikunja-db:/var/lib/postgresql/data:Z',
                'run_as_user': 999,
                'run_as_group': 999,
            },
        ],
        'db_variants': {
            'replace': 'postgres',
            'options': [
                {
                    'key': 'postgres',
                    'label': 'PostgreSQL 16',
                    'icon': 'bi-elephant',
                    'container': {
                        'name': 'postgres',
                        'image': 'docker.io/postgres:16',
                        'env': (
                            'POSTGRES_USER=vikunja\n'
                            'POSTGRES_PASSWORD=changeme\n'
                            'POSTGRES_DB=vikunja'
                        ),
                        'volumes': 'vikunja-db:/var/lib/postgresql/data:Z',
                        'run_as_user': 999,
                        'run_as_group': 999,
                    },
                },
                {
                    'key': 'mariadb',
                    'label': 'MariaDB 11',
                    'icon': 'bi-database',
                    'container': {
                        'name': 'mariadb',
                        'image': 'docker.io/mariadb:11',
                        'env': (
                            'MARIADB_USER=vikunja\n'
                            'MARIADB_PASSWORD=changeme\n'
                            'MARIADB_ROOT_PASSWORD=changeme_root\n'
                            'MARIADB_DATABASE=vikunja'
                        ),
                        'volumes': 'vikunja-db:/var/lib/mysql:Z',
                        'run_as_user': 999,
                        'run_as_group': 999,
                    },
                    'app_env': (
                        'VIKUNJA_DATABASE_TYPE=mysql\n'
                        'VIKUNJA_DATABASE_HOST=127.0.0.1\n'
                        'VIKUNJA_DATABASE_DATABASE=vikunja\n'
                        'VIKUNJA_DATABASE_USER=vikunja\n'
                        'VIKUNJA_DATABASE_PASSWORD=changeme\n'
                        'VIKUNJA_SERVICE_JWTSECRET=changeme\n'
                        'VIKUNJA_SERVICE_FRONTENDURL=http://localhost:3456\n'
                        'VIKUNJA_SERVICE_PUBLICURL=http://localhost:3456'
                    ),
                },
            ],
        },
        'sqlite_option': True,
        'sqlite_env': (
            'VIKUNJA_DATABASE_TYPE=sqlite\n'
            'VIKUNJA_SERVICE_JWTSECRET=changeme\n'
            'VIKUNJA_SERVICE_FRONTENDURL=http://localhost:3456'
        ),
        'sqlite_volumes_append': 'vikunja-db:/app/vikunja:Z',
    },

    'bookstack': {
        'label': 'BookStack',
        'description': 'Wiki- und Dokumentationsplattform mit Bücher-/Kapitel-Struktur',
        'description_en': 'Wiki and documentation platform with book/chapter structure',
        'icon': 'bi-journal-text',
        'category': 'Productivity',
        'pod_name': 'bookstack',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'bookstack',
                'image': 'lscr.io/linuxserver/bookstack:latest',
                'ports': '8080:80',
                'env': (
                    'PUID=1000\n'
                    'PGID=1000\n'
                    'APP_URL=http://localhost:8080\n'
                    'DB_HOST=127.0.0.1\n'
                    'DB_PORT=3306\n'
                    'DB_USER=bookstack\n'
                    'DB_PASS=changeme\n'
                    'DB_DATABASE=bookstack'
                ),
                'volumes': 'bookstack-config:/config:Z',
            },
            {
                'name': 'mariadb',
                'image': 'docker.io/mariadb:11',
                'env': (
                    'MARIADB_ROOT_PASSWORD=changeme_root\n'
                    'MARIADB_USER=bookstack\n'
                    'MARIADB_PASSWORD=changeme\n'
                    'MARIADB_DATABASE=bookstack'
                ),
                'volumes': 'bookstack-db:/var/lib/mysql:Z',
                'run_as_user': 999,
                'run_as_group': 999,
            },
        ],
    },

    # ── DevOps ────────────────────────────────────────────────────
    'code-server': {
        'label': 'code-server',
        'description': 'VS Code im Browser — Entwicklungsumgebung überall erreichbar',
        'description_en': 'VS Code in the browser — development environment accessible anywhere',
        'icon': 'bi-code-slash',
        'category': 'DevOps',
        'pod_name': 'code-server',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'code-server',
                'image': 'lscr.io/linuxserver/code-server:latest',
                'ports': '8443:8443',
                'env': (
                    'PUID=1000\n'
                    'PGID=1000\n'
                    'TZ=Europe/Vienna\n'
                    'PASSWORD=changeme\n'
                    'SUDO_PASSWORD=changeme'
                ),
                'volumes': 'code-server-config:/config:Z',
            },
        ],
    },

    # ── Security (Authentik) ──────────────────────────────────────
    'authentik': {
        'label': 'Authentik',
        'description': 'Flexibler Identity Provider mit SSO, OAuth2, SAML und LDAP',
        'description_en': 'Flexible identity provider with SSO, OAuth2, SAML and LDAP',
        'icon': 'bi-person-badge',
        'category': 'Security',
        'pod_name': 'authentik',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'authentik-server',
                'image': 'ghcr.io/goauthentik/server:latest',
                'ports': '9000:9000\n9443:9443',
                'env': (
                    'AUTHENTIK_REDIS__HOST=127.0.0.1\n'
                    'AUTHENTIK_POSTGRESQL__HOST=127.0.0.1\n'
                    'AUTHENTIK_POSTGRESQL__USER=authentik\n'
                    'AUTHENTIK_POSTGRESQL__PASSWORD=changeme\n'
                    'AUTHENTIK_POSTGRESQL__NAME=authentik\n'
                    'AUTHENTIK_SECRET_KEY=changeme'
                ),
                'command': 'dumb-init -- ak server',
            },
            {
                'name': 'authentik-worker',
                'image': 'ghcr.io/goauthentik/server:latest',
                'env': (
                    'AUTHENTIK_REDIS__HOST=127.0.0.1\n'
                    'AUTHENTIK_POSTGRESQL__HOST=127.0.0.1\n'
                    'AUTHENTIK_POSTGRESQL__USER=authentik\n'
                    'AUTHENTIK_POSTGRESQL__PASSWORD=changeme\n'
                    'AUTHENTIK_POSTGRESQL__NAME=authentik\n'
                    'AUTHENTIK_SECRET_KEY=changeme'
                ),
                'command': 'dumb-init -- ak worker',
            },
            {
                'name': 'postgres',
                'image': 'docker.io/postgres:16',
                'env': (
                    'POSTGRES_USER=authentik\n'
                    'POSTGRES_PASSWORD=changeme\n'
                    'POSTGRES_DB=authentik'
                ),
                'volumes': 'authentik-db:/var/lib/postgresql/data:Z',
                'run_as_user': 999,
                'run_as_group': 999,
            },
            {
                'name': 'redis',
                'image': 'docker.io/redis:7-alpine',
                'command': 'redis-server --appendonly yes',
                'volumes': 'authentik-redis:/data:Z',
            },
        ],
    },

    # ── DNS ───────────────────────────────────────────────────────
    'technitium': {
        'label': 'Technitium DNS',
        'description': 'Self-hosted DNS-Server mit Blocklisten und Web-Oberfläche',
        'description_en': 'Self-hosted DNS server with blocklists and web interface',
        'icon': 'bi-reception-4',
        'category': 'DNS',
        'pod_name': 'technitium',
        'restart_policy': 'Always',
        'mode': 'rootful',
        'containers': [
            {
                'name': 'technitium',
                'image': 'docker.io/technitium/dns-server:latest',
                'ports': '53:53\n5380:5380',
                'env': (
                    'DNS_SERVER_DOMAIN=dns.local\n'
                    'DNS_SERVER_ADMIN_PASSWORD=changeme'
                ),
                'volumes': 'technitium-config:/etc/dns:Z',
            },
        ],
    },

    'pihole': {
        'label': 'Pi-hole',
        'description': 'Netzwerkweiter Werbeblocker als DNS-Sinkhole',
        'description_en': 'Network-wide ad blocker as a DNS sinkhole',
        'icon': 'bi-funnel',
        'category': 'DNS',
        'pod_name': 'pihole',
        'restart_policy': 'Always',
        'mode': 'rootful',
        'containers': [
            {
                'name': 'pihole',
                'image': 'docker.io/pihole/pihole:latest',
                'ports': '53:53\n8080:80',
                'env': (
                    'TZ=Europe/Vienna\n'
                    'WEBPASSWORD=changeme\n'
                    'PIHOLE_DNS_=8.8.8.8;8.8.4.4'
                ),
                'volumes': (
                    'pihole-etc:/etc/pihole:Z\n'
                    'pihole-dnsmasq:/etc/dnsmasq.d:Z'
                ),
            },
        ],
    },

    'adguard-home': {
        'label': 'AdGuard Home',
        'description': 'DNS-basierter Werbeblocker mit erweiterter Filter- und Statistikfunktion',
        'description_en': 'DNS-based ad blocker with advanced filtering and statistics',
        'icon': 'bi-shield-check',
        'category': 'DNS',
        'pod_name': 'adguard-home',
        'restart_policy': 'Always',
        'mode': 'rootful',
        'containers': [
            {
                'name': 'adguard-home',
                'image': 'docker.io/adguard/adguardhome:latest',
                'ports': '53:53\n3000:3000\n80:80',
                'volumes': (
                    'adguard-home-work:/opt/adguardhome/work:Z\n'
                    'adguard-home-conf:/opt/adguardhome/conf:Z'
                ),
            },
        ],
    },

    # ── Media (Musik) ─────────────────────────────────────────────
    'navidrome': {
        'label': 'Navidrome',
        'description': 'Leichtgewichtiger Musik-Streaming-Server, kompatibel mit Subsonic/Airsonic-Clients',
        'description_en': 'Lightweight music streaming server, compatible with Subsonic/Airsonic clients',
        'icon': 'bi-music-note-beamed',
        'category': 'Media',
        'description': 'Leichtgewichtiger Musik-Streaming-Server, kompatibel mit Subsonic/Airsonic-Clients',
        'description_en': 'Lightweight music streaming server, compatible with Subsonic/Airsonic clients',
        'pod_name': 'navidrome',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'navidrome',
                'image': 'docker.io/deluan/navidrome:latest',
                'ports': '4533:4533',
                'env': (
                    'ND_SCANSCHEDULE=1h\n'
                    'ND_LOGLEVEL=info\n'
                    'ND_SESSIONTIMEOUT=24h\n'
                    'ND_BASEURL=\n'
                    'TZ=Europe/Vienna'
                ),
                'volumes': (
                    'navidrome-data:/data:Z\n'
                    '/music:/music:ro'
                ),
            },
        ],
    },

    # ── Network ───────────────────────────────────────────────────
    'unifi': {
        'label': 'UniFi Network Application',
        'description': 'Self-hosted UniFi Network Application zur Verwaltung von Ubiquiti Access Points und Switches',
        'description_en': 'Self-hosted UniFi Network Application for managing Ubiquiti access points and switches',
        'icon': 'bi-wifi',
        'category': 'Network',
        'description': 'Self-hosted UniFi Network Application zur Verwaltung von Ubiquiti Access Points und Switches',
        'description_en': 'Self-hosted UniFi Network Application for managing Ubiquiti access points and switches',
        'pod_name': 'unifi',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'unifi',
                'image': 'lscr.io/linuxserver/unifi-network-application:latest',
                'ports': '8443:8443\n8080:8080',
                'env': (
                    'PUID=1000\n'
                    'PGID=1000\n'
                    'TZ=Europe/Vienna\n'
                    'MONGO_USER=unifi\n'
                    'MONGO_PASS=changeme\n'
                    'MONGO_HOST=127.0.0.1\n'
                    'MONGO_PORT=27017\n'
                    'MONGO_DBNAME=unifi\n'
                    'MONGO_AUTHSOURCE=admin'
                ),
                'volumes': 'unifi-config:/config:Z',
            },
            {
                'name': 'mongodb',
                'image': 'docker.io/mongo:7',
                'env': (
                    'MONGO_INITDB_ROOT_USERNAME=unifi\n'
                    'MONGO_INITDB_ROOT_PASSWORD=changeme'
                ),
                'volumes': 'unifi-db:/data/db:Z',
            },
        ],
    },

    # ── Security (Passbolt) ───────────────────────────────────────
    'passbolt': {
        'label': 'Passbolt',
        'description': 'Open-Source Passwort-Manager für Teams mit End-to-End-Verschlüsselung und Browser-Extension',
        'description_en': 'Open-source password manager for teams with end-to-end encryption and browser extension',
        'icon': 'bi-key',
        'category': 'Security',
        'description': 'Open-Source Passwort-Manager für Teams mit End-to-End-Verschlüsselung und Browser-Extension',
        'description_en': 'Open-source password manager for teams with end-to-end encryption and browser extension',
        'pod_name': 'passbolt',
        'restart_policy': 'Always',
        'mode': 'rootful',
        'containers': [
            {
                'name': 'passbolt',
                'image': 'docker.io/passbolt/passbolt:latest-ce',
                'ports': '80:80\n443:443',
                'env': (
                    'APP_FULL_BASE_URL=https://passbolt.example.com\n'
                    'DATASOURCES_DEFAULT_HOST=127.0.0.1\n'
                    'DATASOURCES_DEFAULT_USERNAME=passbolt\n'
                    'DATASOURCES_DEFAULT_PASSWORD=changeme\n'
                    'DATASOURCES_DEFAULT_DATABASE=passbolt\n'
                    'EMAIL_TRANSPORT_DEFAULT_HOST=smtp.example.com\n'
                    'EMAIL_TRANSPORT_DEFAULT_PORT=587\n'
                    'EMAIL_TRANSPORT_DEFAULT_TLS=true\n'
                    'EMAIL_DEFAULT_FROM=passbolt@example.com'
                ),
                'volumes': (
                    'passbolt-gpg:/etc/passbolt/gpg:Z\n'
                    'passbolt-jwt:/etc/passbolt/jwt:Z'
                ),
            },
            {
                'name': 'mariadb',
                'image': 'docker.io/mariadb:11',
                'env': (
                    'MARIADB_ROOT_PASSWORD=changeme_root\n'
                    'MARIADB_USER=passbolt\n'
                    'MARIADB_PASSWORD=changeme\n'
                    'MARIADB_DATABASE=passbolt'
                ),
                'volumes': 'passbolt-db:/var/lib/mysql:Z',
                'run_as_user': 999,
                'run_as_group': 999,
            },
        ],
    },

    # ── Productivity (Linkwarden) ─────────────────────────────────
    'linkwarden': {
        'label': 'Linkwarden',
        'description': 'Self-hosted Lesezeichen-Manager mit Archivierung, Tagging und Kollaboration',
        'description_en': 'Self-hosted bookmark manager with archiving, tagging and collaboration',
        'icon': 'bi-bookmark-star',
        'category': 'Productivity',
        'description': 'Self-hosted Lesezeichen-Manager mit Archivierung, Tagging und Kollaboration',
        'description_en': 'Self-hosted bookmark manager with archiving, tagging and collaboration',
        'pod_name': 'linkwarden',
        'restart_policy': 'Always',
        'mode': 'rootless',
        'containers': [
            {
                'name': 'linkwarden',
                'image': 'ghcr.io/linkwarden/linkwarden:latest',
                'ports': '3000:3000',
                'env': (
                    'DATABASE_URL=postgresql://linkwarden:changeme@127.0.0.1:5432/linkwarden\n'
                    'NEXTAUTH_SECRET=changeme_secret\n'
                    'NEXTAUTH_URL=http://localhost:3000\n'
                    'NEXT_PUBLIC_DISABLE_REGISTRATION=false'
                ),
                'volumes': 'linkwarden-data:/data/data:Z',
            },
            {
                'name': 'postgres',
                'image': 'docker.io/postgres:16',
                'env': (
                    'POSTGRES_USER=linkwarden\n'
                    'POSTGRES_PASSWORD=changeme\n'
                    'POSTGRES_DB=linkwarden'
                ),
                'volumes': 'linkwarden-db:/var/lib/postgresql/data:Z',
                'run_as_user': 999,
                'run_as_group': 999,
            },
        ],
    },
}


# Verbindungs-Mapping: welche Env-Vars braucht Container A um Container B zu erreichen
CONNECTION_HINTS = {
    'postgres': {
        5432: ['DB_HOST=127.0.0.1', 'DB_PORT=5432', 'DATABASE_URL=postgresql://user:pass@127.0.0.1:5432/dbname'],
    },
    'mariadb': {
        3306: ['DB_HOST=127.0.0.1', 'DB_PORT=3306', 'DATABASE_URL=mysql://user:pass@127.0.0.1:3306/dbname'],
    },
    'mysql': {
        3306: ['DB_HOST=127.0.0.1', 'DB_PORT=3306', 'DATABASE_URL=mysql://user:pass@127.0.0.1:3306/dbname'],
    },
    'redis': {
        6379: ['REDIS_URL=redis://127.0.0.1:6379', 'REDIS_HOST=127.0.0.1', 'REDIS_PORT=6379'],
    },
    'valkey': {
        6379: ['REDIS_URL=redis://127.0.0.1:6379', 'REDIS_HOST=127.0.0.1', 'REDIS_PORT=6379'],
    },
    'mongodb': {
        27017: ['MONGO_URL=mongodb://127.0.0.1:27017', 'MONGODB_HOST=127.0.0.1', 'MONGODB_PORT=27017'],
    },
    'mongo': {
        27017: ['MONGO_URL=mongodb://127.0.0.1:27017', 'MONGODB_HOST=127.0.0.1', 'MONGODB_PORT=27017'],
    },
    'influxdb': {
        8086: ['INFLUXDB_URL=http://127.0.0.1:8086', 'INFLUXDB_HOST=127.0.0.1'],
    },
    'memcached': {
        11211: ['MEMCACHED_HOST=127.0.0.1', 'MEMCACHED_PORT=11211'],
    },
    'rabbitmq': {
        5672: ['RABBITMQ_URL=amqp://user:pass@127.0.0.1:5672', 'RABBITMQ_HOST=127.0.0.1'],
    },
    'minio': {
        9000: ['S3_ENDPOINT=http://127.0.0.1:9000', 'S3_HOST=127.0.0.1', 'S3_PORT=9000'],
    },
}
