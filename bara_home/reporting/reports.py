from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from django.template.loader import render_to_string

from .integrations import effective_owners
from .models import BillingPeriod, NotificationTemplate, ReportKind


class ReportError(Exception):
    pass


TITLES = {
    ReportKind.HOSTING_USAGE: ("Hosting usage", "ホスティング利用状況"),
    ReportKind.HOSTING_CHARGES: ("Hosting charges", "ホスティング料金"),
    ReportKind.MARKETING: ("Marketing performance", "マーケティング実績"),
    ReportKind.SOCIAL: ("Social media performance", "SNS運用実績"),
    ReportKind.REVIEWS: ("Business Profile reviews", "ビジネスプロフィールのクチコミ"),
    ReportKind.PAYMENT_REMINDER: ("Payment reminder", "お支払いのご案内"),
    ReportKind.MAINTENANCE: ("Maintenance notice", "メンテナンスのお知らせ"),
    ReportKind.SUSPENSION: ("Suspension notice", "サービス停止のお知らせ"),
}
SUPPORTED = {ReportKind.HOSTING_USAGE, ReportKind.HOSTING_CHARGES}


@dataclass(frozen=True)
class Summary:
    title: str
    text: str
    html: str
    context: dict


def finish(language, title, introduction, period_label, rows, note):
    if not title.strip() or "\r" in title or "\n" in title:
        raise ReportError("invalid_subject")
    context = {
        "language": language, "title": title, "introduction": introduction,
        "period": period_label, "rows": rows, "note": note,
    }
    return Summary(
        title, render_to_string("reporting/report.txt", context).strip(),
        render_to_string("reporting/report.html", context), context,
    )


def render_report(run):
    cfg = run.configuration
    if cfg.kind not in SUPPORTED:
        raise ReportError("report_source_not_ready")
    ja = cfg.language == "ja"
    title = TITLES[cfg.kind][ja]
    custom = NotificationTemplate.objects.filter(
        organization_id=cfg.organization_id, kind=cfg.kind, language=cfg.language
    ).first()
    label = f"{run.period_start.isoformat()} – {run.period_end.isoformat()}"
    label += "（終了日を含まない）" if ja else " (end date excluded)"
    notes = ("このレポートで請求は行われません。", "This report does not create an invoice.")
    if cfg.sample:
        rows = sample_rows(ja, cfg.kind)
        note = ("サンプルデータです。実際の利用状況や請求額ではありません。" if ja
                else "Sample data only. These figures are not actual usage or charges.")
    else:
        rows = actual_rows(run, ja)
        note = notes[not ja]
    return finish(cfg.language, custom.subject if custom else title,
                  custom.introduction if custom else "", label, rows, note)


def sample_rows(ja, kind=ReportKind.HOSTING_CHARGES):
    if kind == ReportKind.HOSTING_USAGE:
        return [
            ("稼働確認の成功率" if ja else "Successful availability checks", "99.5% (199/200)"),
            ("確定済みクラウド原価" if ja else "Finalized cloud cost", "JPY 1,200"),
            ("推定クラウド原価" if ja else "Estimated cloud cost", "JPY 350"),
        ]
    return [
        ("確定済みクラウド原価" if ja else "Finalized cloud cost", "JPY 1,200"),
        ("推定クラウド原価" if ja else "Estimated cloud cost", "JPY 350"),
        ("顧客向け料金（税込）" if ja else "Customer charges including tax", "JPY 3,300"),
        ("Stripe請求額" if ja else "Stripe invoiced", "JPY 3,300"),
        ("入金済み" if ja else "Collected payments", "JPY 2,000"),
        ("未払い残高" if ja else "Outstanding", "JPY 1,300"),
    ]


def money(currency, amount):
    return f"{currency} {amount:,.6f}".rstrip("0").rstrip(".")


