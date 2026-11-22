"""Customer-facing delivery steps and localized search descriptions."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Step:
    title: tuple[str, str]
    description: tuple[str, str]


@dataclass(frozen=True)
class Workflow:
    description: tuple[str, str]
    steps: tuple[Step, ...]


CONSULT = Step(
    ("Consultation and schedule", "ご相談と制作スケジュール"),
    ("Discuss the audience, goals, required content and target launch date. Agree a schedule with deadlines for client materials, wireframes, design approval and launch.",
     "対象のお客様、制作の目的、掲載内容、公開希望日を確認します。素材の提出、ワイヤーフレームの提示、デザイン承認、公開の各日程を決めます。"),
)
WIREFRAME = Step(
    ("Wireframes and design approval", "ワイヤーフレームとデザインの承認"),
    ("Review the wireframe by the agreed date to confirm page structure and calls to action. Then review and approve the visual design before development begins.",
     "合意した日程までにワイヤーフレームでページ構成や申込みへの導線を確認し、実装前にデザインをご承認いただきます。"),
)
MATERIALS = Step(
    ("Photos, product information and copy", "写真・商品情報・掲載原稿の提出"),
    ("Supply approved photos, product or service details and website copy by the agreed dates. If you want Bara to draft the copy with you, we’ll discuss the work and quote it separately. Late materials may move the launch date. Any late-delivery charges must be agreed in writing beforehand.",
     "合意した期限までに、使用許可を得た写真、商品・サービス情報、掲載原稿をご提出ください。Baraと一緒に原稿を作成する場合は、内容をご相談のうえ別途お見積もりします。素材の提出が遅れると、公開日が変更になる場合があります。遅延に伴う追加費用は、事前に書面で合意した場合に限ります。"),
)
LAUNCH = Step(
    ("Build, review and launch", "実装・最終確認・公開"),
    ("Build from the approved design and materials, test on desktop and mobile, and review together before publishing and handing over the site.",
     "承認済みのデザインと素材をもとに実装し、パソコンとスマートフォンで動作を確認します。最終確認を行ったうえで公開し、運用方法をお伝えします。"),
)

WORKFLOWS = {
    "landing": Workflow(
        ("See Bara’s landing page process, from consultation and wireframes to design approval, content deadlines and launch.",
         "ランディングページ制作の流れをご案内します。初回相談、構成案、デザイン承認、素材の提出、公開までを確認できます。"),
        (CONSULT, WIREFRAME, MATERIALS, LAUNCH),
    ),
    "business-site": Workflow(
        ("Plan a small business website with page design, content deadlines and an optional automated email reply workflow.",
         "小規模事業者向けWebサイトの制作工程をご案内します。ページの設計、原稿の提出、お問い合わせへの自動返信についてご相談いただけます。"),
        (CONSULT, WIREFRAME, MATERIALS, Step(
            ("Inquiry flow and email replies", "お問い合わせとメールの自動返信"),
            ("Decide what happens after a customer submits an inquiry or books. Using the Pedal Somewhere project as an example, we can scope automatic replies, agree who receives notifications, approve the wording and test sending and receipt before launch.",
             "お問い合わせや予約の受付後の流れを決めます。Pedal Somewhereの事例のような自動返信をご希望の場合は、対象となる操作、通知先、文面を確認し、公開前に送受信をテストします。"),
        ), LAUNCH),
    ),
    "bilingual-site": Workflow(
        ("Plan a Japanese and English website with separate copy deadlines, language approvals and bilingual launch checks.",
         "日英対応Webサイトの制作工程です。言語ごとの原稿提出と承認、表示やリンクの確認、公開までの流れをご案内します。"),
        (CONSULT, WIREFRAME, Step(
            ("Japanese and English copy deadlines", "日本語・英語原稿の提出と承認"),
            ("List every page, button, form message and search description that needs copy in both languages. Assign a reviewer and a submission and approval date for each language. Photos and product details have their own deadlines. Drafting, translation or editing can be scoped and quoted separately. Late materials may shift the schedule. Any late-delivery charges must be agreed in writing beforehand.",
             "ページ本文、ボタン、フォームの案内文、検索結果向けの説明文など、日英で必要な原稿を一覧にします。各言語の確認担当者と提出・承認期限を決め、写真や商品情報にも提出期限を設けます。原稿作成、翻訳、編集が必要な場合は、内容をご相談のうえ別途お見積もりします。提出が遅れると日程が変更になる場合があり、遅延に伴う追加費用は事前に書面で合意した場合に限ります。"),
        ), Step(
            ("Review and launch both languages", "両言語の確認と公開"),
            ("Check the language switch, links and forms alongside the approved copy. If automated replies are in scope, approve and test the message and recipient routing in each language. Review both versions on desktop and mobile before sign-off and launch.",
             "承認済みの原稿に沿って、言語切り替え、リンク、フォームを確認します。自動返信を導入する場合は、言語ごとに文面と通知先を承認し、送受信をテストします。パソコンとスマートフォンで両言語版を確認し、承認後に公開します。"),
        )),
    ),
    "dashboard": Workflow(
        ("Plan an operations dashboard with the data owner, agree metric definitions and design, and approve milestones before development.",
         "データ管理者との打ち合わせから、指標の定義、画面設計、日程の承認まで、業務ダッシュボードの開発工程をご案内します。"),
        (Step(
            ("Consultation and decisions", "ご相談と利用目的の確認"),
            ("Identify who will use the dashboard, which decisions it should support, and which metrics need to be visible.",
             "利用者、ダッシュボードを使って判断したいこと、表示が必要な指標を整理します。"),
        ), Step(
            ("Review with the data owner", "データ管理者との確認"),
            ("Meet with the owner of the data source to confirm access permissions, metric definitions, refresh frequency and sample data. Agree how to handle missing or inconsistent records.",
             "データ管理者と、利用権限、指標の定義、更新頻度、サンプルデータを確認します。欠損や不整合があるデータの扱いも決めます。"),
        ), Step(
            ("Design and deadline approval", "画面設計と日程の承認"),
            ("Discuss chart, filter and layout preferences. Review a draft using representative data and approve the design, review dates and delivery deadline.",
             "グラフ、絞り込み、画面構成のご希望を伺います。サンプルデータを使った案を確認し、デザイン、レビュー日、納期を承認します。"),
        ), Step(
            ("Build, reconcile and hand over", "実装・数値の照合・引き継ぎ"),
            ("Connect the agreed source, test permissions, reconcile key figures against the source and show your team how to use the dashboard.",
             "合意したデータソースと連携し、アクセス権限をテストします。主要な数値を元データと照合し、利用方法をお伝えします。"),
        )),
    ),
    "automation": Workflow(
        ("See how Bara scopes automation through a detailed consultation, proposal, requirements review and implementation.",
         "詳しいヒアリングから提案、要件整理、確認、実装へと進む業務自動化の流れをご案内します。"),
        (Step(
            ("In-depth consultation", "詳しいヒアリング"),
            ("Walk through the current workflow with the people who run it. Identify repetitive steps, exceptions, systems and the outcome you want.",
             "実務担当者と現在の手順を確認します。繰り返し作業、例外、利用中のシステム、改善したい点を整理します。"),
        ), Step(
            ("Proposal", "ご提案"),
            ("Review a proposal describing the workflow to automate, expected deliverables, dependencies, timing and price.",
             "自動化の対象、成果物、前提条件、日程、費用をまとめた提案をご確認いただきます。"),
        ), Step(
            ("Requirements gathering and review", "要件整理とレビュー"),
            ("Confirm triggers, inputs, permissions, error handling and any human review steps. Agree on test examples and sign off on what counts as a successful run.",
             "実行条件、入力、権限、エラー時の対応、人による確認の要否を決めます。テスト例を用意し、正常完了の基準を確認します。"),
        ), Step(
            ("Implementation and handoff", "実装・検証・引き継ぎ"),
            ("Build and test the approved workflow with representative cases. Review failures and recovery procedures before rollout and handoff.",
             "承認した要件に沿って実装し、代表的なケースで検証します。本番導入前に、失敗時の対応や復旧手順を確認し、引き継ぎます。"),
        )),
    ),
    "internal-tool": Workflow(
        ("Plan a custom internal tool with workflow discovery, roles, wireframes, acceptance testing and a staged handover.",
         "業務フローの整理、権限設計、画面案、受け入れテスト、引き継ぎまで、業務用Webアプリの開発工程をご案内します。"),
        (Step(
            ("Map the workflow", "業務フローの整理"),
            ("Meet with the owner and daily users to map the process, identify bottlenecks, and decide which workflow the first version should cover.",
             "業務責任者と現場の利用者に話を伺い、現在の手順と課題を整理し、初回リリースで対応する業務を決めます。"),
        ), Step(
            ("Agree the proposal and requirements", "ご提案と要件の合意"),
            ("Agree on scope, milestones and budget. Confirm user roles, permissions, data inputs, exceptions, and any migration or integration tasks.",
             "開発範囲、工程、予算を確認します。利用者の役割、権限、入力データ、例外処理、必要なデータ移行や連携を整理します。"),
        ), Step(
            ("Review wireframes and acceptance criteria", "画面案と受け入れ基準の確認"),
            ("Review wireframes for the main tasks. Agree on test scenarios, review dates and the conditions for sign-off before implementation.",
             "主要な作業画面のワイヤーフレームを確認します。実装前に、テスト項目、レビュー日、承認条件を決めます。"),
        ), Step(
            ("Build, pilot and hand over", "実装・試験運用・引き継ぎ"),
            ("Test with representative data and each user role, run a pilot with the team, address agreed findings, and provide deployment and operating instructions.",
             "代表的なデータと各利用者権限でテストを行い、チームで試験運用します。合意した修正を反映し、導入と運用の手順をお渡しします。"),
        )),
    ),
}
