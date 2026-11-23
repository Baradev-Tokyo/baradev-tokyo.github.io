"""Generate or validate local marketplace draft packages."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bara_home"))

from services.marketplace_catalog import canonical_catalog, draft_catalog, draft_markdown, validate_drafts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.check:
        args.directory.mkdir(parents=True, exist_ok=True)
        items = {"canonical": list(canonical_catalog().values()),
                 **{platform: draft_catalog(platform) for platform in ("upwork", "fiverr")}}
        for name, payload in items.items():
            destination = args.directory / f"{name}.json"
            with destination.open("x", encoding="utf-8") as file:
                file.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
            if name != "canonical":
                with (args.directory / f"{name}.md").open("x", encoding="utf-8") as file:
                    file.write(draft_markdown(payload))
    expected_catalog = list(canonical_catalog().values())
    saved_catalog = json.loads((args.directory / "canonical.json").read_text(encoding="utf-8"))
    errors = [] if saved_catalog == expected_catalog else ["Canonical snapshot changed."]
    for platform in ("upwork", "fiverr"):
        data = json.loads((args.directory / f"{platform}.json").read_text(encoding="utf-8"))
        conflicts, pending = validate_drafts(data, platform)
        errors.extend(conflicts)
        print(f"{platform}: {len(data)} drafts; {len(pending)} tiers await owner decisions.")
    if errors:
        raise SystemExit("\n".join(errors))


if __name__ == "__main__":
    main()
