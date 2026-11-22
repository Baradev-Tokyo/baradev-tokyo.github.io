from django.urls import path
from django.views.generic import RedirectView

from . import views

urlpatterns = [
    path("", views.services, name="services"),
    path("services", RedirectView.as_view(pattern_name="services")),
]
