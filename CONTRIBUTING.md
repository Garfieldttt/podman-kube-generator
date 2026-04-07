# Contributing

Contributions are welcome! Here's how to get started.

## Getting started

```bash
git clone git@github.com:Garfieldttt/podman-kube-generator.git
cd podman-kube-generator
bash start.sh
```

This sets up a local dev server at http://127.0.0.1:8000.

## Workflow

1. Fork the repository
2. Create a branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Test locally with `bash start.sh`
5. Open a pull request against `main`

## What to contribute

- Bug fixes
- New community stack templates (`generator/stacks.py`)
- UI improvements
- New Quadlet or Kubernetes YAML features
- Translations

## Stack templates

Templates are defined in `generator/stacks.py`. Each entry follows this structure:

```python
{
    "id": "my-app",
    "name": "My App",
    "description": "Short description",
    "icon": "icon-name",   # Bootstrap Icons name
    "containers": [
        {
            "name": "myapp",
            "image": "myapp:latest",
            "ports": "8080:80",
            "env": "MY_VAR=value",
            "volumes": "/data:/data",
        }
    ],
}
```

Run `python manage.py load_stacks` after changes to import them into the database.

## Code style

- Python: follow existing style, no external linter required
- Templates: Bootstrap 5, htmx for dynamic parts
- Keep changes focused — one feature or fix per PR
