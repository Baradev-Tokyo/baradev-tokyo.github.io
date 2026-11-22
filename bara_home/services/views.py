from django.shortcuts import redirect, render
from django.views.decorators.http import require_safe, require_http_methods

from .catalog import PACKAGES, PACKAGE_BY_SLUG
from .forms import ProjectRequestForm


@require_safe
def services(request, *, static_export=False):
    return render(request, "services.html", {
        "packages": PACKAGES,
        "static_export": static_export,
    })


@require_http_methods(["GET", "HEAD", "POST"])
def intake(request):
    selected_package = PACKAGE_BY_SLUG.get(request.GET.get("package"))
    form = ProjectRequestForm(
        request.POST if request.method == "POST" else None,
        initial={"package": selected_package.slug if selected_package else ""},
    )
    if request.method == "POST" and form.is_valid():
        project = form.save(commit=False)
        package = PACKAGE_BY_SLUG[form.cleaned_data["package"]]
        project.package = package.name
        project.estimate = package.estimate
        scope = "\n".join(f"- {item}" for item in package.scope)
        target = project.target_date.isoformat() if project.target_date else "To be agreed"
        client = project.company or project.name
        project.proposal = (
            f"Project proposal for {client}\n\n"
            f"Package: {project.package}\n\n"
            f"Project brief\n{project.brief}\n\n"
            f"Proposed scope\n{scope}\n\n"
            "Client inputs\nCopy, assets, and access to be confirmed.\n\n"
            "Revisions and exclusions\nTo be agreed.\n\n"
            f"Requested launch date: {target}\n"
            "Milestones and acceptance criteria: To be agreed.\n\n"
            f"Planning estimate (JPY): {project.estimate}\n"
            "Final fee, taxes, third-party costs and payment schedule: To be agreed."
        )
        project.save()
        return redirect("request_received")
    return render(request, "contact.html", {"form": form})


@require_safe
def received(request):
    return render(request, "request_received.html")
