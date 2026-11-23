# Offline screening and catalog drafts

Run from the repository root using the installed Python environment; use an unused folder for each fresh export:

```powershell
.venv/Scripts/python scripts/marketplace_catalog.py dist-marketplace
.venv/Scripts/python scripts/marketplace_catalog.py dist-marketplace --check
.venv/Scripts/python scripts/marketplace_gallery.py dist-marketplace
```

The website package definitions drive the catalog. Category names are candidate mappings; requirements and extras derive from the site workflows. Price ranges are estimates, and exact fixed prices, days and revisions remain unresolved. The validator fails on source scope/range drift, missing rows, duplicate IDs or untraceable deliverables. It lists unapproved tier fields separately. Review native marketplace rules before transferring any draft.

After local migrations, use an existing workspace ID and an owner-provided JSON file. Prefer redacted facts and use only platform-permitted inputs. The command evaluates locally; Add `--save` to persist it. Existing rows with the same workspace, platform and ID remain intact. URLs are references only. In private Django admin, the owner can review opportunities, status, listing IDs, and receipts; the dashboard is at `/admin/bara-operations/`.

```powershell
.venv/Scripts/python bara_home/manage.py import_opportunity 1 docs/marketplace/sample-opportunity.json
```

The provided sample is synthetic. Numeric economics, scope clarity and recurring potential remain unknown unless provided. Default factors are 25/20/15/15/15/10. Set integer weights summing to 100 in a local JSON object using keys technical, budget, clarity, profitability, repeatability, and recurring, then pass `--weights-file`. Unknown evidence reduces confidence and leaves the recommendation for review. Profit is a conservative estimate before owner labor and tax. There is no action pathway to spend Connects, apply or message anyone.

If a trusted llama.cpp CLI and a small quantized GGUF are already installed, run with `--local-model PATH_TO_GGUF`. It receives only the rules’ missing field names and risk categories and returns advisory notes. It receives no download or remote-model options. Measure runtime and memory before relying on it. No model or service was installed. The OpenAI provider is disabled.
