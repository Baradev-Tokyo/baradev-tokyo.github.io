from django.urls import path
from django.views.generic import RedirectView

from services.views import intake, received

urlpatterns = [
    path("", intake, name="contact"),
    path("received/", received, name="request_received"),
    path("contact", RedirectView.as_view(pattern_name="contact", query_string=True)),
]
