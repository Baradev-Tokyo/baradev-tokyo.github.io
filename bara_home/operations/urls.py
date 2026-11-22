from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health),
    path("billing/checkout/<uuid:order_id>/", views.checkout, name="sandbox_checkout"),
    path("billing/result/", views.result),
    path("billing/webhook/", views.webhook),
]
