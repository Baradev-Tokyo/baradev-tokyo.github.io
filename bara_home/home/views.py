from django.contrib.staticfiles import finders
from django.shortcuts import render


def home(request):
    portrait_path = "bara/joey.jpg"
    return render(request, "index.html", {
        "portrait": portrait_path if finders.find(portrait_path) else None,
    })
