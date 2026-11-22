from django.urls import path
from django.views.generic import RedirectView

from .views import about

urlpatterns = [
    path("", about, name="about"),
    path("about", RedirectView.as_view(pattern_name="about")),
]
