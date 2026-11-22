from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.urls import include, path
from reporting.notifications import delivery_webhook

urlpatterns = [
    path("admin/", admin.site.urls),
    path("ops/", include("operations.urls")),
    path("ops/reporting/delivery-webhook/", delivery_webhook),
]

urlpatterns += i18n_patterns(
    path("", include("home.urls")),
    path("services/", include("services.urls")),
    path("about/", include("about.urls")),
    path("contact/", include("contact.urls")),
    prefix_default_language=False,
)
