from urllib.parse import urlsplit

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from operations.stripe_gateway import StripeError, StripeGateway


class Command(BaseCommand):
    help = "Create one-use Stripe Payment Link in an explicitly enabled sandbox."

    def add_arguments(self, parser):
        parser.add_argument("price_id")
        parser.add_argument("request_id", help="Stable identifier for immediate retries.")

    def handle(self, *args, **options):
        if not settings.BARA_STRIPE_SANDBOX_ENABLED:
            raise CommandError("Stripe sandbox is disabled.")
        try:
            result = StripeGateway().test_payment_link(options["price_id"], options["request_id"])
            url = result.get("url")
            if not isinstance(url, str):
                raise StripeError("Missing URL.")
            parsed = urlsplit(url)
            if parsed.scheme != "https" or parsed.netloc != "buy.stripe.com" or not parsed.path.startswith("/test_"):
                raise StripeError("Unexpected test Payment Link URL.")
        except StripeError:
            raise CommandError("Unable to create a Stripe test Payment Link.") from None
        self.stdout.write(url)
