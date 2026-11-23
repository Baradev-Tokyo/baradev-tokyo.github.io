"""Offline marketplace drafts derived from the website package definitions."""

from .catalog import PACKAGES

CATEGORIES = {
    "landing": ("Web Development", "Website Development", ["landing page", "responsive design", "HTML", "CSS"]),
    "business-site": ("Web Development", "Website Development", ["business website", "web development", "contact form"]),
    "bilingual-site": ("Web Development", "Website Development", ["bilingual website", "Japanese", "English", "localization"]),
    "dashboard": ("Data Visualization", "Data Visualization", ["dashboard", "data visualization", "Python", "Django"]),
    "automation": ("Scripting & Automation", "Software Development", ["automation", "Python", "API integration"]),
    "internal-tool": ("Web Development", "Software Development", ["Django", "Python", "web application", "internal tool"]),
}
REQUIREMENTS = {
    "landing": "Supply approved page copy, images, branding, and the inquiry or booking destination.",
    "business-site": "Supply approved page content, branding, and the intended inquiry or booking workflow.",
    "bilingual-site": "Supply approved Japanese and English copy and identify a reviewer for each language.",
    "dashboard": "Share a redacted sample, the metric definitions, and a point of contact for authorized source access.",
    "automation": "Describe the existing workflow, the systems involved, exceptions, and representative test inputs.",
    "internal-tool": "Identify the workflow owner, user roles, example records and acceptance criteria.",
}
PORTFOLIO = {
    "business-site": "Pedal Somewhere booking case study; permission required before using client media.",
    "dashboard": "Household finance dashboard case study; use synthetic data in any image.",
    "automation": "Receipt workflow case study; use synthetic data in any image.",
    "internal-tool": "Private file sharing case study; omit private screens and customer data.",
}
ADD_ONS = {
    "landing": ["Copywriting, separately quoted after scope review."],
    "business-site": ["Copywriting or automated email replies, scoped and quoted separately."],
    "bilingual-site": ["Drafting, translation or editing, scoped and quoted separately."],
}


def canonical_catalog():
    return {
        package.slug: {
            "id": package.slug, "slug": package.slug, "title": package.name,
            "category": CATEGORIES[package.slug][0],
            "description": package.summary, "target_customer": None,
            "base_price": None, "estimate_low": package.low, "estimate_high": package.high,
            "currency": "JPY", "deliverables": list(package.scope),
            "delivery_days": None, "revisions": None,
            "add_ons": ADD_ONS.get(package.slug, []),
            "requirements": [REQUIREMENTS[package.slug]],
            "recurring_available": None, "active": True,
        } for package in PACKAGES
    }


def draft_catalog(platform):
    if platform not in {"upwork", "fiverr"}:
        raise ValueError("Unknown marketplace.")
    drafts = []
    for slug, canonical in canonical_catalog().items():
        upwork, fiverr, tags = CATEGORIES[slug]
        tiers = ("Starter", "Standard", "Advanced") if platform == "upwork" else ("Basic", "Standard", "Premium")
        title = canonical["title"] if platform == "upwork" else f"I will build your {canonical['title'].lower()}"
        drafts.append({
            "platform": platform, "service_id": slug, "canonical_snapshot": canonical,
            "status": "owner_review_required", "title": title,
            "category_suggestion": "Development & IT" if platform == "upwork" else "Programming & Tech",
            "subcategory_suggestion": upwork if platform == "upwork" else fiverr,
            "skills_and_tags": tags,
            "description": canonical["description"] + " Included scope: " + "; ".join(canonical["deliverables"]) + ".",
            "tiers": [{
                "name": tier, "deliverables": canonical["deliverables"] if index == 0 else None,
                "price": None, "currency": "USD", "delivery_days": None, "revisions": None,
            } for index, tier in enumerate(tiers)],
            "extras": [{"description": extra, "price": None} for extra in canonical["add_ons"]],
            "faq": [
                {"question": "What should I provide before work starts?", "answer": REQUIREMENTS[slug]},
                {"question": "How are changes to the scope handled?",
                 "answer": "Discuss changes in the marketplace order before adding any work or fees."},
            ],
            "buyer_requirements": canonical["requirements"],
            "portfolio": PORTFOLIO.get(slug, "Use the original Bara scope card or an approved work sample."),
            "gallery_asset": f"{slug}.png",
        })
    return drafts


def validate_drafts(drafts, platform):
    canonical = canonical_catalog()
    seen = set()
    errors = []
    pending = []
    for draft in drafts:
        slug = draft.get("service_id")
        if slug not in canonical or slug in seen:
            errors.append(f"{slug}: unknown or duplicate service")
            continue
        seen.add(slug)
        if draft.get("platform") != platform or draft.get("canonical_snapshot") != canonical[slug]:
            errors.append(f"{slug}: marketplace or canonical scope/estimate changed")
        tiers = draft.get("tiers", [])
        if not 1 <= len(tiers) <= 3:
            errors.append(f"{slug}: expected one to three tiers")
        for tier in tiers:
            name = tier.get("name")
            scope = tier.get("deliverables")
            if scope and not set(scope) <= set(canonical[slug]["deliverables"]):
                errors.append(f"{slug}/{name}: untraceable scope")
            price, days, revisions = (tier.get(key) for key in ("price", "delivery_days", "revisions"))
            if tier.get("currency") != "USD" or (price is not None and (
                type(price) is not int or price < 5 or (platform == "upwork" and price > 500_000)
            )):
                errors.append(f"{slug}/{name}: review USD price or marketplace limits")
            if days is not None and (type(days) is not int or days < 1):
                errors.append(f"{slug}/{name}: delivery days must be a positive integer")
            if revisions is not None and (type(revisions) is not int or revisions < (1 if platform == "fiverr" else 0)):
                errors.append(f"{slug}/{name}: review the revision count")
            if not scope or any(tier.get(key) is None for key in ("price", "delivery_days", "revisions")):
                pending.append(f"{slug}/{name}: confirm scope, USD price, delivery and revision terms")
    for slug in sorted(canonical.keys() - seen):
        errors.append(f"{slug}: missing draft")
    return errors, pending


def draft_markdown(drafts):
    lines = [f"# {drafts[0]['platform'].title()} package drafts", "",
             "Owner review required. Confirm categories, USD pricing, timing, revisions and asset rights.", ""]
    for draft in drafts:
        lines.extend([
            f"## {draft['title']}", "",
            f"Canonical service: `{draft['service_id']}`",
            f"Suggested category: {draft['category_suggestion']} / {draft['subcategory_suggestion']}",
            f"Skills and tags: {', '.join(draft['skills_and_tags'])}", "",
            draft["description"], "", "### Tiers", "",
        ])
        for tier in draft["tiers"]:
            scope = "; ".join(tier["deliverables"] or []) or "[Owner to approve the scope]"
            lines.append(f"- **{tier['name']}** · {scope} · [USD price, delivery days and revisions pending]")
        lines.extend(["", "### Buyer requirements", "", *(f"- {item}" for item in draft["buyer_requirements"]), ""])
        if draft["extras"]:
            lines.extend(["### Optional extras", "", *(f"- {item['description']}" for item in draft["extras"]), ""])
        lines.extend(["### FAQs", "", *(f"- **{item['question']}** {item['answer']}" for item in draft["faq"]), "",
                      f"Artwork: `{draft['gallery_asset']}`. {draft['portfolio']}", ""])
    return "\n".join(lines)
