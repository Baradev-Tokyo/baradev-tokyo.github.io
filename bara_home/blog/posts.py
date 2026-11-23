from django.utils.translation import get_language


# Add approved posts newest first. Social links are public post permalinks.
POSTS = {
    "planning-an-online-booking-flow": {
        "social_links": {},
        "en": (
            "Planning an online booking flow",
            "Decide what customers need to see before they book, pay, and receive confirmation.",
            (
                "Start with availability. Write down the time slots customers can book, what capacity means for each slot, and how far in advance customers can reserve.",
                "Decide when payment is due and what happens if a customer needs to reschedule. Make the confirmation email clear about what was booked and how to get help.",
                "Pedal Somewhere brings online booking, Stripe payments, and automated email into one flow for guided cycling tours in Tokyo.",
            ),
        ),
        "ja": (
            "オンライン予約の流れを設計するには",
            "予約・決済・確認メールの各段階で、お客様に必要な情報を整理します。",
            (
                "まずは予約枠を整理しましょう。受付時間、各枠の定員、何日前から予約を受け付けるかを決めます。",
                "支払いのタイミングと日程変更時の対応を決めます。確認メールには予約内容と問い合わせ先を分かりやすく記載しましょう。",
                "東京のサイクリングツアーを提供するPedal Somewhereでは、オンライン予約、Stripe決済、自動メールを一つの流れにまとめています。",
            ),
        ),
    },
}


def localized_post(slug):
    entry = POSTS[slug]
    language = "ja" if get_language() == "ja" else "en"
    title, summary, paragraphs = entry[language]
    return {
        "slug": slug,
        "title": title,
        "summary": summary,
        "paragraphs": paragraphs,
        "social_links": entry["social_links"],
    }
