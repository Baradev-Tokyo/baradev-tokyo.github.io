from django.contrib.staticfiles import finders
from django.shortcuts import render
from blog.posts import POSTS, localized_post


def home(request):
    portrait_path = "bara/joey.jpg"
    return render(request, "index.html", {
        "portrait": portrait_path if finders.find(portrait_path) else None,
        "latest_post": localized_post(next(iter(POSTS))),
    })


def privacy(request):
    return render(request, "privacy.html")
