from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.urls import include, path

urlpatterns = [path("admin/", admin.site.urls)]

urlpatterns += i18n_patterns(
    path("", include("home.urls")),
    path("services/", include("services.urls")),
    path("about/", include("about.urls")),
    path("contact/", include("contact.urls")),
    prefix_default_language=False,
)
