from django.http import Http404
from django.shortcuts import render

from .posts import POSTS, localized_post


def blog(request):
    return render(request, "bara-updates.html", {
        "posts": [localized_post(slug) for slug in POSTS],
    })


def blog_details(request, slug):
    if slug not in POSTS:
        raise Http404
    return render(request, "bara-update.html", {"post": localized_post(slug)})
