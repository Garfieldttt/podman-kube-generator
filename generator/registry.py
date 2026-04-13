"""
Registry API – Image-Suche und Tag-Abruf (Docker Hub, ghcr.io, quay.io).
"""
import urllib.request
import urllib.parse
import json
import time
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

# Simple in-memory cache: key → (timestamp, result)
_CACHE: dict = {}
_CACHE_TTL = 3600  # seconds (1h — tags change rarely, avoids Docker Hub rate limits)


def _cache_get(key):
    entry = _CACHE.get(key)
    if entry and time.monotonic() - entry[0] < _CACHE_TTL:
        return entry[1]
    return None


def _cache_set(key, value):
    _CACHE[key] = (time.monotonic(), value)
    # Evict entries older than TTL to prevent unbounded growth
    if len(_CACHE) > 200:
        cutoff = time.monotonic() - _CACHE_TTL
        stale = [k for k, v in _CACHE.items() if v[0] < cutoff]
        for k in stale:
            _CACHE.pop(k, None)


def _search_dockerhub(query, limit=10):
    url = f"https://hub.docker.com/v2/search/repositories/?query={urllib.parse.quote(query)}&page_size={limit}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'podman-kube-gen/1.0'})
        with urllib.request.urlopen(req, timeout=4) as r:
            data = json.loads(r.read())
        results = []
        for item in data.get('results', []):
            ns = item.get('repo_owner') or 'library'
            name = item.get('repo_name', '')
            if '/' in name:
                ns, name = name.split('/', 1)
            full = f"docker.io/{name}" if ns == 'library' else f"docker.io/{ns}/{name}"
            results.append({
                'name': name,
                'namespace': ns,
                'full': full,
                'registry': 'docker.io',
                'official': item.get('is_official', False),
                'description': (item.get('short_description') or '')[:80],
            })
        return results
    except Exception:
        return []


def _search_ghcr(query, limit=5):
    """GitHub Container Registry — uses GitHub API package search."""
    url = f"https://api.github.com/search/repositories?q={urllib.parse.quote(query)}+topic:docker&per_page={limit}"
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'podman-kube-gen/1.0',
            'Accept': 'application/vnd.github+json',
        })
        with urllib.request.urlopen(req, timeout=4) as r:
            data = json.loads(r.read())
        results = []
        for item in data.get('items', []):
            owner = item.get('owner', {}).get('login', '')
            repo  = item.get('name', '')
            if not owner or not repo:
                continue
            full = f"ghcr.io/{owner.lower()}/{repo.lower()}"
            results.append({
                'name': repo.lower(),
                'namespace': owner.lower(),
                'full': full,
                'registry': 'ghcr.io',
                'official': False,
                'description': (item.get('description') or '')[:80],
            })
        return results
    except Exception:
        return []


def _search_quay(query, limit=5):
    url = f"https://quay.io/api/v1/find/repositories?query={urllib.parse.quote(query)}&limit={limit}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'podman-kube-gen/1.0'})
        with urllib.request.urlopen(req, timeout=4) as r:
            data = json.loads(r.read())
        results = []
        for item in data.get('results', []):
            ns   = item.get('namespace', {}).get('name', '') or item.get('namespace', '')
            name = item.get('name', '')
            if isinstance(ns, dict):
                ns = ns.get('name', '')
            if not name:
                continue
            full = f"quay.io/{ns}/{name}" if ns else f"quay.io/{name}"
            results.append({
                'name': name,
                'namespace': ns or 'quay',
                'full': full,
                'registry': 'quay.io',
                'official': False,
                'description': (item.get('description') or '')[:80],
            })
        return results
    except Exception:
        return []


def search_images(query, limit=10, registry='all'):
    """
    registry='hub'  → nur Docker Hub (schnell)
    registry='ext'  → nur ghcr.io + quay.io
    registry='all'  → alle drei parallel
    """
    side_limit = 3
    cache_key = f'{registry}:{query}:{limit}'
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    if registry == 'hub':
        result = _search_dockerhub(query, limit)
        _cache_set(cache_key, result)
        return result

    if registry == 'ext':
        ex = ThreadPoolExecutor(max_workers=2)
        futures = {
            ex.submit(_search_ghcr, query, side_limit): 'ghcr',
            ex.submit(_search_quay, query, side_limit): 'quay',
        }
        done, _ = wait(futures, timeout=5)
        ex.shutdown(wait=False)
        results = {'ghcr': [], 'quay': []}
        for f in done:
            try:
                results[futures[f]] = f.result()
            except Exception:
                pass
        result = results['ghcr'] + results['quay']
        _cache_set(cache_key, result)
        return result

    # all: Hub sofort + ext parallel (wird vom Frontend getrennt aufgerufen)
    hub_limit = max(limit - 4, 6)
    result = _search_dockerhub(query, hub_limit)
    _cache_set(cache_key, result)
    return result


def get_tags(namespace, name, limit=50):
    """
    Gibt Liste der Tag-Strings zurück: ['latest', '1.25', '1.24', ...]
    """
    cache_key = f'tags:{namespace}/{name}'
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    url = f"https://hub.docker.com/v2/repositories/{namespace}/{name}/tags/?page_size={limit}&ordering=last_updated"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'podman-kube-gen/1.0'})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        result = [t['name'] for t in data.get('results', [])]
        _cache_set(cache_key, result)
        return result
    except Exception:
        return []


def get_hub_info(namespace, name):
    """Docker Hub Repository-Metadaten: Beschreibung, Pull-Count, Stars, Official-Flag."""
    cache_key = f'hubinfo:{namespace}/{name}'
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    url = f"https://hub.docker.com/v2/repositories/{namespace}/{name}/"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'podman-kube-gen/1.0'})
        with urllib.request.urlopen(req, timeout=4) as r:
            data = json.loads(r.read())
        result = {
            'description': (data.get('description') or '')[:200],
            'pull_count': data.get('pull_count', 0),
            'star_count': data.get('star_count', 0),
            'is_official': data.get('is_official', False),
            'last_updated': (data.get('last_updated') or '')[:10],
        }
        _cache_set(cache_key, result)
        return result
    except Exception:
        return {}


def get_tag_vulns(namespace, name, tag='latest'):
    """Vulnerability-Counts für einen Tag (nur Docker Hub offizielle Images)."""
    cache_key = f'vulns:{namespace}/{name}:{tag}'
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    url = f"https://hub.docker.com/v2/repositories/{namespace}/{name}/tags/{tag}/"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'podman-kube-gen/1.0'})
        with urllib.request.urlopen(req, timeout=4) as r:
            data = json.loads(r.read())
        vulns = None
        for img in data.get('images', []):
            v = img.get('vulnerabilities')
            if v:
                vulns = v
                break
        result = vulns or {}
        _cache_set(cache_key, result)
        return result
    except Exception:
        return {}
