"""
Bekannte Image-Presets mit empfohlenen Einstellungen.
Felder entsprechen ContainerForm-Feldern + optionalen Pod-Empfehlungen.
"""

PRESETS = {
    # ── Webserver ────────────────────────────────────────────────
    "nginx": {
        "ports": "8080:80",
        "volumes": "nginx-html:/usr/share/nginx/html:Z\nnginx-conf:/etc/nginx/conf.d:Z",
        "run_as_user": None,
        "mode_hint": "rootless",
        "note": "Port 80 nur rootful oder sysctl. Empfohlen: 8080→80.",
        "probe": {"type": "tcpSocket", "tcp_port": 80, "initial_delay": 5, "period": 10},
    },
    "caddy": {
        "ports": "8080:80\n8443:443",
        "volumes": "caddy-data:/data:Z\ncaddy-config:/config:Z",
        "mode_hint": "rootless",
        "note": "Caddy verwaltet TLS automatisch.",
        "probe": {"type": "tcpSocket", "tcp_port": 80, "initial_delay": 5, "period": 10},
    },
    "traefik": {
        "ports": "80:80\n443:443\n8080:8080",
        "mode_hint": "rootful",
        "note": "Ports 80/443 → rootful. Traefik benötigt Socket-Zugriff (nicht mit podman play kube kompatibel).",
        "probe": {"type": "httpGet", "http_path": "/ping", "http_port": 8080, "initial_delay": 10, "period": 10},
    },
    "httpd": {
        "ports": "8080:80",
        "volumes": "apache-html:/usr/local/apache2/htdocs:Z\napache-conf:/usr/local/apache2/conf:Z",
        "mode_hint": "rootless",
        "note": "Apache HTTP Server. Port 80 nur rootful.",
        "probe": {"type": "tcpSocket", "tcp_port": 80, "initial_delay": 5, "period": 10},
    },

    # ── Datenbanken ───────────────────────────────────────────────
    "postgres": {
        "ports": "5432:5432",
        "env": "POSTGRES_USER=appuser\nPOSTGRES_PASSWORD=changeme\nPOSTGRES_DB=appdb",
        "volumes": "postgres-data:/var/lib/postgresql/data:Z",
        "mode_hint": "rootless",
        "probe": {"type": "exec", "cmd": "pg_isready -U postgres", "initial_delay": 30, "period": 10},
    },
    "mariadb": {
        "ports": "3306:3306",
        "env": "MARIADB_ROOT_PASSWORD=changeme\nMARIADB_USER=appuser\nMARIADB_PASSWORD=changeme\nMARIADB_DATABASE=appdb",
        "volumes": "mariadb-data:/var/lib/mysql:Z",
        "mode_hint": "rootless",
        "probe": {"type": "exec", "cmd": "healthcheck.sh --connect --innodb_initialized", "initial_delay": 30, "period": 10},
    },
    "mysql": {
        "ports": "3306:3306",
        "env": "MYSQL_ROOT_PASSWORD=changeme\nMYSQL_USER=appuser\nMYSQL_PASSWORD=changeme\nMYSQL_DATABASE=appdb",
        "volumes": "mysql-data:/var/lib/mysql:Z",
        "mode_hint": "rootless",
        "probe": {"type": "exec", "cmd": "mysqladmin ping -h 127.0.0.1 --silent", "initial_delay": 30, "period": 10},
    },
    "redis": {
        "ports": "6379:6379",
        "volumes": "redis-data:/data:Z",
        "command": "redis-server --appendonly yes",
        "mode_hint": "rootless",
        "note": "appendonly yes = persistente Daten.",
        "probe": {"type": "exec", "cmd": "redis-cli ping", "initial_delay": 10, "period": 10},
    },
    "valkey": {
        "ports": "6379:6379",
        "volumes": "valkey-data:/data:Z",
        "command": "valkey-server --appendonly yes",
        "mode_hint": "rootless",
        "note": "Redis-Fork, drop-in Ersatz.",
        "probe": {"type": "exec", "cmd": "valkey-cli ping", "initial_delay": 10, "period": 10},
    },
    "mongodb": {
        "ports": "27017:27017",
        "env": "MONGO_INITDB_ROOT_USERNAME=admin\nMONGO_INITDB_ROOT_PASSWORD=changeme",
        "volumes": "mongodb-data:/data/db:Z",
        "mode_hint": "rootless",
        "probe": {"type": "exec", "cmd": "mongosh --eval \"db.adminCommand('ping')\" --quiet", "initial_delay": 30, "period": 10},
    },
    "mongo": "mongodb",  # alias

    # ── Anwendungen ───────────────────────────────────────────────
    "wordpress": {
        "ports": "8080:80",
        "env": "WORDPRESS_DB_HOST=127.0.0.1:3306\nWORDPRESS_DB_USER=appuser\nWORDPRESS_DB_PASSWORD=changeme\nWORDPRESS_DB_NAME=appdb",
        "volumes": "wordpress-html:/var/www/html:Z",
        "mode_hint": "rootless",
        "note": "Zusammen mit MariaDB/MySQL deployen.",
    },
    "nextcloud": {
        "ports": "8080:80",
        "env": "POSTGRES_HOST=127.0.0.1\nPOSTGRES_DB=nextcloud\nPOSTGRES_USER=nextcloud\nPOSTGRES_PASSWORD=changeme\nNEXTCLOUD_ADMIN_USER=admin\nNEXTCLOUD_ADMIN_PASSWORD=changeme\nNEXTCLOUD_TRUSTED_DOMAINS=localhost",
        "volumes": "nextcloud-html:/var/www/html:Z",
        "mode_hint": "rootless",
        "note": "Supports PostgreSQL (default) and MySQL/MariaDB. For MySQL use MYSQL_HOST/DATABASE/USER/PASSWORD instead.",
    },
    "gitea": {
        "ports": "3000:3000\n2222:22",
        "env": "GITEA__database__DB_TYPE=sqlite3\nGITEA__database__PATH=/data/gitea/gitea.db",
        "volumes": "gitea-data:/data:Z",
        "mode_hint": "rootless",
    },
    "vaultwarden": {
        "ports": "8080:80",
        "env": "ADMIN_TOKEN=changeme\nSIGNUPS_ALLOWED=false",
        "volumes": "vaultwarden-data:/data:Z",
        "mode_hint": "rootless",
        "note": "ADMIN_TOKEN unbedingt ändern!",
    },
    "jellyfin": {
        "ports": "8096:8096",
        "env": "JELLYFIN_PublishedServerUrl=http://localhost:8096",
        "volumes": "jellyfin-config:/config:Z\njellyfin-media:/media:ro",
        "mode_hint": "rootless",
    },
    "grafana": {
        "ports": "3000:3000",
        "env": "GF_SECURITY_ADMIN_PASSWORD=changeme",
        "volumes": "grafana-data:/var/lib/grafana:Z",
        "mode_hint": "rootless",
        "probe": {"type": "httpGet", "http_path": "/api/health", "http_port": 3000, "initial_delay": 15, "period": 10},
    },
    "prometheus": {
        "ports": "9090:9090",
        "volumes": "prometheus-config:/etc/prometheus:Z\nprometheus-data:/prometheus:Z",
        "command": "--config.file=/etc/prometheus/prometheus.yml --storage.tsdb.path=/prometheus",
        "mode_hint": "rootless",
        "probe": {"type": "httpGet", "http_path": "/-/healthy", "http_port": 9090, "initial_delay": 15, "period": 15},
    },
    "influxdb": {
        "ports": "8086:8086",
        "env": "DOCKER_INFLUXDB_INIT_MODE=setup\nDOCKER_INFLUXDB_INIT_USERNAME=admin\nDOCKER_INFLUXDB_INIT_PASSWORD=changeme\nDOCKER_INFLUXDB_INIT_ORG=myorg\nDOCKER_INFLUXDB_INIT_BUCKET=mybucket",
        "volumes": "influxdb-data:/var/lib/influxdb2:Z\ninfluxdb-config:/etc/influxdb2:Z",
        "mode_hint": "rootless",
        "probe": {"type": "httpGet", "http_path": "/health", "http_port": 8086, "initial_delay": 20, "period": 15},
    },
    "keycloak": {
        "ports": "8080:8080",
        "env": "KEYCLOAK_ADMIN=admin\nKEYCLOAK_ADMIN_PASSWORD=changeme\nKC_DB=dev-file",
        "command": "start-dev",
        "mode_hint": "rootless",
        "note": "dev-file nur zum Testen. Produktiv: externe DB.",
    },
    "home-assistant": {
        "ports": "8123:8123",
        "volumes": "homeassistant-config:/config:Z",
        "host_network": True,
        "mode_hint": "rootful",
        "note": "hostNetwork empfohlen für mDNS/Zigbee-Erkennung.",
    },
    "pihole": {
        "ports": "53:53\n8080:80",
        "env": "WEBPASSWORD=changeme\nTZ=Europe/Vienna",
        "volumes": "pihole-etc:/etc/pihole:Z\npihole-dnsmasq:/etc/dnsmasq.d:Z",
        "mode_hint": "rootful",
        "note": "Port 53 → rootful. DNS-Server braucht privilegierten Port.",
    },
    "uptime-kuma": {
        "ports": "3001:3001",
        "volumes": "uptime-kuma-data:/app/data:Z",
        "mode_hint": "rootless",
    },
    "semaphore": {
        "ports": "3000:3000",
        "env": "SEMAPHORE_DB_DIALECT=bolt\nSEMAPHORE_ADMIN=admin\nSEMAPHORE_ADMIN_PASSWORD=changeme\nSEMAPHORE_ADMIN_EMAIL=admin@example.com",
        "volumes": "semaphore-data:/var/lib/semaphore:Z\nsemaphore-config:/etc/semaphore:Z",
        "mode_hint": "rootless",
    },
    "minio": {
        "ports": "9000:9000\n9001:9001",
        "env": "MINIO_ROOT_USER=admin\nMINIO_ROOT_PASSWORD=changeme",
        "volumes": "minio-data:/data:Z",
        "command": "server /data --console-address :9001",
        "mode_hint": "rootless",
    },
    "zabbix-server": {
        "ports": "10051:10051",
        "env": "DB_SERVER_HOST=127.0.0.1\nPOSTGRES_USER=zabbix\nPOSTGRES_PASSWORD=changeme\nPOSTGRES_DB=zabbix",
        "mode_hint": "rootless",
    },
    "zabbix-server-mysql": {
        "ports": "10051:10051",
        "env": "DB_SERVER_HOST=127.0.0.1\nMYSQL_USER=zabbix\nMYSQL_PASSWORD=changeme\nMYSQL_DATABASE=zabbix",
        "mode_hint": "rootless",
    },
    "zabbix-server-pgsql": {
        "ports": "10051:10051",
        "env": "DB_SERVER_HOST=127.0.0.1\nPOSTGRES_USER=zabbix\nPOSTGRES_PASSWORD=changeme\nPOSTGRES_DB=zabbix",
        "mode_hint": "rootless",
    },
    "zabbix-web-nginx-pgsql": {
        "ports": "8080:8080",
        "env": "ZBX_SERVER_HOST=127.0.0.1\nPOSTGRES_USER=zabbix\nPOSTGRES_PASSWORD=changeme\nPOSTGRES_DB=zabbix\nPHP_TZ=Europe/Vienna",
        "mode_hint": "rootless",
    },
    "zabbix-proxy-mysql": {
        "ports": "10051:10051",
        "env": "ZBX_SERVER_HOST=changeme\nZBX_HOSTNAME=proxy-hostname\nZBX_PROXYMODE=0\nZBX_DB_HOST=127.0.0.1\nZBX_DB_USER=zabbix\nZBX_DB_PASSWORD=changeme\nZBX_DB_NAME=zabbix_proxy",
        "mode_hint": "rootless",
        "note": "ZBX_PROXYMODE=0 = aktiver Proxy. ZBX_SERVER_HOST = Zabbix-Server-IP. ZBX_DB_* muss mit MySQL-Container übereinstimmen.",
    },
    "zabbix-proxy-pgsql": {
        "ports": "10051:10051",
        "env": "ZBX_SERVER_HOST=changeme\nZBX_HOSTNAME=proxy-hostname\nZBX_PROXYMODE=0\nDB_SERVER_HOST=127.0.0.1\nPOSTGRES_USER=zabbix\nPOSTGRES_PASSWORD=changeme\nPOSTGRES_DB=zabbix_proxy",
        "mode_hint": "rootless",
        "note": "ZBX_PROXYMODE=0 = aktiver Proxy. ZBX_SERVER_HOST = Zabbix-Server-IP.",
    },
    "zabbix-agent2": {
        "ports": "10050:10050",
        "env": "ZBX_SERVER_HOST=changeme\nZBX_HOSTNAME=changeme",
        "volumes": "zabbix-agent2-config:/etc/zabbix:Z",
        "mode_hint": "rootless",
    },
    "audiobookshelf": {
        "ports": "13378:80",
        "env": "TZ=Europe/Vienna",
        "volumes": "audiobookshelf-config:/config:Z\naudiobookshelf-metadata:/metadata:Z\naudiobooks:/audiobooks:ro\npodcasts:/podcasts:ro",
        "mode_hint": "rootless",
        "note": "Volumes audiobooks/podcasts zeigen auf Medienbibliothek.",
    },
    "nginx-proxy-manager": {
        "ports": "80:80\n443:443\n81:81",
        "volumes": "nginx-proxy-manager-data:/data:Z\nnginx-proxy-manager-letsencrypt:/etc/letsencrypt:Z",
        "mode_hint": "rootful",
        "note": "Admin-UI: Port 81. Standard-Login: admin@example.com / changeme.",
    },
    "zoraxy": {
        "ports": "80:80\n443:443\n8000:8000",
        "volumes": "zoraxy-config:/opt/zoraxy/config:Z",
        "mode_hint": "rootful",
        "note": "Management-UI: Port 8000. Ports 80/443 benötigen rootful.",
    },
    "wg-easy": {
        "ports": "51820:51820\n51821:51821",
        "env": "WG_HOST=changeme\nPASSWORD_HASH=changeme\nWG_DEFAULT_DNS=1.1.1.1\nWG_ALLOWED_IPS=0.0.0.0/0",
        "volumes": "wg-easy-data:/etc/wireguard:Z",
        "cap_add": "NET_ADMIN\nSYS_MODULE",
        "mode_hint": "rootful",
        "note": "WG_HOST = öffentliche IP/Domain. PASSWORD_HASH = bcrypt-Hash (generieren: podman run --rm ghcr.io/wg-easy/wg-easy wgpw PASSWORT). Port 51820/UDP = WireGuard, 51821/TCP = Web-UI.",
    },
    "headscale": {
        "ports": "8080:8080\n9090:9090",
        "volumes": "headscale-config:/etc/headscale:Z\nheadscale-data:/var/lib/headscale:Z",
        "command": "/ko-app/headscale serve",
        "mode_hint": "rootless",
        "note": "Config-Datei /etc/headscale/config.yaml muss vor dem Start erstellt werden.",
    },
    "stirling-pdf": {
        "ports": "8080:8080",
        "env": "DOCKER_ENABLE_SECURITY=false\nLANGS=de_DE",
        "volumes": "stirling-pdf-tessdata:/usr/share/tessdata:Z\nstirling-pdf-config:/configs:Z",
        "mode_hint": "rootless",
    },
    "changedetection.io": {
        "ports": "5000:5000",
        "volumes": "changedetection-data:/datastore:Z",
        "mode_hint": "rootless",
    },
    "code-server": {
        "ports": "8443:8443",
        "env": "PUID=1000\nPGID=1000\nTZ=Europe/Vienna\nPASSWORD=changeme",
        "volumes": "code-server-config:/config:Z",
        "mode_hint": "rootless",
    },
    "linkding": {
        "ports": "9090:9090",
        "env": "LD_SUPERUSER_NAME=admin\nLD_SUPERUSER_PASSWORD=changeme",
        "volumes": "linkding-data:/etc/linkding/data:Z",
        "mode_hint": "rootless",
    },
    "vikunja": {
        "ports": "3456:3456",
        "env": "VIKUNJA_DATABASE_TYPE=sqlite\nVIKUNJA_SERVICE_JWTSECRET=changeme\nVIKUNJA_SERVICE_FRONTENDURL=http://localhost:3456",
        "volumes": "vikunja-files:/app/vikunja/files:Z",
        "mode_hint": "rootless",
    },
    "photoprism": {
        "ports": "2342:2342",
        "env": "PHOTOPRISM_ADMIN_USER=admin\nPHOTOPRISM_ADMIN_PASSWORD=changeme\nPHOTOPRISM_SITE_URL=http://localhost:2342/",
        "volumes": "photoprism-originals:/photoprism/originals:Z\nphotoprism-storage:/photoprism/storage:Z",
        "mode_hint": "rootless",
    },
    "sonarr": {
        "ports": "8989:8989",
        "env": "PUID=1000\nPGID=1000\nTZ=Europe/Vienna",
        "volumes": "sonarr-config:/config:Z\ntv:/tv\ndownloads:/downloads",
        "mode_hint": "rootless",
    },
    "radarr": {
        "ports": "7878:7878",
        "env": "PUID=1000\nPGID=1000\nTZ=Europe/Vienna",
        "volumes": "radarr-config:/config:Z\nmovies:/movies\ndownloads:/downloads",
        "mode_hint": "rootless",
    },
    "prowlarr": {
        "ports": "9696:9696",
        "env": "PUID=1000\nPGID=1000\nTZ=Europe/Vienna",
        "volumes": "prowlarr-config:/config:Z",
        "mode_hint": "rootless",
    },
    "syncthing": {
        "ports": "8384:8384\n22000:22000",
        "env": "PUID=1000\nPGID=1000\nTZ=Europe/Vienna",
        "volumes": "syncthing-config:/var/syncthing/config:Z\nsyncthing-data:/var/syncthing/data:Z",
        "mode_hint": "rootless",
    },
    "adguardhome": {
        "ports": "53:53\n3000:3000\n80:80",
        "volumes": "adguardhome-work:/opt/adguardhome/work:Z\nadguardhome-conf:/opt/adguardhome/conf:Z",
        "mode_hint": "rootful",
        "note": "Ersteinrichtung über Port 3000. Danach Admin-UI auf Port 80.",
    },
    "loki": {
        "ports": "3100:3100",
        "volumes": "loki-data:/loki:Z\nloki-config:/etc/loki:Z",
        "mode_hint": "rootless",
        "note": "Grafana Loki Log-Aggregation. Config unter /etc/loki/local-config.yaml.",
    },
    "victoria-metrics": {
        "ports": "8428:8428",
        "volumes": "victoria-metrics-data:/victoria-metrics-data:Z",
        "args": "-storageDataPath=/victoria-metrics-data -retentionPeriod=12",
        "mode_hint": "rootless",
        "note": "Prometheus-kompatibler TSDB. UI + API auf Port 8428. retentionPeriod in Monaten.",
    },
    "victoria-logs": {
        "ports": "9428:9428",
        "volumes": "victoria-logs-data:/vlogs-data:Z",
        "args": "-storageDataPath=/vlogs-data",
        "mode_hint": "rootless",
        "note": "VictoriaMetrics Log-Storage. API auf Port 9428.",
    },
    "alloy": {
        "volumes": "alloy-config:/etc/alloy:Z",
        "mode_hint": "rootless",
        "note": "Grafana Alloy Collector. Config unter /etc/alloy/config.alloy. Ports je nach Pipeline (4317 OTLP gRPC, 4318 OTLP HTTP, 12345 UI).",
    },
    "jaeger": {
        "ports": "16686:16686\n4317:4317\n4318:4318",
        "mode_hint": "rootless",
        "note": "UI: 16686, OTLP gRPC: 4317, OTLP HTTP: 4318.",
    },
    "n8n": {
        "ports": "5678:5678",
        "env": "N8N_BASIC_AUTH_ACTIVE=true\nN8N_BASIC_AUTH_USER=admin\nN8N_BASIC_AUTH_PASSWORD=changeme\nN8N_HOST=localhost\nN8N_PROTOCOL=http",
        "volumes": "n8n-data:/home/node/.n8n:Z",
        "run_as_user": 1000,
        "run_as_group": 1000,
        "mode_hint": "rootless",
    },
    "portainer": {
        "ports": "9000:9000\n9443:9443",
        "volumes": "portainer-data:/data:Z",
        "mode_hint": "rootful",
        "note": "Portainer CE. Socket-Zugriff → rootful. UI auf Port 9000 (HTTP) oder 9443 (HTTPS).",
    },
    "planka": {
        "ports": "3333:1337",
        "env": "BASE_URL=http://localhost:3333\nDATABASE_URL=postgresql://planka:changeme@localhost:5432/planka\nSECRET_KEY=changeme",
        "volumes": "planka-avatars:/app/public/user-avatars:Z\nplanka-backgrounds:/app/public/project-background-images:Z\nplanka-attachments:/app/private/attachments:Z",
        "mode_hint": "rootless",
        "note": "Trello-ähnliches Kanban-Board. SECRET_KEY und DB-Passwort unbedingt ändern. Zusammen mit PostgreSQL deployen.",
    },
    "leantime": {
        "ports": "8088:8080",
        "env": "LEAN_DB_HOST=localhost\nLEAN_DB_USER=leantime\nLEAN_DB_PASSWORD=changeme\nLEAN_DB_DATABASE=leantime\nLEAN_APP_URL=http://localhost:8088",
        "volumes": "leantime-userfiles:/var/www/html/userfiles:Z\nleantime-public-userfiles:/var/www/html/public/userfiles:Z",
        "run_as_user": 0,
        "mode_hint": "rootless",
        "note": "Container-Port ist 8080 (nicht 80). runAsUser 0 nötig — nginx schreibt /run/nginx.pid. Zusammen mit MySQL/MariaDB deployen.",
    },
    "umami": {
        "ports": "3000:3000",
        "env": "DATABASE_URL=postgresql://umami:changeme@localhost:5432/umami\nDATABASE_TYPE=postgresql",
        "mode_hint": "rootless",
        "note": "Privacy-fokussierte Web-Analytics. Zusammen mit PostgreSQL deployen.",
    },

    "heimdall": {
        "ports": "8080:80\n8443:443",
        "volumes": "heimdall-config:/config:Z",
        "mode_hint": "rootless",
        "note": "Application dashboard. Admin-UI direkt auf Port 8080.",
    },
    "authentik": {
        "ports": "9000:9000\n9443:9443",
        "env": "AUTHENTIK_REDIS__HOST=localhost\nAUTHENTIK_POSTGRESQL__HOST=localhost\nAUTHENTIK_POSTGRESQL__NAME=authentik\nAUTHENTIK_POSTGRESQL__USER=authentik\nAUTHENTIK_POSTGRESQL__PASSWORD=changeme\nAUTHENTIK_SECRET_KEY=changeme",
        "volumes": "authentik-media:/media:Z\nauthentik-certs:/certs:Z",
        "run_as_user": 1000,
        "mode_hint": "rootless",
        "note": "Server + Worker im selben Container möglich (args: server / worker). SECRET_KEY und DB-Passwort unbedingt ändern. Zusammen mit PostgreSQL + Redis deployen.",
    },

    # ── Immich ────────────────────────────────────────────────────
    "immich-server": {
        "ports": "2283:2283",
        "env": "DB_USERNAME=postgres\nDB_PASSWORD=changeme\nDB_DATABASE_NAME=immich\nDB_HOSTNAME=localhost\nREDIS_HOSTNAME=localhost\nUPLOAD_LOCATION=./library",
        "volumes": "./library:/usr/src/app/upload\n/etc/localtime:/etc/localtime",
        "mode_hint": "rootless",
        "note": "Immich Server. DB_HOSTNAME/REDIS_HOSTNAME = 'localhost' innerhalb eines Pods.",
    },
    "immich-machine-learning": {
        "volumes": "model-cache:/cache",
        "mode_hint": "rootless",
        "note": "Immich Machine Learning. model-cache wird als named volume angelegt.",
    },
}


