from dataclasses import dataclass


@dataclass(frozen=True)
class Package:
    slug: str
    name: str
    low: int
    high: int
    summary: str
    scope: tuple[str, ...]

    @property
    def estimate(self):
        return f"¥{self.low:,}–¥{self.high:,}"


PACKAGES = (
    Package("landing", "Landing page", 100_000, 160_000,
            "Give one service, event, or campaign a clear place to send visitors.",
            ("One responsive page using supplied copy and images",
             "One inquiry or booking link", "Basic search metadata and launch handoff")),
    Package("business-site", "Small business website", 220_000, 380_000,
            "Explain what you offer and help visitors take the next step.",
            ("Up to five responsive pages", "One inquiry form or existing booking integration",
             "Basic search metadata and launch handoff")),
    Package("bilingual-site", "Japanese / English website", 250_000, 500_000,
            "Present the same offer to Japanese- and English-speaking customers.",
            ("One to five page layouts in two languages", "Language switching and localized metadata",
             "Implementation using supplied Japanese and English copy")),
    Package("dashboard", "Operations dashboard", 300_000, 550_000,
            "See the numbers your team uses without assembling reports by hand.",
            ("One existing data source", "Up to three charts and one filterable table",
             "Private access and handoff")),
    Package("automation", "Workflow automation", 180_000, 400_000,
            "Reduce manual copying between the tools your team already uses.",
            ("One defined workflow using up to two systems",
             "Validation and failure reporting", "Optional review step within the agreed scope")),
    Package("internal-tool", "Custom internal tool", 500_000, 950_000,
            "Give a small team a dedicated app for a process it runs every week.",
            ("One core workflow with up to two roles", "Django app with data entry and review screens",
             "Deployment handoff for one environment")),
)

PACKAGE_BY_SLUG = {package.slug: package for package in PACKAGES}
