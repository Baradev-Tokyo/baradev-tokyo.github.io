from django.contrib import admin
from django.urls import path

from .views import calendar_view, draft_media

app_name = "content_queue"
urlpatterns = [
    path("", admin.site.admin_view(calendar_view), name="calendar"),
    path("<int:workspace_id>/media/<int:draft_id>/", admin.site.admin_view(draft_media), name="media"),
]
