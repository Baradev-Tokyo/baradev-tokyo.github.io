import os
import secrets
import ssl

from django.conf import settings
from django.contrib.staticfiles.handlers import StaticFilesHandler
from django.core.management.base import BaseCommand
from django.core.servers.basehttp import WSGIRequestHandler, WSGIServer, get_internal_wsgi_application


class PrivateRequestHandler(WSGIRequestHandler):
    def get_environ(self):
        environment = super().get_environ()
        environment["HTTPS"] = "on"
        environment["wsgi.url_scheme"] = "https"
        return environment

    def log_request(self, *args, **kwargs):
        # Instagram puts the authorization code in the query string.
        pass


class Command(BaseCommand):
    help = "Serve the owner-only Instagram OAuth flow over HTTPS on this computer."

    def add_arguments(self, parser):
        parser.add_argument("--cert", required=True)
        parser.add_argument("--key", required=True)

    def handle(self, *args, **options):
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.load_cert_chain(options["cert"], options["key"])
        if not os.getenv("DJANGO_SECRET_KEY"):
            settings.SECRET_KEY = secrets.token_urlsafe(48)
        settings.ALLOWED_HOSTS = ["127.0.0.1"]
        settings.SESSION_COOKIE_NAME = "bara_instagram_session"
        settings.SESSION_COOKIE_SECURE = True
        settings.CSRF_COOKIE_SECURE = True
        settings.SECURE_REFERRER_POLICY = "no-referrer"
        application = StaticFilesHandler(get_internal_wsgi_application())
        with WSGIServer(("127.0.0.1", 8443), PrivateRequestHandler, allow_reuse_address=True) as server:
            server.set_app(application)
            server.socket = tls.wrap_socket(server.socket, server_side=True)
            self.stdout.write("Instagram OAuth HTTPS listener ready on 127.0.0.1:8443.")
            server.serve_forever()
