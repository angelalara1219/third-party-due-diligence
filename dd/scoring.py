"""Turn a third party's answers and screening results into a risk tier.

Every rule is written out here so a reviewer can see exactly why a third
party scored the way it did. The weights are example settings, not a
standard; a real program would set them through its own risk assessment.
"""

from __future__ import annotations

from dataclasses import dataclass, field

COMMISSION_FLAG_PCT = 15
LARGE_CONTRACT_USD = 250_000

POINTS = {
    "high_risk_country": 3,
    "medium_risk_country": 1,
    "government_ties": 3,
    "interacts_with_officials": 2,
    "high_commission": 2,
    "payment_elsewhere": 2,
    "other_red_flag": 3,
    "unknown_ownership": 2,
    "large_contract": 1,
}

REQUIRED_REVIEW = {
    "Prohibited": "Do not engage. Escalate to Legal.",
    "Hold": "Resolve the possible sanctions match before anything else. Compliance decides; escalate true matches to Legal.",
    "High": "Compliance approval required. Enhanced due diligence, anti-bribery clauses and audit rights in the contract, Legal review if officials are involved, refresh every year.",
    "Medium": "Enhanced questionnaire and business-owner sign-off. Anti-bribery clause in the contract. Refresh every two years.",
    "Low": "Standard onboarding. Refresh every three years.",
}


@dataclass
class Assessment:
    id: str
    name: str
    country: str
    tier: str
    points: int
    reasons: list[str] = field(default_factory=list)
    sanctions_hits: list = field(default_factory=list)
    required_review: str = ""


def is_yes(value: str) -> bool:
    return value.strip().lower().startswith("yes")


def to_float(value: str) -> float:
    try:
        return float(str(value).replace(",", "").replace("%", "").strip() or 0)
    except ValueError:
        return 0.0


def assess(tp: dict, country_risk: dict[str, tuple[str, str]], hits: list) -> Assessment:
    reasons: list[str] = []
    points = 0

    def add(rule: str, text: str):
        nonlocal points
        points += POINTS[rule]
        reasons.append(f"{text} (+{POINTS[rule]})")

    risk, why = country_risk.get(tp["country"], ("Medium", "Country not on the risk list; treated as Medium until rated"))
    if risk == "Restricted":
        reasons.append(f"{tp['country']} is a restricted country: {why}")
        return Assessment(tp["id"], tp["name"], tp["country"], "Prohibited", 0, reasons, hits,
                          REQUIRED_REVIEW["Prohibited"])
    if risk == "High":
        add("high_risk_country", f"High-risk country: {tp['country']}. {why}")
    elif risk == "Medium":
        add("medium_risk_country", f"Medium-risk country: {tp['country']}. {why}")

    pay_risk = country_risk.get(tp["payment_country"], ("Medium", ""))[0]
    if pay_risk == "Restricted":
        reasons.append(f"Payment routed to a restricted country ({tp['payment_country']})")
        return Assessment(tp["id"], tp["name"], tp["country"], "Prohibited", 0, reasons, hits,
                          REQUIRED_REVIEW["Prohibited"])

    if is_yes(tp["government_ties"]):
        add("government_ties", f"Government ties: {tp['government_ties'][3:].strip(' -') or 'yes'}")
    if is_yes(tp["interacts_with_officials"]):
        add("interacts_with_officials", "Will deal with government officials on the company's behalf")
    if to_float(tp["commission_pct"]) > COMMISSION_FLAG_PCT:
        add("high_commission", f"Commission of {to_float(tp['commission_pct']):g}% is above the "
                               f"{COMMISSION_FLAG_PCT}% review threshold")
    if tp["payment_country"].strip() and tp["payment_country"] != tp["country"]:
        add("payment_elsewhere", f"Wants payment in {tp['payment_country']}, not where it operates "
                                 f"({tp['country']})")
    if tp["owners"].strip().lower() in ("", "unknown") or tp["government_ties"].strip().lower() == "unknown":
        add("unknown_ownership", "Ownership or government ties not disclosed")
    if tp["other_red_flags"].strip():
        add("other_red_flag", f"Red flag: {tp['other_red_flags'].strip()}")
    if to_float(tp["contract_value_usd"]) >= LARGE_CONTRACT_USD:
        add("large_contract", f"Contract value ${to_float(tp['contract_value_usd']):,.0f}")

    if hits:
        reasons.insert(0, "Possible sanctions match: " + "; ".join(
            f"{h.screened_name} vs {h.listed_name} ({h.source} #{h.entry_id}, score {h.score})"
            for h in hits))
        tier = "Hold"
    elif points >= 5:
        tier = "High"
    elif points >= 2:
        tier = "Medium"
    else:
        tier = "Low"
    return Assessment(tp["id"], tp["name"], tp["country"], tier, points, reasons, hits,
                      REQUIRED_REVIEW[tier])
