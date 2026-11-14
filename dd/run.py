"""Screen and risk-rate every third party, then write the reports.

    python -m dd                      # uses the live sanctions snapshots on GitHub
    python -m dd --lists path/to/dir  # uses local snapshot CSVs instead
"""

from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path

from .scoring import Assessment, assess
from .screening import Screener, load_lists

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
REPORTS = ROOT / "reports"
README = ROOT / "README.md"

TIER_ORDER = ["Prohibited", "Hold", "High", "Medium", "Low"]
NEEDS_PERSON = {"Prohibited", "Hold", "High"}
SKIP_OWNER = {"", "unknown", "publicly traded"}


def read_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def status_for(a: Assessment, decisions: dict[str, dict]) -> str:
    d = decisions.get(a.id)
    if d:
        return f"{d['decision']} ({d['reviewer']}, {d['decided_on']})"
    if a.tier == "Prohibited":
        return "Blocked: escalate to Legal"
    if a.tier in NEEDS_PERSON:
        return "Awaiting Compliance review"
    if a.tier == "Medium":
        return "Awaiting business-owner sign-off"
    return "Cleared for standard onboarding"


def cleared_for(decision: dict | None) -> set[str]:
    if not decision:
        return set()
    return {c.strip() for c in decision.get("cleared_matches", "").split(";") if c.strip()}


def assess_all(third_parties, country_risk, screener, decisions=None) -> list[Assessment]:
    decisions = decisions or {}
    results = []
    for tp in third_parties:
        names = [tp["name"]] + [o.strip() for o in tp["owners"].split(";")
                                if o.strip().lower() not in SKIP_OWNER]
        hits = [h for n in names for h in screener.screen(n)]
        # A reviewer can clear a specific list entry for a specific third party.
        # Only that entry is cleared; any new or different match still stops onboarding.
        cleared = cleared_for(decisions.get(tp["id"]))
        open_hits = [h for h in hits if f"{h.source} #{h.entry_id}" not in cleared]
        a = assess(tp, country_risk, open_hits)
        for h in hits:
            if h not in open_hits:
                a.reasons.insert(0, f"Cleared match (reviewed): {h.screened_name} vs {h.listed_name} "
                                    f"({h.source} #{h.entry_id})")
        results.append(a)
    return sorted(results, key=lambda a: (TIER_ORDER.index(a.tier), -a.points, a.id))


def summary_table(results, decisions) -> str:
    lines = ["| ID | Third party | Country | Tier | Points | Status |", "|---|---|---|---|---|---|"]
    for a in results:
        lines.append(f"| {a.id} | {a.name} | {a.country} | **{a.tier}** | {a.points} | "
                     f"{status_for(a, decisions)} |")
    return "\n".join(lines)


def full_report(results, decisions, screened_on: str, list_count: int) -> str:
    out = ["# Third-party due diligence report", "",
           f"Screened on {screened_on} against {list_count:,} listed names from the US, UK, "
           "Australian and UN sanctions lists. All third parties are synthetic.", "",
           summary_table(results, decisions), ""]
    for a in results:
        out += [f"## {a.id} · {a.name} ({a.tier})", "",
                f"**Status:** {status_for(a, decisions)}  ", f"**Required review:** {a.required_review}", ""]
        out += [f"- {r}" for r in a.reasons] or ["- No risk factors found"]
        d = decisions.get(a.id)
        if d:
            out += ["", f"**Reviewer rationale:** {d['rationale']}"]
        out.append("")
    return "\n".join(out)


def write_results_csv(results, decisions, path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "country", "tier", "points", "status", "sanctions_hits", "reasons"])
        for a in results:
            w.writerow([a.id, a.name, a.country, a.tier, a.points, status_for(a, decisions),
                        "; ".join(f"{h.listed_name} ({h.source} #{h.entry_id}, {h.score})"
                                  for h in a.sanctions_hits),
                        " | ".join(a.reasons)])


def update_readme(table: str, screened_on: str, path: Path = README) -> None:
    if not path.exists():
        return
    start, end = "<!-- RESULTS:START -->", "<!-- RESULTS:END -->"
    text = path.read_text(encoding="utf-8")
    if start not in text or end not in text:
        return
    head, rest = text.split(start, 1)
    _, tail = rest.split(end, 1)
    body = f"_Last screened {screened_on}._\n\n{table}"
    path.write_text(f"{head}{start}\n{body}\n{end}{tail}", encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lists", type=Path, help="folder of local snapshot CSVs")
    parser.add_argument("--data", type=Path, default=DATA)
    parser.add_argument("--out", type=Path, default=REPORTS)
    parser.add_argument("--readme", type=Path, default=README)
    args = parser.parse_args(argv)

    listed = load_lists(args.lists)
    if not listed:
        print("No sanctions lists loaded; refusing to clear anyone.")
        return 1
    screener = Screener(listed)
    third_parties = read_rows(args.data / "third_parties.csv")
    country_risk = {r["country"]: (r["risk"], r["why"]) for r in read_rows(args.data / "country_risk.csv")}
    decisions = {r["id"]: r for r in read_rows(args.data / "decisions.csv")}

    results = assess_all(third_parties, country_risk, screener, decisions)
    today = date.today().isoformat()
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "dd_report.md").write_text(full_report(results, decisions, today, len(listed)),
                                           encoding="utf-8")
    write_results_csv(results, decisions, args.out / "results.csv")
    update_readme(summary_table(results, decisions), today, args.readme)

    for a in results:
        print(f"{a.id} {a.tier:<10} {a.name}")
    return 0
