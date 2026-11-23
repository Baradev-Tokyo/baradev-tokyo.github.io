from django.utils.translation import get_language, gettext

from .catalog import PACKAGES


DESIGNS = (
    ("natural", ("Natural & clean", "ナチュラルで清潔感のあるデザイン"),
     ("Soft colors, generous spacing, and photography.", "やわらかな色と余白を活かし、写真を引き立てます。"), "album"),
    ("technology", ("Technology-focused", "先進的なテクノロジーデザイン"),
     ("Bold typography and sections that explain how the product works.", "力強い見出しと、製品の仕組みを伝える構成です。"), "product"),
    ("professional", ("Professional", "信頼感のあるビジネスデザイン"),
     ("A clear introduction with structured sections for services and credentials.",
      "サービス内容や実績を整理し、分かりやすく伝えます。"), "heroes"),
)

FEATURES = {
    "landing": (
        ("Contact or quote request", "お問い合わせ・見積もり依頼"),
        ("Booking link", "予約ページへのリンク"),
        ("Email signup", "メールマガジン登録"),
        ("Product or event information", "商品・イベントの案内"),
    ),
    "business-site": (
        ("Contact forms and automatic email replies", "お問い合わせフォーム・自動返信メール"),
        ("Customer reservations, reminders, and cancellations", "お客様向け予約・リマインダー・キャンセル"),
        ("Stripe payments or deposits", "Stripe決済・予約金"),
        ("Blog or news updates", "ブログ・お知らせ更新"),
        ("Service or product catalog", "サービス・商品一覧"),
        ("Customer accounts or member pages", "顧客アカウント・会員ページ"),
        ("Maps, hours, and location pages", "地図・営業時間・店舗案内"),
        ("Newsletter signup and consent", "メールマガジン登録・同意管理"),
        ("Search optimization and analytics", "検索対策・アクセス解析"),
        ("Content editing for staff", "スタッフ向けのコンテンツ編集"),
    ),
    "bilingual-site": (
        ("Japanese and English copy already prepared", "日英両方の原稿を用意済み"),
        ("Help preparing or adapting copy", "原稿作成・ローカライズの相談"),
        ("Localized inquiries and automatic replies", "日英のお問い合わせフォーム・自動返信"),
        ("Localized booking or service pages", "日英の予約・サービス案内"),
    ),
    "dashboard": (
        ("Charts and key metrics", "グラフ・主要指標"),
        ("Filterable tables and spreadsheet export", "絞り込み可能な一覧・データ出力"),
        ("Alerts and scheduled reports", "アラート・定期レポート"),
        ("Role-based access", "役割に応じた閲覧権限"),
        ("Connect a spreadsheet, database, or API", "スプレッドシート・データベース・APIとの連携"),
    ),
    "automation": (
        ("Email, LINE, or Slack notifications", "メール・LINE・Slackへの通知"),
        ("Spreadsheet, CRM, or API synchronization", "スプレッドシート・CRM・API間の同期"),
        ("Form routing and approvals", "フォームの振り分け・承認"),
        ("Invoice or document generation", "請求書・書類の作成"),
        ("File or receipt processing", "ファイル・レシートの処理"),
        ("Scheduled reporting and reconciliation", "定期レポート・データの照合"),
        ("Validation, retries, and error alerts", "入力チェック・再試行・エラー通知"),
    ),
    "internal-tool": (
        ("Employee scheduling and shift swaps", "シフト作成・シフト交換"),
        ("Timesheets and leave requests", "勤怠記録・休暇申請"),
        ("Inventory or equipment tracking", "在庫・機材管理"),
        ("Internal requests and approvals", "社内申請・承認"),
        ("Role-based access and audit history", "権限管理・操作履歴"),
        ("Customer, vendor, or case management", "顧客・取引先・案件管理"),
        ("File uploads and records search", "ファイルの登録・記録の検索"),
        ("Reporting and exports", "レポート・データ出力"),
    ),
}

PROMPTS = {
    "landing": ("What are you promoting? What should visitors do? Do you have copy and photos?",
                "何を紹介し、訪問者にどんな行動を取ってほしいですか？原稿や写真は用意済みですか？"),
    "business-site": ("Describe your business, the pages you need, and any website or tools you use today.",
                      "事業内容、必要なページ、現在お使いのサイトやツールを教えてください。"),
    "bilingual-site": ("Describe the audiences, required pages, and the status of Japanese and English copy.",
                       "対象となるお客様、必要なページ、日英の原稿の準備状況を教えてください。"),
    "dashboard": ("Which data sources, metrics, users, and update frequency do you need?",
                  "データの参照元、確認したい指標、利用者、更新頻度を教えてください。"),
    "automation": ("What starts the workflow? Which tools and manual steps are involved, how often does it run, and what needs human review?",
                   "処理のきっかけ、使用ツール、手作業の手順、実行頻度、人の確認が必要な箇所を教えてください。"),
    "internal-tool": ("Who will use the tool? Describe current steps, records, roles, and approvals.",
                      "利用者と、現在の業務手順、管理するデータ、役割、承認の流れを教えてください。"),
}


def package_briefs():
    language = int(get_language() == "ja")
    designs = [
        (key, name[language], description[language], f"https://getbootstrap.com/docs/5.3/examples/{example}/")
        for key, name, description, example in DESIGNS
    ]
    return [
        {
            "slug": package.slug,
            "name": gettext(package.name),
            "features": [label[language] for label in FEATURES[package.slug]],
            "prompt": PROMPTS[package.slug][language],
            "designs": designs if package.slug in {"landing", "business-site", "bilingual-site"} else [],
        }
        for package in PACKAGES
    ]
