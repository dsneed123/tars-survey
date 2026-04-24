import json
import logging
import urllib.error
import urllib.request
from datetime import datetime, timezone

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from django.db.models import Q

from analytics.utils import fire_event
from tasks.models import Task

from .forms import ProjectForm, ProjectSettingsForm
from .models import Project

logger = logging.getLogger(__name__)


def _visible_projects(user):
    """Projects the user owns OR belongs to via a team."""
    return Project.objects.filter(
        Q(owner=user) | Q(team__memberships__user=user) | Q(team__owner=user)
    ).distinct()


def _github_request(path, token=None):
    """Make an authenticated GitHub API GET request. Returns parsed JSON or None on error."""
    url = f"https://api.github.com{path}"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "TARS-Survey/1.0")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        logger.warning("GitHub API HTTP error for %s: %s", path, exc.code)
        return None
    except Exception as exc:
        logger.warning("GitHub API error for %s: %s", path, exc)
        return None


def _parse_gh_date(date_str):
    """Parse a GitHub ISO 8601 date string into a datetime object."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _format_commit(c):
    sha = c.get("sha", "")
    commit_obj = c.get("commit", {})
    author = commit_obj.get("author", {})
    message = (commit_obj.get("message", "") or "").split("\n")[0]
    return {
        "sha": sha,
        "sha_short": sha[:7],
        "message": message,
        "author": author.get("name", ""),
        "date": _parse_gh_date(author.get("date", "")),
        "html_url": c.get("html_url", ""),
    }


def _format_pr(pr):
    return {
        "number": pr.get("number"),
        "title": pr.get("title", ""),
        "url": pr.get("html_url", ""),
        "state": pr.get("state", ""),
        "merged_at": _parse_gh_date(pr.get("merged_at", "")),
        "created_at": _parse_gh_date(pr.get("created_at", "")),
        "head": pr.get("head", {}).get("ref", ""),
    }


@login_required
def project_list(request):
    projects = _visible_projects(request.user).order_by("-created_at")
    return render(request, "projects/project_list.html", {"projects": projects})


@login_required
def project_add(request):
    if request.method == "POST":
        form = ProjectForm(request.POST, user=request.user)
        if form.is_valid():
            project = form.save(commit=False)
            project.owner = request.user
            project.save()
            fire_event(
                "project_added",
                user=request.user,
                metadata={"project_id": project.pk, "repo": project.github_repo},
            )
            messages.success(request, f'Project "{project.name}" added successfully.')
            return redirect("projects:detail", pk=project.pk)
    else:
        initial = {}
        team_slug = request.GET.get("team")
        if team_slug:
            from teams.models import Team
            try:
                team = Team.objects.get(slug=team_slug)
                if team.is_member(request.user):
                    initial["team"] = team
            except Team.DoesNotExist:
                pass
        form = ProjectForm(user=request.user, initial=initial)
    return render(request, "projects/project_add.html", {"form": form})


@login_required
def project_detail(request, pk):
    project = get_object_or_404(_visible_projects(request.user), pk=pk)
    token = getattr(settings, "GITHUB_TOKEN", "")

    commits = []
    tars_branches = []
    open_prs = []
    merged_prs = []
    github_available = False

    if project.github_repo:
        repo = project.github_repo
        branch = project.default_branch or "main"

        raw_commits = _github_request(
            f"/repos/{repo}/commits?sha={branch}&per_page=20", token
        )
        if isinstance(raw_commits, list):
            github_available = True
            commits = [_format_commit(c) for c in raw_commits]

        raw_branches = _github_request(f"/repos/{repo}/branches?per_page=100", token)
        if isinstance(raw_branches, list):
            for b in raw_branches:
                name = b.get("name", "")
                if name.startswith("tars/"):
                    tars_branches.append({
                        "name": name,
                        "sha_short": (b.get("commit", {}).get("sha", "") or "")[:7],
                        "url": f"https://github.com/{repo}/tree/{name}",
                    })

        raw_open_prs = _github_request(
            f"/repos/{repo}/pulls?state=open&per_page=20", token
        )
        if isinstance(raw_open_prs, list):
            open_prs = [
                _format_pr(pr)
                for pr in raw_open_prs
                if pr.get("head", {}).get("ref", "").startswith("tars/")
            ]

        raw_closed_prs = _github_request(
            f"/repos/{repo}/pulls?state=closed&sort=updated&per_page=20", token
        )
        if isinstance(raw_closed_prs, list):
            merged_prs = [
                _format_pr(pr)
                for pr in raw_closed_prs
                if pr.get("head", {}).get("ref", "").startswith("tars/")
                and pr.get("merged_at")
            ][:5]

    recent_tasks = list(
        Task.objects.filter(project=project).select_related("created_by").order_by("-created_at")[:5]
    )
    open_pr_count = len(open_prs)
    task_count = Task.objects.filter(project=project).count()

    return render(
        request,
        "projects/project_detail.html",
        {
            "project": project,
            "commits": commits,
            "tars_branches": tars_branches,
            "open_prs": open_prs,
            "merged_prs": merged_prs,
            "recent_tasks": recent_tasks,
            "open_pr_count": open_pr_count,
            "task_count": task_count,
            "github_available": github_available,
        },
    )


@login_required
@require_POST
def project_rollback(request, pk):
    """Create a revert task for a given commit SHA."""
    project = get_object_or_404(Project, pk=pk, owner=request.user)
    sha = request.POST.get("sha", "").strip()
    commit_message = request.POST.get("message", "").strip()

    if not sha or len(sha) < 7:
        messages.error(request, "Invalid commit SHA.")
        return redirect("projects:detail", pk=project.pk)

    short_sha = sha[:7]
    title = f"Revert to commit {short_sha}"
    if commit_message:
        description = (
            f"Revert the repository to commit `{sha}`.\n\n"
            f"**Commit message:** {commit_message}\n\n"
            f"Run `git revert` to undo changes introduced after this commit, "
            f"creating a new commit that restores the repository state."
        )
    else:
        description = (
            f"Revert the repository to commit `{sha}`.\n\n"
            f"Run `git revert` to undo changes introduced after this commit, "
            f"creating a new commit that restores the repository state."
        )

    task = Task.objects.create(
        project=project,
        created_by=request.user,
        title=title,
        description=description,
        priority=70,
    )
    _forward_task_to_controller(task)
    messages.success(request, f'Rollback task created: "{title}"')
    return redirect("tasks:detail", pk=task.pk)


@login_required
def project_commit_diff(request, pk, sha):
    """Return JSON with diff details for a single commit."""
    project = get_object_or_404(Project, pk=pk, owner=request.user)
    # Validate sha is hex-only to prevent path injection
    if not sha or not all(c in "0123456789abcdefABCDEF" for c in sha):
        return JsonResponse({"error": "Invalid SHA."}, status=400)

    token = getattr(settings, "GITHUB_TOKEN", "")
    data = _github_request(f"/repos/{project.github_repo}/commits/{sha}", token)
    if not data or not isinstance(data, dict):
        return JsonResponse({"error": "Could not fetch commit data from GitHub."}, status=502)

    commit_obj = data.get("commit", {})
    author = commit_obj.get("author", {})
    files = [
        {
            "filename": f.get("filename", ""),
            "status": f.get("status", ""),
            "additions": f.get("additions", 0),
            "deletions": f.get("deletions", 0),
            "patch": f.get("patch", ""),
        }
        for f in data.get("files", [])
    ]

    return JsonResponse({
        "sha": data.get("sha", ""),
        "message": commit_obj.get("message", ""),
        "author": author.get("name", ""),
        "date": author.get("date", ""),
        "stats": data.get("stats", {}),
        "files": files,
    })


@login_required
def project_settings(request, pk):
    project = get_object_or_404(Project, pk=pk, owner=request.user)
    if request.method == "POST":
        if "delete" in request.POST:
            name = project.name
            project.delete()
            messages.success(request, f'Project "{name}" has been deleted.')
            return redirect("projects:list")
        form = ProjectSettingsForm(request.POST, instance=project, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Project settings saved.")
            return redirect("projects:settings", pk=project.pk)
    else:
        form = ProjectSettingsForm(instance=project, user=request.user)
    return render(
        request,
        "projects/project_settings.html",
        {"project": project, "form": form},
    )


@login_required
@require_POST
def project_detect(request):
    """AJAX: detect GitHub repo metadata from a URL. Returns JSON."""
    from .forms import _parse_github_repo
    raw = request.POST.get("repo_url", "").strip()
    slug = _parse_github_repo(raw)
    if not slug:
        return JsonResponse({"ok": False, "error": "Enter a valid GitHub URL or owner/repo slug."})

    token = getattr(settings, "GITHUB_TOKEN", "")

    # Try with TARS token first (supports private repos the token can access)
    data = None
    tars_has_access = False
    if token:
        data = _github_request(f"/repos/{slug}", token)
        tars_has_access = isinstance(data, dict)

    # Fall back to unauthenticated request (public repos only)
    if not tars_has_access:
        data = _github_request(f"/repos/{slug}")
        if not isinstance(data, dict):
            if token:
                msg = (
                    f'Repository "{slug}" was not found. It may be private and TARS does '
                    f"not have access, or it doesn't exist."
                )
            else:
                msg = (
                    f'Repository "{slug}" not found on GitHub. '
                    f"Make sure it's public or configure a GITHUB_TOKEN."
                )
            return JsonResponse({"ok": False, "error": msg})

    lang = (data.get("language") or "other").lower()
    valid = [c[0] for c in Project.LANGUAGE_CHOICES]
    if lang not in valid:
        lang = "other"

    is_private = bool(data.get("private", False))
    existing = _visible_projects(request.user).filter(github_repo=slug).first()

    return JsonResponse({
        "ok": True,
        "slug": slug,
        "name": data.get("name", slug.split("/")[-1]),
        "language": lang,
        "default_branch": data.get("default_branch", "main"),
        "description": data.get("description", "") or "",
        "is_private": is_private,
        "tars_has_access": tars_has_access,
        "token_configured": bool(token),
        "already_connected": existing is not None,
        "existing_project_id": existing.pk if existing else None,
    })


@login_required
@require_POST
def project_add_chat(request):
    """Create a project from the chat-based simplified one-field flow."""
    github_repo = request.POST.get("github_repo", "").strip()
    name = request.POST.get("name", "").strip()
    language = request.POST.get("language", "other").strip()
    default_branch = request.POST.get("default_branch", "main").strip()
    description = request.POST.get("description", "").strip()
    if not github_repo or not name:
        messages.error(request, "Missing project data.")
        return redirect("members:dashboard")
    if Project.objects.filter(owner=request.user, github_repo=github_repo).exists():
        messages.info(request, f'"{name}" is already connected.')
        return redirect("members:dashboard")
    valid_languages = [c[0] for c in Project.LANGUAGE_CHOICES]
    if language not in valid_languages:
        language = "other"
    project = Project.objects.create(
        owner=request.user,
        github_repo=github_repo,
        name=name,
        language=language,
        default_branch=default_branch or "main",
        description=description,
    )
    fire_event(
        "project_added",
        user=request.user,
        metadata={"project_id": project.pk, "repo": project.github_repo},
    )
    messages.success(request, f'Connected "{project.name}". Now tell TARS what to build!')
    return redirect("members:dashboard")


def _forward_task_to_controller(task):
    """Send a newly created task to the TARS controller API."""
    import requests as http_requests

    url = getattr(settings, "TARS_CONTROLLER_URL", "")
    api_key = getattr(settings, "TARS_API_KEY", "")
    if not url or not api_key:
        logger.info("TARS_CONTROLLER_URL or TARS_API_KEY not set, skipping forward.")
        return

    payload = {
        "project": task.project.github_repo,
        "task_type": "tars-code",
        "title": task.title,
        "description": task.description,
        "priority": task.priority,
        "user_id": str(task.created_by_id),
        "survey_task_id": task.pk,
    }
    try:
        resp = http_requests.post(
            f"{url.rstrip('/')}/api/tasks",
            json=payload,
            headers={"X-API-Key": api_key},
            timeout=10,
        )
        if resp.ok:
            logger.info(
                "Task %s forwarded to controller: %s",
                task.pk,
                resp.json().get("task", {}).get("id"),
            )
        else:
            logger.warning("Controller rejected task %s: %s", task.pk, resp.text)
    except Exception as exc:
        logger.warning("Failed to forward task %s to controller: %s", task.pk, exc)
