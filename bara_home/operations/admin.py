from django.conf import settings
from django.contrib import admin

from .models import BillingCustomer, BillingOrder, Invoice, StripeEvent, Subscription, Workspace


@admin.register(BillingOrder)
class BillingOrderAdmin(admin.ModelAdmin):
    change_form_template = "admin/operations/billingorder/change_form.html"
    list_display = ("id", "customer", "kind", "status")
    readonly_fields = (
        "attempt_started", "session_id", "status", "payment_intent_id", "invoice_id", "subscription_id",
    )

    def get_readonly_fields(self, request, obj=None):
        immutable = ("customer", "kind", "stripe_price") if obj else ()
        return (*self.readonly_fields, *immutable)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        order = self.get_object(request, object_id)
        return super().change_view(request, object_id, form_url, {
            **(extra_context or {}),
            "can_start_sandbox": (
                request.user.is_superuser and settings.BARA_STRIPE_SANDBOX_ENABLED
                and order is not None and order.status == "pending"
            ),
        })

    def has_delete_permission(self, request, obj=None):
        return False


class ReadOnlyBillingAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BillingCustomer)
class BillingCustomerAdmin(admin.ModelAdmin):
    list_display = ("label", "workspace", "stripe_id")

    def get_readonly_fields(self, request, obj=None):
        return ("workspace", "stripe_id") if obj else ()


admin.site.register(Workspace)
admin.site.register((Invoice, Subscription, StripeEvent), ReadOnlyBillingAdmin)
