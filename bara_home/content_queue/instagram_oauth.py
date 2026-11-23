import json
import os
import secrets
import time
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.middleware.csrf import get_token
from django.utils.html import format_html
from django.views.decorators.http import require_http_methods, require_safe

REDIRECT_URI = "https://127.0.0.1:8443/oauth/instagram/callback/"
SESSION_KEY = "bara_instagram_oauth"
TOKEN_URL = "https://api.instagram.com/oauth/access_token"
PROFILE_URL = "https://graph.instagram.com/me?fields=user_id%2Cusername"


def owner_only(request):
    if not request.user.is_superuser or not request.is_secure():
        raise PermissionDenied


@require_http_methods(["GET", "POST"])
def start(request):
    owner_only(request)
    if request.method == "GET":
        return HttpResponse(format_html(
            '<form method="post"><input type="hidden" name="csrfmiddlewaretoken" value="{}">'
            '<button type="submit">Authorize Bara on Instagram</button></form>', get_token(request),
        ))
    client_id = os.getenv("BARA_INSTAGRAM_APP_ID", "")
    if not client_id.isdecimal() or not os.getenv("BARA_INSTAGRAM_APP_SECRET"):
        return HttpResponse("Configure the Instagram app ID and secret in the private backend.", status=503)
    state = secrets.token_urlsafe(32)
    request.session[SESSION_KEY] = {"value": state, "issued": time.time()}
    query = urlencode({
        "client_id": client_id, "redirect_uri": REDIRECT_URI, "response_type": "code",
        "scope": "instagram_business_basic,instagram_business_content_publishing", "state": state,
        "enable_fb_login": 0,
    })
    return HttpResponseRedirect(f"https://www.instagram.com/oauth/authorize?{query}")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def fetch_json(request):
    with build_opener(NoRedirect()).open(request, timeout=12) as response:
        return json.loads(response.read(65537))


@require_safe
def callback(request):
    owner_only(request)
    if request.method == "HEAD":
        return HttpResponse(status=405)
    grant = request.session.pop(SESSION_KEY, None)
    received = request.GET.get("state", "")
    if (
        not grant or not received.isascii() or not secrets.compare_digest(grant["value"], received)
        or not 0 <= time.time() - grant["issued"] <= 600
    ):
        return HttpResponseBadRequest("No matching authorization. Start again from Bara’s Instagram sign-in page.")
    code = request.GET.get("code", "")
    if not code or len(code) > 4096 or request.GET.get("error"):
        return HttpResponseBadRequest("Instagram authorization was declined or incomplete.")
    client_id = os.getenv("BARA_INSTAGRAM_APP_ID", "")
    client_secret = os.getenv("BARA_INSTAGRAM_APP_SECRET", "")
    if not client_id or not client_secret:
        return HttpResponse("Instagram credentials are not configured.", status=503)
    try:
        payload = urlencode({
            "client_id": client_id, "client_secret": client_secret, "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI, "code": code,
        }).encode("ascii")
        token = fetch_json(Request(TOKEN_URL, data=payload))["access_token"]
        profile = fetch_json(Request(PROFILE_URL, headers={"Authorization": f"Bearer {token}"}))
        username = profile["username"]
    except (OSError, ValueError, KeyError, TypeError):
        return HttpResponse("Instagram didn’t complete the exchange or account check.", status=502)
    if not isinstance(username, str) or username.casefold() != "baradev_tokyo":
        return HttpResponseBadRequest("Sign in with the Bara Instagram account and try again.")
    response = HttpResponse("Verified @baradev_tokyo. This test did not save a publishing token.")
    response["Referrer-Policy"] = "no-referrer"
    return response
