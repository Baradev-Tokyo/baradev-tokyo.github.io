from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.urls import include, path
from acquisition.views import dashboard, review_opportunity
from content_queue.instagram_oauth import callback as instagram_callback, start as instagram_start
from reporting.notifications import delivery_webhook

urlpatterns = [
    path("oauth/instagram/start/", admin.site.admin_view(instagram_start), name="instagram_oauth_start"),
    path("oauth/instagram/callback/", admin.site.admin_view(instagram_callback), name="instagram_oauth_callback"),
    path("admin/bara-operations/", admin.site.admin_view(dashboard), name="bara_operations"),
    path("admin/bara-operations/content/", include("content_queue.urls")),
    path("admin/bara-operations/<int:workspace_id>/jobs/<int:pk>/",
         admin.site.admin_view(review_opportunity), name="bara_job_review"),
    path("admin/", admin.site.urls),
    path("ops/", include("operations.urls")),
    path("ops/reporting/delivery-webhook/", delivery_webhook),
]

urlpatterns += i18n_patterns(
    path("", include("home.urls")),
    path("services/", include("services.urls")),
    path("about/", include("about.urls")),
    path("contact/", include("contact.urls")),
    path("blog/", include("blog.urls")),
    prefix_default_language=False,
)
