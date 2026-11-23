# Upwork · owner-operated workflow

## Zero-Connects discovery

Rotate search terms across Python, Django, PostgreSQL, Docker, Google Cloud Run, Stripe, REST APIs, booking systems and workflow automation. Favor work that fits Bara's existing services and has a clear deliverable. Candidate search rows are unverified. Before import, read the job details and confirm the account can apply, the proposal has not already been submitted, and the actual application cost is the integer zero. A Connects wallet balance, missing cost, and an invitation without verified application eligibility do not establish a zero-cost application. Check relevant incoming invitations as a separate source and use the invitation-specific flow.

The batch importer accepts only explicitly verified zero-cost jobs. When checking an older record, update the stored cost only from a fresh verified result. The dashboard hides paid and unknown-cost Upwork rows and rejects draft requests for them. Draft approval saves locally. Upwork's proposal preview and explicit submission confirmation are separate steps. Check the live cost again before any submission and leave boosting off.

Run small batches, allow time between searches, and pause when Upwork rate-limits the account. A schedule still requires an authorized runner and a tested delivery path into the local dashboard.

The official server is https://mcp.upwork.com/mcp. Upwork documents OAuth 2.1 for Codex and related MCP clients, opportunity search/details and proposal drafting. This session has no Upwork tool connection; anonymous access returned HTTP 403. The owner can configure it from their own Codex CLI and authenticate in the browser using their existing account:

```powershell
codex mcp add upwork --url https://mcp.upwork.com/mcp
codex mcp login upwork
codex mcp list
```

Review approved permissions and use only supported reads and drafts. Keep the initial workflow manual. The platform still applies its rate limits and Connects rules. Record the stated Connect requirement and hold any unclear or positive cost. Neither discovery nor a draft authorizes a submission or applicant message. Do not copy personal data or confidential content into this repo. [Official Upwork MCP](https://www.upwork.com/ai/mcp) · [MCP rules](https://support.upwork.com/hc/en-us/articles/55446516654611-How-to-use-Upwork-with-AI-agents-through-MCP) · [Codex MCP setup](https://developers.openai.com/learn/docs-mcp)

## Project Catalog

Generate the six local draft records and scope cards with the commands in the [screening guide](opportunity-screening.md). Categories and skills are suggestions to confirm in the marketplace UI. The advertised site prices are JPY planning ranges, so exact USD tier prices, promised days, revisions and any larger tier scope remain owner decisions. Use one tier if the others are unapproved. Review the scope, FAQs, requirements and artwork, then manually create a project in **Find Work → Your services**. Catalog publishing is outside the MCP API. The owner submits only after checking scope, fee, capacity, and media rights. [Project Catalog requirements](https://support.upwork.com/hc/en-us/articles/360057397533-How-to-create-a-project-in-Project-Catalog)

Record actual Upwork fees from the contract and earnings statements. Upwork lists a variable Freelancer Service Fee of 0–15% per contract. Do not estimate the fee as a single universal rate or use Bara Stripe links for those contracts. [Freelancer Service Fee](https://support.upwork.com/hc/en-us/articles/211062538-Learn-about-the-Freelancer-Service-Fee)
