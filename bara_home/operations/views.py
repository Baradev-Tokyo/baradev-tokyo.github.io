from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.http import Http404, HttpResponse, HttpResponseRedirect, UnreadablePostError
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_safe

from .billing import reconcile, start_checkout
from .models import BillingOrder
from .stripe_gateway import InvalidEvent, StripeError, verify_snapshot

owner_required = user_passes_test(lambda user: user.is_active and user.is_superuser, login_url="/admin/login/")


def require_sandbox():
    if not settings.BARA_STRIPE_SANDBOX_ENABLED:
        raise Http404


@owner_required
@require_POST
def checkout(request, order_id):
    require_sandbox()
    try:
        url = start_checkout(order_id)
    except BillingOrder.DoesNotExist as exc:
        raise Http404 from exc
    except StripeError:
        return HttpResponse("Checkout unavailable. Check the order and sandbox settings.", status=503)
    return HttpResponseRedirect(url)


@owner_required
@require_safe
def result(request):
    require_sandbox()
    if request.GET.get("outcome") == "cancelled":
        return HttpResponse("Checkout was left. Check the order in the Django admin.")
    return HttpResponse("Returned from Stripe. Check the confirmed order status in the Django admin.")


@csrf_exempt
@require_POST
def webhook(request):
    require_sandbox()
    try:
        payload = request.body
        event = verify_snapshot(
            payload, request.headers.get("Stripe-Signature", ""), settings.BARA_STRIPE_WEBHOOK_SECRET,
        )
        reconcile(event)
    except (InvalidEvent, UnreadablePostError):
        return HttpResponse(status=400)
    except StripeError:
        return HttpResponse(status=503)
    return HttpResponse(status=204)


@require_safe
def health(request):
    return HttpResponse("ok", content_type="text/plain")
