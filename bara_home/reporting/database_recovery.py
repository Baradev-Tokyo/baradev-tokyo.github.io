"""Recover a confirmed paused Supabase project before scheduled work."""

import json
import re
from time import sleep
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.db import OperationalError


class RecoveryError(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class SupabaseProject:
    def __init__(self, ref, token):
        if not re.fullmatch("[a-z]{20}", ref) or not token:
            raise RecoveryError("Configure a Supabase project ref and Management API token.")
        self.ref = ref
        self.token = token
        self.opener = build_opener(NoRedirect())

    def matches_database(self, database):
        host = database.get("HOST", "").lower()
        user = database.get("USER", "")
        return (
            host == f"db.{self.ref}.supabase.co"
            or (host.endswith(".pooler.supabase.com") and user.endswith(f".{self.ref}"))
        )

    def request(self, suffix="", method="GET"):
        req = Request(
            f"https://api.supabase.com/v1/projects/{self.ref}{suffix}",
            method=method, headers={"Authorization": f"Bearer {self.token}"},
        )
        try:
            with self.opener.open(req, timeout=8) as response:
                if method == "GET":
                    data = json.load(response)
                    if not isinstance(data, dict) or data.get("ref") != self.ref:
                        raise RecoveryError("Supabase returned a different project.")
                    return data.get("status")
        except HTTPError as exc:
            raise RecoveryError(f"Supabase Management API returned HTTP {exc.code}.") from None
        except (OSError, ValueError):
            raise RecoveryError("Supabase Management API request failed.") from None

    def status(self):
        return self.request()

    def resume(self):
        self.request("/restore", "POST")


def probe_database(connection):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return True
    except OperationalError:
        connection.close()
        return False


def ensure_database_ready(connection, project=None, *, auto_resume=False, wait=sleep):
    if project and not project.matches_database(connection.settings_dict):
        raise RecoveryError("Supabase recovery project does not match the configured database.")
    if probe_database(connection):
        return False

    resumed = False
    if project:
        status = project.status()
        if status == "INACTIVE":
            if not auto_resume:
                raise RecoveryError("Supabase project is paused. Resume it in the Dashboard or enable auto-resume.")
            project.resume()
            resumed = True
        elif status not in {"ACTIVE_HEALTHY", "ACTIVE_UNHEALTHY", "RESTORING", "COMING_UP", "RESTARTING"}:
            raise RecoveryError("Supabase project needs owner review before reporting can continue.")

    for delay in (2, 5, 10, 20):
        wait(delay)
        if probe_database(connection):
            return resumed
    raise RecoveryError("PostgreSQL is still unavailable. The reporting job can retry on its next trigger.")
