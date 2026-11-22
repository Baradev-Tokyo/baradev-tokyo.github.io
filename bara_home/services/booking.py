"""Validate the public Google Calendar appointment link used by both frontends."""
import re
from urllib.parse import urlsplit

CONSULTATION_HOURS = (
    ("Monday", "月曜日", 12, 20),
    ("Tuesday", "火曜日", None, None),
    ("Wednesday", "水曜日", 15, 20),
    ("Thursday", "木曜日", None, None),
    ("Friday", "金曜日", None, None),
    ("Saturday", "土曜日", None, None),
    ("Sunday", "日曜日", None, None),
)


def consultation_week(japanese):
    return [
        (
            ja if japanese else en,
            f"{start:02d}:00–{end:02d}:00" if start is not None else "",
            start + 1 if start is not None else None,
            end + 1 if end is not None else None,
        )
        for en, ja, start, end in CONSULTATION_HOURS
    ]


def google_booking_url(value):
    if not value:
        return ""
    url = urlsplit(value)
    valid_path = (
        url.netloc == "calendar.app.google" and re.fullmatch(r"/[A-Za-z0-9_-]+/?", url.path)
        or url.netloc == "calendar.google.com" and re.fullmatch(
            r"/calendar/(?:u/\d+/)?appointments/schedules/[A-Za-z0-9_-]+/?", url.path
        )
    )
    if url.scheme != "https" or not valid_path or url.fragment or url.query not in ("", "gv=true"):
        raise ValueError("Set BARA_GOOGLE_BOOKING_URL to the public Google Calendar appointment booking link.")
    return value


def google_booking_embed_url(booking_url):
    url = urlsplit(booking_url)
    if url.netloc != "calendar.google.com":
        return ""
    return url._replace(query="gv=true").geturl()
