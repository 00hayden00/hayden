# SRM-Bot

Personal lead-organization and pipeline assistant for a loan officer at South River Mortgage.

SRM-Bot pulls lead exports from the company CRM (**DemandConversions**) and outside sources
(**AtlasAddress**, or any CSV), merges and dedupes them into a single local database, scores
every lead by expected payout, and hands you an ordered **call queue** so you can dial your
top prospects back-to-back without hunting through spreadsheets. It also tracks each deal's
pipeline stage so nothing goes stale.

Everything runs and stores its memory **locally on your laptop** — a single SQLite file at
`data/srmbot.db`. No cloud, no external services. You control it from your office desktop by
remoting into the laptop (see [docs/REMOTE_ACCESS.md](docs/REMOTE_ACCESS.md)).

## Quick start

Requires Python 3.9+ (standard library only — nothing to `pip install`).

```bash
# 1. One-time setup: create the local database and a config file
python -m srm_bot init

# 2. Import today's reports (re-run daily; duplicates are merged automatically)
python -m srm_bot import ~/Downloads/dc_daily_report.csv --source demandconversions
python -m srm_bot import ~/Downloads/atlas_export.csv    --source atlasaddress

# 3. See your top prospects, best first
python -m srm_bot queue --limit 25

# 4. Work the queue: shows the #1 lead with phone number front and center
python -m srm_bot next

# 5. Log the result in two seconds, then `next` again
python -m srm_bot log 42 callback --notes "wants rates Thursday AM"
```

## Daily workflow

1. Export the daily report from DemandConversions and any AtlasAddress pulls.
2. `import` each file — new leads are added, existing ones (matched by phone/email) are updated.
3. `queue` / `next` / `log` in a loop until you've burned through your call block.
4. `pipeline` to review active deals and see which ones haven't moved.

## Commands

| Command | What it does |
|---|---|
| `init` | Create `data/srmbot.db` and `config.json` from the example |
| `import FILE --source NAME` | Import a CSV export; dedupes against existing leads |
| `score` | Recompute every lead's score (runs automatically after import) |
| `queue [--limit N] [--state XX] [--min-amount N]` | Ranked list of callable leads |
| `next` | Top uncalled lead, dial-ready |
| `log LEAD_ID OUTCOME [--notes ...]` | Record a call: `no_answer`, `callback`, `appointment`, `not_interested`, `dead`, `converted` |
| `stage LEAD_ID STAGE` | Move a deal: `lead` → `contacted` → `application` → `processing` → `closing` → `funded` |
| `pipeline [--stale N]` | Active deals by stage; flag deals untouched for N+ days |
| `show LEAD_ID` | Full detail + call history for one lead |
| `stats` | Import/call/conversion summary |

## How scoring works

Each lead gets a 0–100 score from weights you control in `config.json`:

- **Loan amount / est. home value** — bigger deals score higher (this is the payout proxy)
- **Source quality** — per-source multiplier (e.g. rate CRM leads above cold list pulls)
- **Recency** — fresh leads decay-boosted; a lead loses value every day it sits
- **Call history** — `callback` outcomes float up; repeated `no_answer` sinks; `dead` is excluded

Tune the weights in `config.json` → `scoring`. Column names in your exports are mapped in
`config.json` → `sources` — the importer also auto-detects common header names, so most
exports work with zero configuration.

## Where things live

| Path | Contents | Committed? |
|---|---|---|
| `data/srmbot.db` | All leads, calls, pipeline — the bot's memory | **No** (gitignored, stays on the laptop) |
| `config.json` | Your scoring weights and column mappings | **No** (gitignored; copy from `config.example.json`) |
| `samples/` | Example CSVs showing the expected shapes | Yes |

Back up `data/srmbot.db` occasionally (it's one file — copy it anywhere).

## Compliance note

You're dialing consumers: follow South River Mortgage policy and applicable rules (DNC
registry, TCPA calling hours) for every list you import — especially outside-source pulls
like AtlasAddress. SRM-Bot organizes your leads; scrubbing lists is on you and your company's
tooling.
