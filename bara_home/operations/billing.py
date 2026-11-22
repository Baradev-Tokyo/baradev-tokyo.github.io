from datetime import timedelta
from urllib.parse import urlsplit
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from .models import BillingCustomer, BillingOrder, Invoice, StripeEvent, Subscription
from .stripe_gateway import InvalidEvent, StripeError, StripeGateway

CHECKOUT_EVENTS = {
    "checkout.session.completed",
    "checkout.session.async_payment_succeeded",
    "checkout.session.async_payment_failed",
    "checkout.session.expired",
}
SUBSCRIPTION_EVENTS = {
    "customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted",
}
INVOICE_EVENTS = {
    "invoice.finalized", "invoice.paid", "invoice.payment_succeeded", "invoice.payment_failed",
    "invoice.voided", "invoice.marked_uncollectible",
}


def start_checkout(order_id):
    # Persist the attempt before the network call so an ambiguous result can be retried.
    with transaction.atomic():
        order = BillingOrder.objects.select_for_update().get(pk=order_id)
        if order.status != "pending":
            raise StripeError("Checkout is no longer available for this order.")
        if order.session_id:
            return order.checkout_url
        if order.attempt_started is None:
            order.attempt_started = timezone.now()
            order.save(update_fields=["attempt_started"])
        elif order.attempt_started < timezone.now() - timedelta(hours=23):
            raise StripeError("Review this attempt in Stripe before creating another order.")

    session = StripeGateway().checkout(order)
    url = session.get("url")
    if not isinstance(url, str):
        raise StripeError("Checkout URL is unavailable.")
    parsed_url = urlsplit(url or "")
    if parsed_url.scheme != "https" or parsed_url.netloc != "checkout.stripe.com":
        raise StripeError("Unexpected Checkout URL.")
    if not isinstance(session.get("id"), str) or not session["id"].startswith("cs_test_"):
        raise StripeError("Unexpected Checkout session.")
    with transaction.atomic():
        saved = BillingOrder.objects.select_for_update().get(pk=order_id)
        if saved.session_id and saved.session_id != session["id"]:
            raise StripeError("Conflicting Checkout sessions.")
        saved.session_id = session["id"]
        saved.checkout_url = url
        saved.save(update_fields=["session_id", "checkout_url"])
    return url


@transaction.atomic
def reconcile(event):
    kind = event["type"]
    if kind not in CHECKOUT_EVENTS | SUBSCRIPTION_EVENTS | INVOICE_EVENTS:
        return
    _, created = StripeEvent.objects.get_or_create(stripe_id=event["id"], defaults={"kind": kind})
    if not created:
        return
    data = event.get("data")
    snapshot = data.get("object") if isinstance(data, dict) else None
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("id"), str):
        raise InvalidEvent("Missing event object.")
    customer = BillingCustomer.objects.select_for_update().filter(stripe_id=snapshot.get("customer")).first()
    if customer is None:
        return
    gateway = StripeGateway()
    if kind in CHECKOUT_EVENTS:
        reconcile_checkout(gateway, kind, snapshot, customer)
    elif kind in SUBSCRIPTION_EVENTS:
        current = gateway.retrieve("subscriptions", snapshot["id"])
        if current["customer"] != customer.stripe_id:
            raise InvalidEvent("Wrong subscription customer.")
        Subscription.objects.update_or_create(stripe_id=current["id"], defaults={
            "customer": customer, "status": current["status"],
            "cancel_at_period_end": current["cancel_at_period_end"],
        })
    else:
        current = gateway.retrieve("invoices", snapshot["id"])
        if current["customer"] != customer.stripe_id:
            raise InvalidEvent("Wrong invoice customer.")
        previous = Invoice.objects.filter(stripe_id=current["id"]).first()
        failed = kind == "invoice.payment_failed" or bool(previous and previous.payment_failed)
        Invoice.objects.update_or_create(stripe_id=current["id"], defaults={
            "customer": customer, "status": current["status"], "currency": current["currency"],
            "amount_due": current["amount_due"], "amount_paid": current["amount_paid"],
            "attempt_count": current["attempt_count"],
            "payment_failed": current["status"] == "open" and failed,
            "subscription_id": current.get("subscription") or "",
        })
        from reporting.integrations import sync_verified_stripe_invoice

        sync_verified_stripe_invoice(customer.workspace_id, current)


def reconcile_checkout(gateway, kind, snapshot, customer):
    try:
        order_id = UUID(snapshot.get("client_reference_id") or "")
    except (ValueError, AttributeError):
        return
    order = BillingOrder.objects.select_for_update().filter(pk=order_id, customer=customer).first()
    if order is None or order.attempt_started is None:
        return
    current = gateway.retrieve("checkout/sessions", snapshot["id"])
    expected = (str(order.pk), customer.stripe_id, order.mode)
    if (current["client_reference_id"], current["customer"], current["mode"]) != expected:
        raise InvalidEvent("Checkout details do not match the order.")
    if order.session_id and order.session_id != current["id"]:
        raise InvalidEvent("Wrong Checkout session.")
    order.session_id = current["id"]
    order.invoice_id = current.get("invoice") or ""
    order.subscription_id = current.get("subscription") or ""
    if current["payment_status"] == "paid":
        order.status = "paid"
        order.payment_intent_id = current.get("payment_intent") or ""
    elif order.status != "paid":
        if current["status"] == "expired":
            order.status = "expired"
        elif kind == "checkout.session.async_payment_failed":
            order.status = "failed"
        elif current["status"] == "complete" and order.status != "failed":
            order.status = "awaiting_payment" if order.mode == "payment" else "subscription_started"
    order.save(update_fields=[
        "session_id", "status", "payment_intent_id", "invoice_id", "subscription_id",
    ])
