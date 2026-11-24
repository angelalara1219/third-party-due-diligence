# Third-Party Due Diligence

A working example of how I'd run risk-based due diligence on resellers, agencies, consultants and vendors: sanctions screening, anti-bribery red flags, a risk tier, and a clear record of who decided what and why.

## Why I built this

Most bribery and sanctions problems don't come from employees. They come from the third parties acting on a company's behalf: the local reseller with a cousin at the regulator, or the agency that wants its commission paid offshore. Screening a name is only one part of it. The real work is pulling together the ownership, the country, how they get paid, and whether they'll deal with officials, then deciding how much scrutiny each one needs.

This tool does that for a list of third parties and re-screens all of them every weekday, because a third party that was clean at onboarding can be designated next month.

— Angela Lara, CAMS

## Current results

<!-- RESULTS:START -->
_Last screened 2026-11-24._

| ID | Third party | Country | Tier | Points | Status |
|---|---|---|---|---|---|
| TP-006 | Caribe Media Services | Cuba | **Prohibited** | 0 | Blocked: escalate to Legal |
| TP-005 | Greenleaf General Trading LLC | United Arab Emirates | **Hold** | 1 | Awaiting Compliance review |
| TP-002 | Harbour Bridge Media Group | Hong Kong | **High** | 14 | Sanctions match cleared as a false positive; anti-bribery review still open (A. Lara, 2026-11-14) |
| TP-009 | Lagos Public Affairs Associates | Nigeria | **High** | 13 | Awaiting Compliance review |
| TP-008 | Anatolia Digital Reklam | Turkey | **High** | 5 | Awaiting Compliance review |
| TP-003 | Sao Paulo Creative Agency Ltda | Brazil | **Medium** | 4 | Approved with conditions (A. Lara, 2026-11-14) |
| TP-004 | Cloudline Data Services Inc | United States | **Low** | 1 | Cleared for standard onboarding |
| TP-001 | Lion City Ad Partners Pte Ltd | Singapore | **Low** | 0 | Cleared for standard onboarding |
| TP-007 | Dublin Brightwork Consulting | Ireland | **Low** | 0 | Cleared for standard onboarding |
| TP-010 | Sakura Annotation KK | Japan | **Low** | 0 | Cleared for standard onboarding |
<!-- RESULTS:END -->

Full write-up with every reason and reviewer note: [`reports/dd_report.md`](reports/dd_report.md) · Spreadsheet version: [`reports/results.csv`](reports/results.csv)

**All third parties here are synthetic.** One demo company, *Greenleaf General Trading LLC*, was named on purpose to resemble an entity on the OFAC SDN List, to show what a possible match looks like. The reviewer decisions in [`data/decisions.csv`](data/decisions.csv) are illustrative too.

## How a third party gets its tier

| Tier | When | What has to happen |
|---|---|---|
| **Prohibited** | Based in, or paid through, a restricted country | Don't engage. Escalate to Legal. |
| **Hold** | A name or owner possibly matches a sanctions list | Resolve the match first. A person decides; true matches go to Legal. |
| **High** | 5+ risk points | Compliance approval, enhanced due diligence, anti-bribery clauses and audit rights, annual refresh |
| **Medium** | 2–4 risk points | Enhanced questionnaire, business-owner sign-off, anti-bribery clause |
| **Low** | 0–1 risk points | Standard onboarding |

Risk points ([`dd/scoring.py`](dd/scoring.py)):

| Red flag | Points |
|---|---|
| High-risk country / medium-risk country | 3 / 1 |
| Government ties (owner, family member, or former official) | 3 |
| Will deal with government officials for the company | 2 |
| Commission above 15% | 2 |
| Wants payment somewhere other than where it operates | 2 |
| Ownership or government ties not disclosed | 2 |
| Other red flags (offshore account requests, success fees tied to approvals) | 3 |
| Contract of $250,000 or more | 1 |

These weights are example settings to show the method. A real program would set them through its own risk assessment and country risk methodology, and review them regularly. The country ratings in [`data/country_risk.csv`](data/country_risk.csv) are illustrative and should be checked against current sanctions programs before relying on them.

## Sanctions screening

Each third party's name and each listed owner are screened against about 27,000 names from the US (OFAC SDN), UK, Australian and UN sanctions lists. The lists come from my [sanctions-list-tracker](https://github.com/angelalara1219/sanctions-list-tracker), which refreshes them every weekday.

- Names are normalized first: punctuation and legal suffixes like LLC, Ltd and Pte are removed, so "Green Leaf General Trading L.L.C." and "Greenleaf General Trading LLC" are compared fairly.
- Matching uses fuzzy scoring on both word order and spacing. Anything scoring 90 or above goes to a person. Nothing is auto-cleared.
- **False positives are handled like a real analyst would:** the reviewer records the specific list entry they cleared and why (for example, date of birth and nationality don't match). Only that entry is cleared for that third party. A new or different match still stops onboarding. See TP-002 for an example.

## Human review and the audit trail

The tool recommends; people decide. Every Prohibited, Hold and High result shows "Awaiting Compliance review" until a decision is logged in [`data/decisions.csv`](data/decisions.csv) with the reviewer, date and rationale. Because everything lives in Git, every decision and every re-screen has a timestamped history.

## How it runs

```
third_parties.csv ─┐
country_risk.csv ──┼─> scoring + screening ─> reports/ + README table
decisions.csv ─────┘          ▲
sanctions-list-tracker ───────┘   (re-screened every weekday by GitHub Actions)
```

```bash
pip install -r requirements.txt
python -m dd                                  # screen against the live lists
python -m unittest discover -s tests          # tests use small synthetic fixtures
```

## Notes

- Synthetic third parties and decisions only. Nothing comes from any employer, and no real customer or vendor data is used.
- This is a demonstration of method, not legal advice or a production screening system.

## License

MIT