# Namespace/Name → Preset-Key für Images wo Name allein nicht eindeutig ist
_NAMESPACE_MAP = {
    'vaultwarden/server': 'vaultwarden',
    'linuxserver/nextcloud': 'nextcloud',
    'linuxserver/heimdall': 'heimdall',
    'homeassistant/home-assistant': 'home-assistant',
    'louislam/uptime-kuma': 'uptime-kuma',
    'semaphoreui/semaphore': 'semaphore',
    'minio/minio': 'minio',
    'grafana/grafana': 'grafana',
    'prom/prometheus': 'prometheus',
    'zabbix/zabbix-server-mysql': 'zabbix-server-mysql',
    'zabbix/zabbix-server-pgsql': 'zabbix-server-pgsql',
    'zabbix/zabbix-web-nginx-pgsql': 'zabbix-web-nginx-pgsql',
    'zabbix/zabbix-proxy-mysql': 'zabbix-proxy-mysql',
    'zabbix/zabbix-proxy-pgsql': 'zabbix-proxy-pgsql',
    'zabbix/zabbix-agent2': 'zabbix-agent2',
    'advplyr/audiobookshelf': 'audiobookshelf',
    'jc21/nginx-proxy-manager': 'nginx-proxy-manager',
    'tobychui/zoraxy': 'zoraxy',
    'juanfont/headscale': 'headscale',
    'wg-easy/wg-easy': 'wg-easy',
    'stirlingtools/stirling-pdf': 'stirling-pdf',
    'dgtlmoon/changedetection.io': 'changedetection.io',
    'linuxserver/code-server': 'code-server',
    'sissbruecker/linkding': 'linkding',
    'vikunja/vikunja': 'vikunja',
    'photoprism/photoprism': 'photoprism',
    'linuxserver/sonarr': 'sonarr',
    'linuxserver/radarr': 'radarr',
    'linuxserver/prowlarr': 'prowlarr',
    'syncthing/syncthing': 'syncthing',
    'adguard/adguardhome': 'adguardhome',
    'goauthentik/server': 'authentik',
    'grafana/loki': 'loki',
    'victoriametrics/victoria-metrics': 'victoria-metrics',
    'victoriametrics/victoria-logs': 'victoria-logs',
    'grafana/alloy': 'alloy',
    'jaegertracing/all-in-one': 'jaeger',
    'n8nio/n8n': 'n8n',
    'portainer/portainer-ce': 'portainer',
    'portainer/portainer-ee': 'portainer',
    'immich-app/immich-server': 'immich-server',
    'immich-app/immich-machine-learning': 'immich-machine-learning',
    'plankanban/planka': 'planka',
    'leantime/leantime': 'leantime',
    'umami-software/umami': 'umami',
}


