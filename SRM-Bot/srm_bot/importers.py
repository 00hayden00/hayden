"""CSV importers for lead sources (DemandConversions CRM, AtlasAddress, generic).

Exports never agree on column names, so mapping happens in two layers:
1. Per-source overrides from config.json -> sources.<name>.columns
2. Auto-detection against the SYNONYMS table below

Leads are deduped by normalized phone, then email, then (source, external_id).
Re-importing a daily report updates existing rows instead of duplicating them.
"""

import csv
import re

# canonical field -> lowercase header names commonly seen in exports
SYNONYMS = {
    "external_id": ["id", "lead id", "lead_id", "record id", "guid"],
    "name": ["name", "full name", "borrower", "borrower name", "contact", "owner name"],
    "first_name": ["first", "first name", "fname"],
    "last_name": ["last", "last name", "lname", "surname"],
    "phone": ["phone", "phone number", "cell", "mobile", "home phone", "primary phone", "phone 1"],
    "email": ["email", "email address", "e-mail"],
    "city": ["city", "town"],
    "state": ["state", "st", "province"],
    "loan_amount": ["loan amount", "loan_amount", "mortgage amount", "amount", "balance",
                    "mortgage balance", "loan balance", "requested amount"],
    "est_value": ["est value", "estimated value", "home value", "property value", "avm",
                  "est. value", "value"],
    "credit": ["credit", "credit score", "fico", "credit tier", "credit rating"],
    "age": ["age", "borrower age"],
    "lead_date": ["date", "lead date", "created", "created at", "create date", "record date"],
    "notes": ["notes", "comments", "remarks"],
}


def normalize_phone(raw):
    if not raw:
        return None
    digits = re.sub(r"\D", "", str(raw))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits or None


def parse_money(raw):
    if raw in (None, ""):
        return None
    cleaned = re.sub(r"[^0-9.]", "", str(raw))
    if not cleaned:
        return None
    try:
        value = float(cleaned)
    except ValueError:
        return None
    # "350k" style values
    if "k" in str(raw).lower() and value < 10000:
        value *= 1000
    return value


def build_header_map(headers, source_cfg):
    """Map canonical field -> actual CSV header for this file."""
    lower = {h.strip().lower(): h for h in headers}
    mapping = {}
    for field, override in (source_cfg.get("columns") or {}).items():
        if override.strip().lower() in lower:
            mapping[field] = lower[override.strip().lower()]
    for field, names in SYNONYMS.items():
        if field in mapping:
            continue
        for candidate in names:
            if candidate in lower:
                mapping[field] = lower[candidate]
                break
    return mapping


def row_to_lead(row, header_map, source):
    get = lambda field: (row.get(header_map[field]) or "").strip() if field in header_map else ""
    name = get("name")
    if not name:
        name = " ".join(part for part in (get("first_name"), get("last_name")) if part)
    age = re.sub(r"\D", "", get("age"))
    return {
        "source": source,
        "external_id": get("external_id") or None,
        "name": name or None,
        "phone": normalize_phone(get("phone")),
        "email": get("email").lower() or None,
        "city": get("city") or None,
        "state": get("state").upper()[:2] or None,
        "loan_amount": parse_money(get("loan_amount")),
        "est_value": parse_money(get("est_value")),
        "credit": get("credit") or None,
        "age": int(age) if age else None,
        "lead_date": get("lead_date") or None,
        "notes": get("notes") or None,
    }


def find_existing(conn, lead):
    if lead["phone"]:
        row = conn.execute("SELECT id FROM leads WHERE phone = ?", (lead["phone"],)).fetchone()
        if row:
            return row["id"]
    if lead["email"]:
        row = conn.execute("SELECT id FROM leads WHERE email = ?", (lead["email"],)).fetchone()
        if row:
            return row["id"]
    if lead["external_id"]:
        row = conn.execute(
            "SELECT id FROM leads WHERE source = ? AND external_id = ?",
            (lead["source"], lead["external_id"]),
        ).fetchone()
        if row:
            return row["id"]
    return None


def upsert_lead(conn, lead):
    """Insert a new lead or fill blanks / refresh values on an existing one."""
    existing_id = find_existing(conn, lead)
    if existing_id is None:
        cols = list(lead.keys())
        conn.execute(
            f"INSERT INTO leads ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
            [lead[c] for c in cols],
        )
        return "inserted"
    updates = {k: v for k, v in lead.items() if v not in (None, "")}
    if updates:
        assignments = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(
            f"UPDATE leads SET {assignments}, updated_at = datetime('now') WHERE id = ?",
            list(updates.values()) + [existing_id],
        )
    return "updated"


def import_csv(conn, path, source, config):
    source_cfg = (config.get("sources") or {}).get(source, {})
    counts = {"inserted": 0, "updated": 0, "skipped": 0}
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        header_map = build_header_map(reader.fieldnames or [], source_cfg)
        for row in reader:
            lead = row_to_lead(row, header_map, source)
            if not (lead["phone"] or lead["email"] or lead["name"]):
                counts["skipped"] += 1
                continue
            counts[upsert_lead(conn, lead)] += 1
    conn.commit()
    return counts, header_map
