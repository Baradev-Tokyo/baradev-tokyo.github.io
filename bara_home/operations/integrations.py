"""Provider ports. Credentials, approvals, and writes belong in future implementations."""

from dataclasses import dataclass
from datetime import date
from typing import Protocol


class ProviderError(Exception):
    def __init__(self, code: str, *, retryable: bool = False, retry_after_seconds: int | None = None):
        super().__init__(code)
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True)
class Connection:
    workspace_id: int
    account_id: str
    credential_ref: str
    scopes: frozenset[str]


@dataclass(frozen=True)
class ApprovedPublication:
    job_id: str
    approval_id: str
    text: str
    media_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class Metric:
    name: str
    value: str
    dimensions: tuple[tuple[str, str], ...] = ()


class Authorization(Protocol):
    def authorization_url(self, state: str, redirect_uri: str, pkce_challenge: str) -> str: ...
    def exchange(self, workspace_id: int, code: str, redirect_uri: str, verifier: str) -> Connection: ...


class Publishing(Protocol):
    def publish(self, connection: Connection, job: ApprovedPublication) -> str:
        """Return the provider ID after validating workspace, approval, and prior attempts."""


class Analytics(Protocol):
    def report(self, connection: Connection, start: date, end: date) -> tuple[Metric, ...]: ...


class XAdapter(Publishing, Analytics, Protocol):
    """Posts and account-level reporting."""


class InstagramAdapter(Publishing, Analytics, Protocol):
    """Eligible media publishing and account insights."""


class LineAdapter(Publishing, Analytics, Protocol):
    """Approved LINE Official Account messaging and delivery reporting."""


@dataclass(frozen=True)
class Review:
    provider_id: str
    rating: int
    text: str


class BusinessProfileAdapter(Publishing, Analytics, Protocol):
    def reviews(self, connection: Connection, cursor: str | None = None) -> tuple[tuple[Review, ...], str | None]: ...
    def reply(self, connection: Connection, review_id: str, job: ApprovedPublication) -> str: ...


class SearchConsoleAdapter(Analytics, Protocol):
    def search_performance(self, connection: Connection, site_url: str, start: date, end: date) -> tuple[Metric, ...]: ...


class AnalyticsDataAdapter(Analytics, Protocol):
    def property_report(self, connection: Connection, property_id: str, start: date, end: date) -> tuple[Metric, ...]: ...
