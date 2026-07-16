"""Command-line interface. Run as `python -m srm_bot <command>`."""

import argparse
import os
import shutil

from srm_bot import db
from srm_bot.importers import import_csv
from srm_bot.scoring import rescore_all


def fmt_phone(digits):
    if digits and len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return digits or "—"


def fmt_money(value):
    return f"${value:,.0f}" if value else "—"


def print_lead_row(lead):
    print(
        f"  #{lead['id']:<5} {lead['score']:>5.1f}  {(lead['name'] or '(no name)'):<28.28} "
        f"{fmt_phone(lead['phone']):<16} {fmt_money(lead['loan_amount']):>10}  "
        f"{(lead['state'] or ''):<2}  {lead['source']}"
    )


def cmd_init(args):
    conn = db.connect()
    conn.close()
    if not os.path.exists(db.CONFIG_PATH):
        shutil.copy(db.EXAMPLE_CONFIG_PATH, db.CONFIG_PATH)
        print(f"Created {db.CONFIG_PATH} — edit scoring weights & column mappings there.")
    print(f"Database ready at {db.DB_PATH}")


def cmd_import(args):
    conn = db.connect()
    config = db.load_config()
    counts, header_map = import_csv(conn, args.file, args.source, config)
    print(f"Imported {args.file} as source '{args.source}':")
    print(f"  new: {counts['inserted']}   updated: {counts['updated']}   skipped: {counts['skipped']}")
    print(f"  columns recognized: {', '.join(sorted(header_map)) or 'NONE — check config.json mappings'}")
    n = rescore_all(conn, config)
    print(f"Rescored {n} leads.")


def cmd_score(args):
    conn = db.connect()
    print(f"Rescored {rescore_all(conn, db.load_config())} leads.")


def _queue_query(conn, args):
    sql = (
        "SELECT * FROM leads WHERE score > 0 AND phone IS NOT NULL "
        "AND stage NOT IN ('funded', 'lost') "
        "AND id NOT IN (SELECT lead_id FROM calls WHERE called_at > datetime('now', ?))"
    )
    params = [f"-{args.cooldown_hours} hours"]
    if args.state:
        sql += " AND state = ?"
        params.append(args.state.upper())
    if args.min_amount:
        sql += " AND loan_amount >= ?"
        params.append(args.min_amount)
    sql += " ORDER BY score DESC LIMIT ?"
    params.append(args.limit)
    return conn.execute(sql, params).fetchall()


def cmd_queue(args):
    conn = db.connect()
    leads = _queue_query(conn, args)
    if not leads:
        print("Queue is empty — import a report or lower your filters.")
        return
    print(f"  {'ID':<6} {'SCORE':>5}  {'NAME':<28} {'PHONE':<16} {'LOAN AMT':>10}  ST  SOURCE")
    for lead in leads:
        print_lead_row(lead)
    print(f"\n{len(leads)} leads. Work them with: python -m srm_bot next")


def cmd_next(args):
    conn = db.connect()
    args.limit = 1
    leads = _queue_query(conn, args)
    if not leads:
        print("Nothing left in the queue. Nice.")
        return
    lead = leads[0]
    print("=" * 52)
    print(f"  CALL NOW  →  {fmt_phone(lead['phone'])}")
    print("=" * 52)
    print(f"  #{lead['id']}  {lead['name'] or '(no name)'}   score {lead['score']}")
    print(f"  {lead['city'] or ''} {lead['state'] or ''}   loan {fmt_money(lead['loan_amount'])}"
          f"   value {fmt_money(lead['est_value'])}   credit {lead['credit'] or '—'}")
    if lead["notes"]:
        print(f"  notes: {lead['notes']}")
    calls = conn.execute(
        "SELECT called_at, outcome, notes FROM calls WHERE lead_id = ? ORDER BY called_at DESC LIMIT 3",
        (lead["id"],),
    ).fetchall()
    for c in calls:
        print(f"  prior: {c['called_at']}  {c['outcome']}  {c['notes'] or ''}")
    print(f"\n  then: python -m srm_bot log {lead['id']} <outcome>")


def cmd_log(args):
    conn = db.connect()
    lead = conn.execute("SELECT * FROM leads WHERE id = ?", (args.lead_id,)).fetchone()
    if not lead:
        print(f"No lead #{args.lead_id}")
        return 1
    conn.execute(
        "INSERT INTO calls (lead_id, outcome, notes) VALUES (?, ?, ?)",
        (args.lead_id, args.outcome, args.notes),
    )
    auto_stage = {"appointment": "contacted", "callback": "contacted", "converted": "application"}
    if args.outcome in auto_stage and lead["stage"] == "lead":
        conn.execute("UPDATE leads SET stage = ? WHERE id = ?", (auto_stage[args.outcome], args.lead_id))
    conn.commit()
    rescore_all(conn, db.load_config())
    print(f"Logged {args.outcome} for #{args.lead_id} ({lead['name']}).")


