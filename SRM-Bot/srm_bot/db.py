"""Local SQLite storage — the bot's memory. One file: data/srmbot.db."""

import json
import os
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
DB_PATH = os.path.join(DATA_DIR, "srmbot.db")
CONFIG_PATH = os.path.join(ROOT, "config.json")
EXAMPLE_CONFIG_PATH = os.path.join(ROOT, "config.example.json")

PIPELINE_STAGES = ["lead", "contacted", "application", "processing", "closing", "funded", "lost"]
CALL_OUTCOMES = ["no_answer", "callback", "appointment", "not_interested", "dead", "converted"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source        TEXT NOT NULL,
    external_id   TEXT,
    name          TEXT,
    phone         TEXT,           -- normalized to digits only
    email         TEXT,
    city          TEXT,
    state         TEXT,
    loan_amount   REAL,
    est_value     REAL,
    credit        TEXT,
    age           INTEGER,
    lead_date     TEXT,           -- ISO date the lead was generated
    stage         TEXT NOT NULL DEFAULT 'lead',
    score         REAL NOT NULL DEFAULT 0,
    notes         TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_leads_phone ON leads(phone);
CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email);
CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(score);

CREATE TABLE IF NOT EXISTS calls (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id   INTEGER NOT NULL REFERENCES leads(id),
    called_at TEXT NOT NULL DEFAULT (datetime('now')),
    outcome   TEXT NOT NULL,
    notes     TEXT
);
CREATE INDEX IF NOT EXISTS idx_calls_lead ON calls(lead_id);
"""


def connect():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def load_config():
    path = CONFIG_PATH if os.path.exists(CONFIG_PATH) else EXAMPLE_CONFIG_PATH
    with open(path) as f:
        return json.load(f)