def actual_rows(run, ja):
    organization_id = run.configuration.organization_id
    period = BillingPeriod.objects.filter(
        organization_id=organization_id, start=run.period_start, end=run.period_end
    ).first()
    if not period:
        raise ReportError("billing_period_missing")

    costs = defaultdict(Decimal)
    for line in period.usagerecord_set.select_related("ownership").all():
        validate_ownership(line, period)
        costs[line.estimated, line.currency, line.service] += line.cost + line.credits

    rows = []
    for (estimated, currency, service), amount in sorted(costs.items()):
        if estimated:
            label = "推定クラウド原価" if ja else "Estimated cloud cost"
        else:
            label = "確定済みクラウド原価" if ja else "Finalized cloud cost"
        rows.append((f"{label} · {service}", money(currency, amount)))
    if not costs:
        rows.append(("クラウドデータ未取り込み" if ja else "Cloud data not imported", "—"))

    if run.configuration.kind == ReportKind.HOSTING_USAGE:
        measured = defaultdict(lambda: [0, 0])
        for record in period.availabilityrecord_set.select_related("ownership").all():
            validate_ownership(record, period)
            totals = measured[record.ownership_id]
            totals[0] += record.checks
            totals[1] += record.successful_checks
        label = "稼働確認の成功率" if ja else "Successful availability checks"
        rows.extend((label, f"{Decimal(passed) / count:.2%} ({passed}/{count})")
                    for count, passed in measured.values() if count)

    if run.configuration.kind == ReportKind.HOSTING_CHARGES:
        currency = period.billing_currency
        excluded_tax = period.base_charge - period.discount
        if period.finalized:
            rows.extend([
                ("顧客向け料金（税込）" if ja else "Customer charges including tax",
                 money(currency, excluded_tax + period.tax)),
                ("値引き" if ja else "Discount", money(currency, period.discount)),
                ("税額" if ja else "Tax", money(currency, period.tax)),
            ])
        else:
            rows.append(("顧客向け料金は未確定" if ja else "Customer charges pending finalization", "—"))

        totals = defaultdict(lambda: [0, 0, 0])
        for snapshot in period.paymentevent_set.exclude(synchronized_at=None):
            values = totals[snapshot.currency]
            values[0] += snapshot.invoiced_minor
            values[1] += snapshot.collected_minor
            values[2] += snapshot.outstanding_minor
        if not totals:
            rows.append(("Stripe請求データ未確認" if ja else "Stripe invoice data not confirmed", "—"))
        for invoice_currency, values in sorted(totals.items()):
            divisor = {"JPY": 1, "USD": 100, "EUR": 100}.get(invoice_currency)
            if divisor is None:
                raise ReportError("unsupported_invoice_currency")
            for label, value in zip(
                ("Stripe請求額", "入金済み", "未払い残高") if ja else
                ("Stripe invoiced", "Collected payments", "Outstanding"), values, strict=True,
            ):
                rows.append((label, money(invoice_currency, Decimal(value) / divisor)))

        actual_cost = sum(
            amount for (estimated, unit, _), amount in costs.items() if not estimated and unit == currency
        )
        if period.finalized and costs and all(not key[0] and key[1] == currency for key in costs):
            rows.append(("粗利（税・決済手数料を除く）" if ja else "Hosting margin before tax and payment fees",
                         money(currency, excluded_tax - actual_cost)))
    return rows


def validate_ownership(record, period):
    owned = record.ownership
    matches = effective_owners(owned.project_id, owned.resource, record.day)
    if (
        list(matches.values_list("pk", "organization_id")[:2]) != [(owned.pk, period.organization_id)]
        or not period.start <= record.day < period.end
    ):
        raise ReportError("cloud_ownership_invalid")


def render_pdf(summary):
    # Optional private-runtime dependency. A bundled CID font keeps Japanese text as text.
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    ja = summary.context["language"] == "ja"
    font = "HeiseiMin-W3" if ja else "Helvetica"
    if ja:
        pdfmetrics.registerFont(UnicodeCIDFont(font))
    title_style = ParagraphStyle("Title", fontName=font, fontSize=18, leading=25,
                                 wordWrap="CJK" if ja else None)
    body_style = ParagraphStyle("Body", fontName=font, fontSize=11, leading=16,
                                wordWrap="CJK" if ja else None)
    flow = [Paragraph(escape(summary.title), title_style), Spacer(0, 12)]
    for line in summary.text.splitlines()[1:]:
        flow.append(Paragraph(escape(line), body_style) if line else Spacer(0, 7))
    stream = BytesIO()
    SimpleDocTemplate(stream, pagesize=A4).build(flow)
    return stream.getvalue()
