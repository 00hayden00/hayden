"""Lead scoring: rank prospects by expected payout so the call queue starts with
the money. All weights come from config.json -> scoring; tune freely."""

from datetime import date, datetime


def _days_old(lead_date, fallback_created):
    for raw in (lead_date, fallback_created):
        if not raw:
            continue
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d %H:%M:%S"):
            try:
                return max((date.today() - datetime.strptime(str(raw).strip(), fmt).date()).days, 0)
            except ValueError:
                continue
    return None


def _credit_factor(credit, tiers):
    if not credit:
        return tiers.get("unknown", 0.7)
    raw = str(credit).strip().lower()
    if raw.isdigit():
        fico = int(raw)
        if fico >= 740:
            return tiers.get("excellent", 1.0)
        if fico >= 680:
            return tiers.get("good", 0.9)
        if fico >= 620:
            return tiers.get("fair", 0.7)
        return tiers.get("poor", 0.4)
    return tiers.get(raw, tiers.get("unknown", 0.7))


def score_lead(lead, calls, config):
    """Return 0-100. `lead` is a sqlite Row/dict, `calls` its outcome history."""
    cfg = config.get("scoring", {})
    weights = cfg.get("weights", {})

    # Deal size: loan amount (or a fraction of est. value) vs. a "full marks" cap
    amount = lead["loan_amount"] or (lead["est_value"] or 0) * cfg.get("value_to_loan_ratio", 0.5)
    cap = cfg.get("full_score_loan_amount", 400000)
    amount_component = min(amount / cap, 1.0) if amount else cfg.get("unknown_amount_score", 0.3)

    source_component = cfg.get("source_quality", {}).get(lead["source"], 0.6)

    days = _days_old(lead["lead_date"], lead["created_at"])
    half_life = cfg.get("recency_half_life_days", 14)
    recency_component = 0.5 ** (days / half_life) if days is not None else 0.5

    credit_component = _credit_factor(lead["credit"], cfg.get("credit_tiers", {}))

    score = 100 * (
        weights.get("amount", 0.4) * amount_component
        + weights.get("source", 0.2) * source_component
        + weights.get("recency", 0.25) * recency_component
        + weights.get("credit", 0.15) * credit_component
    )

    # Call history adjustments: callbacks are hot, repeated no-answers go cold
    outcomes = [c["outcome"] for c in calls]
    adjust = cfg.get("outcome_adjustments", {})
    if "callback" in outcomes:
        score += adjust.get("callback", 15)
    if "appointment" in outcomes:
        score += adjust.get("appointment", 20)
    score += adjust.get("per_no_answer", -4) * outcomes.count("no_answer")
    if outcomes and outcomes[-1] in ("dead", "not_interested"):
        score = 0

    return round(max(min(score, 100), 0), 1)


def rescore_all(conn, config):
    leads = conn.execute("SELECT * FROM leads").fetchall()
    for lead in leads:
        calls = conn.execute(
            "SELECT outcome FROM calls WHERE lead_id = ? ORDER BY called_at", (lead["id"],)
        ).fetchall()
        conn.execute(
            "UPDATE leads SET score = ? WHERE id = ?",
            (score_lead(lead, calls, config), lead["id"]),
        )
    conn.commit()
    return len(leads)
