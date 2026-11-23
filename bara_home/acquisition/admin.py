from django.contrib import admin

from .models import MarketplaceListing, MarketplaceReceipt, Opportunity
from .screening import RulesProvider


class OwnerAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        current = super().get_readonly_fields(request, obj)
        return (*current, "organization", "source", "external_id") if obj else current


@admin.register(Opportunity)
class OpportunityAdmin(OwnerAdmin):
    list_display = ("title", "organization", "source", "status", "score", "recommendation")
    list_filter = ("organization", "source", "status")

    @admin.display
    def score(self, opportunity):
        return RulesProvider().assess(opportunity)["fit_score"]

    @admin.display
    def recommendation(self, opportunity):
        return RulesProvider().assess(opportunity)["recommendation"]


@admin.register(MarketplaceListing)
class ListingAdmin(OwnerAdmin):
    list_display = ("source", "external_id", "service_slug", "organization")
    list_filter = ("source", "organization")


@admin.register(MarketplaceReceipt)
class ReceiptAdmin(OwnerAdmin):
    list_display = ("source", "external_id", "earned_on", "currency", "gross", "fee", "organization")
    list_filter = ("source", "organization")
