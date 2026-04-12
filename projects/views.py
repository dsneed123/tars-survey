from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ProjectForm, ProjectSettingsForm
from .models import Project


@login_required
def project_list(request):
    projects = Project.objects.filter(owner=request.user)
    return render(request, "projects/project_list.html", {"projects": projects})


@login_required
def project_add(request):
    if request.method == "POST":
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.owner = request.user
            project.save()
            messages.success(request, f'Project "{project.name}" added successfully.')
            return redirect("projects:detail", pk=project.pk)
    else:
        form = ProjectForm()
    return render(request, "projects/project_add.html", {"form": form})


@login_required
def project_detail(request, pk):
    project = get_object_or_404(Project, pk=pk, owner=request.user)
    return render(request, "projects/project_detail.html", {"project": project})


@login_required
def project_settings(request, pk):
    project = get_object_or_404(Project, pk=pk, owner=request.user)
    if request.method == "POST":
        if "delete" in request.POST:
            name = project.name
            project.delete()
            messages.success(request, f'Project "{name}" has been deleted.')
            return redirect("projects:list")
        form = ProjectSettingsForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, "Project settings saved.")
            return redirect("projects:settings", pk=project.pk)
    else:
        form = ProjectSettingsForm(instance=project)
    return render(
        request,
        "projects/project_settings.html",
        {"project": project, "form": form},
    )
