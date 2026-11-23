"""Local bilingual transactional drafts. Rendering does not queue or send mail."""

from .reports import finish

NOTICES = {
    "payment_receipt": (
        ("Payment receipt", "お支払いの領収確認"),
        ("Show only a confirmed payment reference and amount.", "確認済みのお支払い番号と金額のみを表示します。"),
    ),
    "failed_payment": (
        ("Payment needs attention", "お支払いの確認が必要です"),
        ("Review the payment status in your agreed billing channel.", "合意済みのお支払い窓口で決済状況をご確認ください。"),
    ),
    "subscription_confirmation": (
        ("Subscription confirmation", "ご契約プランの確認"),
        ("Review the approved plan, billing period and renewal terms.", "承認済みのプラン、請求期間、更新条件をご確認ください。"),
    ),
    "service_notice": (
        ("Service notice", "サービスに関するお知らせ"),
        ("Use only the approved service impact and schedule.", "承認済みの影響範囲と作業日程のみを記載します。"),
    ),
    "opportunity_alert": (
        ("Internal opportunity review", "社内向け案件確認"),
        ("Owner review is needed. This notice does not submit an application.", "担当者による確認が必要です。この通知で応募は行われません。"),
    ),
    "monthly_summary": (
        ("Monthly business summary", "月次事業サマリー"),
        ("Review the separate marketplace, direct revenue and cost records.", "マーケットプレイス売上、直接取引の売上、原価を分けて確認します。"),
    ),
}


def preview_notice(kind, language):
    index = int(language == "ja")
    title, introduction = NOTICES[kind]
    label = "確認用サンプル" if index else "Review sample"
    note = "サンプル通知です。送信されません。" if index else "Sample notice. No email is sent."
    return finish(language, title[index], introduction[index], label, [], note)
