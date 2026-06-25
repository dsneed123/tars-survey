"""Thin client for the TARS controller API (the Mac Mini / GX10 brain).

The site authenticates to the controller with one shared key, so per-user
separation lives here in Django, not on the controller. The controller is used
only for stateless model work: generate a reply, list models, spin up/down.
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class ControllerError(Exception):
    pass


def _config():
    url = getattr(settings, "TARS_CONTROLLER_URL", "").rstrip("/")
    key = getattr(settings, "TARS_API_KEY", "")
    return url, key


def _request(method, path, timeout=120, **kwargs):
    url, key = _config()
    if not url or not key:
        raise ControllerError("Controller not configured (TARS_CONTROLLER_URL / TARS_API_KEY).")
    try:
        resp = requests.request(
            method, f"{url}{path}",
            headers={"X-API-Key": key, "Content-Type": "application/json"},
            timeout=timeout, **kwargs,
        )
    except requests.RequestException as e:
        raise ControllerError(f"Controller unreachable: {e}")
    if not resp.ok:
        detail = ""
        try:
            detail = resp.json().get("error", "")
        except ValueError:
            detail = resp.text[:200]
        raise ControllerError(detail or f"Controller HTTP {resp.status_code}")
    return resp.json() if resp.content else {}


def generate_reply(messages, model=None):
    """messages: [{role, content}, ...] -> assistant reply string.
    Long timeout: a cold large model (e.g. 70B) can take a while to load+generate."""
    data = _request(
        "POST", "/api/chat/generate",
        json={"messages": messages, "model": model}, timeout=600,
    )
    return data.get("reply", "")


def create_fresh_project(name, design_docs, visibility="private"):
    """Ask the controller to create a NEW GitHub repo and generate a task list
    from design docs. Returns {ok, name, repo, tasks:[{title,description}]}.
    auto_queue=False — the website persists tasks itself (Django) and forwards them."""
    return _request(
        "POST", "/api/projects/fresh",
        json={"name": name, "design_docs": design_docs,
              "visibility": visibility, "auto_queue": False},
        timeout=600,
    )


def discover_tasks(name):
    """Auto-populate: ask the controller to analyze a repo and suggest tasks.
    Returns {ok, tasks:[{title,description}]}. `name` is the repo short name."""
    return _request("POST", f"/api/projects/{name}/discover", timeout=600)


def enable_pages(name):
    """Enable GitHub Pages for the repo. Returns {ok, enabled, url}."""
    return _request("POST", f"/api/projects/{name}/pages", timeout=60)


def go_start(name, description):
    """Launch a TARS Go session. Returns {session_id, status}."""
    return _request(
        "POST", f"/api/projects/{name}/go",
        json={"description": description}, timeout=60,
    )


def go_status(name, session_id):
    """Poll a TARS Go session. Returns the full session state dict."""
    return _request("GET", f"/api/projects/{name}/go/{session_id}", timeout=15)


def list_models():
    return _request("GET", "/api/models", timeout=15)


def load_model(model):
    return _request("POST", "/api/models/load", json={"model": model}, timeout=300)


def unload_model(model):
    return _request("POST", "/api/models/unload", json={"model": model}, timeout=60)