def cmd_stage(args):
    conn = db.connect()
    updated = conn.execute(
        "UPDATE leads SET stage = ?, updated_at = datetime('now') WHERE id = ?",
        (args.stage, args.lead_id),
    ).rowcount
    conn.commit()
    print(f"Lead #{args.lead_id} → {args.stage}" if updated else f"No lead #{args.lead_id}")


def cmd_pipeline(args):
    conn = db.connect()
    active = [s for s in db.PIPELINE_STAGES if s not in ("lead", "lost")]
    for stage in active:
        rows = conn.execute(
            "SELECT * FROM leads WHERE stage = ? ORDER BY updated_at", (stage,)
        ).fetchall()
        if not rows:
            continue
        print(f"\n{stage.upper()} ({len(rows)})")
        for lead in rows:
            days = conn.execute(
                "SELECT CAST(julianday('now') - julianday(updated_at) AS INT) d FROM leads WHERE id = ?",
                (lead["id"],),
            ).fetchone()["d"]
            flag = f"  ⚠ stale {days}d" if days >= args.stale else ""
            print(f"  #{lead['id']:<5} {(lead['name'] or '(no name)'):<28.28} "
                  f"{fmt_money(lead['loan_amount']):>10}  updated {lead['updated_at'][:10]}{flag}")


def cmd_show(args):
    conn = db.connect()
    lead = conn.execute("SELECT * FROM leads WHERE id = ?", (args.lead_id,)).fetchone()
    if not lead:
        print(f"No lead #{args.lead_id}")
        return 1
    for key in lead.keys():
        print(f"  {key:<12} {lead[key] if lead[key] is not None else '—'}")
    print("  --- calls ---")
    for c in conn.execute(
        "SELECT called_at, outcome, notes FROM calls WHERE lead_id = ? ORDER BY called_at",
        (args.lead_id,),
    ):
        print(f"  {c['called_at']}  {c['outcome']}  {c['notes'] or ''}")


def cmd_stats(args):
    conn = db.connect()
    total = conn.execute("SELECT COUNT(*) n FROM leads").fetchone()["n"]
    print(f"Leads: {total}")
    for row in conn.execute("SELECT source, COUNT(*) n FROM leads GROUP BY source ORDER BY n DESC"):
        print(f"  {row['source']:<20} {row['n']}")
    print("Pipeline:")
    for row in conn.execute("SELECT stage, COUNT(*) n FROM leads GROUP BY stage"):
        print(f"  {row['stage']:<20} {row['n']}")
    print("Calls:")
    for row in conn.execute("SELECT outcome, COUNT(*) n FROM calls GROUP BY outcome ORDER BY n DESC"):
        print(f"  {row['outcome']:<20} {row['n']}")


def add_queue_filters(parser):
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--state", help="two-letter state filter")
    parser.add_argument("--min-amount", type=float, help="minimum loan amount")
    parser.add_argument("--cooldown-hours", type=int, default=4,
                        help="hide leads called within the last N hours (default 4)")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="srm_bot", description="SRM-Bot: lead queue & pipeline assistant")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="create the local database and config").set_defaults(fn=cmd_init)

    p = sub.add_parser("import", help="import a CSV lead export")
    p.add_argument("file")
    p.add_argument("--source", required=True,
                   help="e.g. demandconversions, atlasaddress, or any label you like")
    p.set_defaults(fn=cmd_import)

    sub.add_parser("score", help="recompute all lead scores").set_defaults(fn=cmd_score)

    p = sub.add_parser("queue", help="ranked call list")
    add_queue_filters(p)
    p.set_defaults(fn=cmd_queue)

    p = sub.add_parser("next", help="top prospect, dial-ready")
    add_queue_filters(p)
    p.set_defaults(fn=cmd_next)

    p = sub.add_parser("log", help="record a call outcome")
    p.add_argument("lead_id", type=int)
    p.add_argument("outcome", choices=db.CALL_OUTCOMES)
    p.add_argument("--notes")
    p.set_defaults(fn=cmd_log)

    p = sub.add_parser("stage", help="move a deal through the pipeline")
    p.add_argument("lead_id", type=int)
    p.add_argument("stage", choices=db.PIPELINE_STAGES)
    p.set_defaults(fn=cmd_stage)

    p = sub.add_parser("pipeline", help="active deals by stage")
    p.add_argument("--stale", type=int, default=5, help="flag deals untouched N+ days (default 5)")
    p.set_defaults(fn=cmd_pipeline)

    p = sub.add_parser("show", help="full detail for one lead")
    p.add_argument("lead_id", type=int)
    p.set_defaults(fn=cmd_show)

    sub.add_parser("stats", help="summary counts").set_defaults(fn=cmd_stats)

    args = parser.parse_args(argv)
    return args.fn(args) or 0