def get_preset(image_full: str) -> dict:
    """
    Gibt Preset zurück oder leeres Dict.
    Sucht nach bekanntem Bildnamen (ohne Registry/Tag).
    String-Aliase (z.B. "mongo": "mongodb") werden aufgelöst.
    Fügt '_preset_name' in das zurückgegebene Dict ein.
    """
    name = image_full.lower()
    for prefix in ('docker.io/library/', 'docker.io/', 'ghcr.io/', 'quay.io/', 'lscr.io/'):
        name = name.replace(prefix, '')
    name = name.split(':')[0]  # Tag entfernen

    def _resolve(key: str) -> dict:
        val = PRESETS.get(key, {})
        if isinstance(val, str):
            resolved_key = val
            val = PRESETS.get(val, {})
        else:
            resolved_key = key
        if val:
            return {**val, '_preset_name': resolved_key}
        return {}

    # Erst namespace/name versuchen (z.B. vaultwarden/server → vaultwarden)
    if name in _NAMESPACE_MAP:
        return _resolve(_NAMESPACE_MAP[name])

    # Dann nur den Image-Namen (letzter Teil)
    short = name.split('/')[-1]
    return _resolve(short)


_SYSTEM_ENV_PREFIXES = ('PATH=', 'HOME=', 'LANG=', 'LC_', 'TERM=', 'HOSTNAME=',
                        'container=', 'GPG_KEY=', 'PYTHON_', 'PYTHONDONTWRITEBYTECODE=',
                        'PYTHONUNBUFFERED=', 'JAVA_', 'GOPATH=', 'GOROOT=', 'GOFIPS=',
                        'NODE_VERSION=', 'YARN_VERSION=', 'npm_',
                        'SSL_CERT_', 'GIT_BUILD_', 'TMPDIR=', 'VENV_PATH=',
                        'POETRY_VIRTUALENVS_', 'build_root=')


