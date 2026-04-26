# Podman Kube Generator

**Podman Kube Generator** is a graphical web-based tool for creating Kubernetes YAML for `podman play kube` and systemd Quadlet files - designed to be approachable for beginners while covering everything advanced users need.

Instead of writing YAML by hand, a visual interface guides you through the full pod configuration. Everything can be adjusted directly in the interface without touching a single line of YAML: image, ports, environment variables, volumes, host paths, CPU and memory limits, GPU access, security context, liveness and readiness probes, restart policy, network settings and more.

Pods can be created in three ways:

- **From a stack template** - pick a pre-configured setup from the built-in library and get a ready-to-run configuration with a single click
- **From scratch** - select any image from Docker Hub, Quay.io, GitHub Container Registry or any other OCI-compatible registry and configure the pod step by step using the visual interface
- **From an existing setup** - import and convert a Docker Compose file, a `podman run` or `docker run` command, or existing pod YAML directly into a new configuration

Environment variable suggestions are fetched automatically from public registries - so you always know which variables an image supports without having to look them up separately. Passwords and secret keys are generated automatically - no default credentials end up in production.

Both rootless and rootful deployments are covered. Once configured, the tool generates a step-by-step deployment guide that walks through everything needed to roll out the pod - from systemd integration via Quadlet to automatic image updates.

Generated configurations can be saved, shared with others via link and organised into collections. A full version history means you can always go back to an earlier state. The community section lets users publish their own stacks, discover what others have built, and rate stacks with likes and comments.

The tool is designed to complement `podman kube play` and Podman Desktop, not replace them. The generator handles the configuration work upfront - the resulting YAML is run directly with `podman kube play` or imported into Podman Desktop.

**Hosted Instance:** https://podman-generator.rzen.at/
<img width="2869" height="1432" alt="image" src="https://github.com/user-attachments/assets/e73cc793-75b9-4f65-a56a-facc37b1a32f" />
<img width="2869" height="1432" alt="image" src="https://github.com/user-attachments/assets/38e08f53-c5a1-40f8-9f8c-14dd744f56bb" />
<img width="2869" height="1432" alt="image" src="https://github.com/user-attachments/assets/b6cdf8de-64e6-47d0-80c9-38d719c2f05b" />



## Features

### Generator
- Generate Kubernetes YAML for `podman play kube`
- Generate Quadlet `.kube` unit with configurable options: AutoUpdate, LogDriver, ExitCodePropagation, KubeDownForce, TimeoutStartSec
- Optional image prune timer: generates companion systemd `.service` + `.timer` units with configurable retention (remove all / keep 7, 14, or 30 days)
- Download `.env` file for secret variables
- Rootless and rootful mode
- Configurable deployment user for rootless mode (used in `useradd`, `loginctl enable-linger`, OpenRC)
- Init containers support
- Host network mode
- Auto-generated secure passwords for `changeme` placeholders
- Validation warnings (privileged ports in rootless mode, weak secrets, etc.)
- Save config as a shareable link (no account required)
- Version history per saved config
- Organize saved configs in collections (requires account)

### Import
- **Docker Compose** → import `docker-compose.yml` / `podman-compose.yml`
- **`docker run` / `podman run`** → paste a run command, get YAML
- **Existing Kubernetes YAML** → re-edit an existing pod YAML in the visual builder

### Visual Pod Builder
- Drag-and-drop canvas for building multi-container pods
- Add, connect and configure containers visually
- Import Compose / run commands directly into the builder

### Image Tools
- Docker Hub image & tag search
- Vulnerability scan info per image tag
- Pre-configured environment variables for 50+ known images (MariaDB, PostgreSQL, Redis, Nextcloud, …)
- Connection hints between containers (which env vars to set for app ↔ database)
- Image inspector: Hub metadata, tags, registry config, CVEs in one view

### Deployment Guide
- Step-by-step deployment guide for rootless and rootful mode (systemd/Quadlet, Alpine/OpenRC, macOS/launchd)
- Config files (`.kube`, prune units) embedded directly in the relevant steps — no scrolling between guide and files
- OS selector (Debian/Ubuntu, Fedora/RHEL, Arch, Alpine, macOS)

### Stack Templates
- 47 ready-to-use templates (WordPress, Nextcloud, Gitea, Vaultwarden, Zabbix, and more)
- DB variant switcher (MariaDB ↔ MySQL ↔ PostgreSQL where supported)
- Auto-replaced passwords on each load — no hardcoded credentials

### Community
- Share your stack publicly (requires account, approved by admin)
- Like and comment on community stacks
- Public user profiles with avatar, bio, website and social links (email is never shown publicly)

### User Accounts
- Registration disabled by default, can be enabled in admin
- Email verification
- TOTP 2FA
- Password reset via email

### Admin
- Full Django admin interface
- SEO, analytics, cookie banner, email, registration settings
- Visitor analytics with bot filtering and IP exclusion
- Stack template management (upload Compose file, icon picker)
- CSV export for visitor stats

> **Note:** This tool generates configuration files only. Pulling container images from Docker Hub may be subject to [Docker's subscription requirements](https://www.docker.com/pricing/) for commercial use.

## Requirements

- Python 3.10+
- pip

## Installation

```bash
git clone https://github.com/Garfieldttt/podman-kube-generator.git
cd podman-kube-generator
bash install.sh
```

`install.sh` handles:
- venv creation & dependency installation
- `.env` setup with generated secret key
- Database migration
- Stack templates import (47 templates included)
- Admin account creation (username + password prompted)
- systemd user service setup on port 9500 (optional)

> **Note:** For the systemd user service to survive logout, `loginctl enable-linger <user>` must be enabled as **root**. `install.sh` prompts for this automatically.

## Configuration

`install.sh` creates `.env` automatically. To adjust settings after installation, edit `.env` in the project directory:

```env
DJANGO_SECRET_KEY=...          # auto-generated by install.sh
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=localhost,your-domain.com
SITE_URL=https://your-domain.com
CSRF_TRUSTED_ORIGINS=https://your-domain.com
ADMIN_URL=admin                # change to obscure the admin URL (default: /admin/)
```

> **HTTPS:** Set `SITE_URL` to `https://...` to enable secure cookies (`SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`). Required when running behind a reverse proxy with TLS.

> **Admin URL:** Set `ADMIN_URL` in `.env` to any path (e.g. `secret-panel`) to move the admin away from `/admin/`.

> **Reverse Proxy:** If running behind Nginx, Caddy or Cloudflare, make sure `CSRF_TRUSTED_ORIGINS` includes your full domain with protocol (e.g. `https://your-domain.com`).

## Update

```bash
bash update.sh
```

Handles package updates, DB migrations, collectstatic and service restart — with automatic rollback on failure.

## Development

```bash
bash start.sh    # starts Django dev server on http://127.0.0.1:8000
bash stop.sh     # stops dev server
```

## Service Management

```bash
systemctl --user status podman-kube-gen.service
systemctl --user restart podman-kube-gen.service
journalctl --user -u podman-kube-gen.service -f
```

> The app runs on port **9500** by default. For these commands to work after logout, `loginctl enable-linger <user>` must be active.

## Nginx Reverse Proxy (optional)

Only needed if you want HTTPS or a custom domain.

```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name your-domain.com;

    # ssl_certificate / ssl_certificate_key here

    location / {
        proxy_pass http://127.0.0.1:9500;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).