def _fetch_registry_config(image_full: str) -> dict:
    """
    Holt den Image-Config-Blob aus der Docker/OCI Registry.
    Gibt das 'config'-Objekt zurück (ExposedPorts, Env, …) oder {}.
    """
    import json
    import urllib.request

    try:
        name = image_full.lower()
        registry = 'registry-1.docker.io'
        auth_service = 'registry.docker.io'
        for prefix in ('docker.io/library/', 'docker.io/'):
            if name.startswith(prefix):
                name = name[len(prefix):]
                break
        if name.startswith('ghcr.io/'):
            registry = 'ghcr.io'
            auth_service = 'ghcr.io'
            name = name[len('ghcr.io/'):]
        elif name.startswith('quay.io/'):
            registry = 'quay.io'
            auth_service = 'quay.io'
            name = name[len('quay.io/'):]
        elif name.startswith('lscr.io/'):
            registry = 'lscr.io'
            auth_service = 'lscr.io'
            name = name[len('lscr.io/'):]

        tag = 'latest'
        if ':' in name:
            name, tag = name.rsplit(':', 1)

        namespace = 'library'
        if '/' in name:
            parts = name.split('/', 1)
            namespace, name = parts[0], parts[1]

        repo = f'{namespace}/{name}'

        if registry == 'ghcr.io':
            token_url = f'https://ghcr.io/token?service=ghcr.io&scope=repository:{repo}:pull'
        elif registry == 'quay.io':
            token_url = f'https://quay.io/v2/auth?service=quay.io&scope=repository:{repo}:pull'
        elif registry == 'lscr.io':
            token_url = f'https://lscr.io/token?service=lscr.io&scope=repository:{repo}:pull'
        else:
            token_url = f'https://auth.docker.io/token?service=registry.docker.io&scope=repository:{repo}:pull'
        with urllib.request.urlopen(token_url, timeout=3) as r:
            token = json.loads(r.read())['token']

        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': (
                'application/vnd.docker.distribution.manifest.v2+json,'
                'application/vnd.oci.image.manifest.v1+json,'
                'application/vnd.docker.distribution.manifest.list.v2+json,'
                'application/vnd.oci.image.index.v1+json'
            ),
        }

        class _NoAuthRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return urllib.request.Request(newurl)

        opener = urllib.request.build_opener(_NoAuthRedirect)

        def _get(url):
            req = urllib.request.Request(url, headers=headers)
            with opener.open(req, timeout=3) as r:
                return json.loads(r.read())

        manifest = _get(f'https://{registry}/v2/{repo}/manifests/{tag}')

        if manifest.get('manifests'):
            chosen = next(
                (m for m in manifest['manifests']
                 if m.get('platform', {}).get('os') == 'linux'
                 and m.get('platform', {}).get('architecture') == 'amd64'),
                manifest['manifests'][0]
            )
            manifest = _get(f'https://{registry}/v2/{repo}/manifests/{chosen["digest"]}')

        config_digest = manifest.get('config', {}).get('digest')
        if not config_digest:
            return {}

        req_blob = urllib.request.Request(
            f'https://{registry}/v2/{repo}/blobs/{config_digest}',
            headers={'Authorization': f'Bearer {token}'}
        )
        with opener.open(req_blob, timeout=3) as r:
            blob = json.loads(r.read())

        return blob.get('config', {})

    except Exception:
        return {}


def fetch_registry_all(image_full: str) -> dict:
    """
    Holt alle relevanten Registry-Daten in einem einzigen Aufruf.
    Gibt dict mit ports, env, run_as_user, volumes zurück.
    """
    cfg = _fetch_registry_config(image_full)
    if not cfg:
        return {}

    # Ports
    ports = list(cfg.get('ExposedPorts', {}).keys())

    # Env (System-Vars rausfiltern)
    env_list = cfg.get('Env', [])
    env_lines = [e for e in env_list
                 if not any(e.startswith(p) for p in _SYSTEM_ENV_PREFIXES)]
    env = '\n'.join(env_lines)

    # User/UID
    user = (cfg.get('User') or '').strip()
    uid_part = user.split(':')[0]
    run_as_user = int(uid_part) if uid_part.isdigit() else None

    # Volumes
    volumes = list((cfg.get('Volumes') or {}).keys())

    return {
        'ports': ports,
        'env': env,
        'run_as_user': run_as_user,
        'volumes': volumes,
    }

