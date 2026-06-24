#!/usr/bin/env python3
"""
Live data updater for the World Cup '26 dashboard.

What it does
------------
1. Pulls real World Cup match data from a football data API.
2. Writes two files the dashboard reads:
     - live_data.js          (window.LIVE = {...})  -> real scores + LIVE minutes
     - results_override.json  -> finished games, fed back into the simulation
3. Re-runs simulate_worldcup.py so predictions update as real results land.

Why a local script (and not the browser)?
------------------------------------------
The good live APIs (a) require a secret key you should NOT ship in client-side
HTML, and (b) block direct browser (CORS) calls. So this script runs on your
machine, holds the key, and the dashboard just polls the files it writes.

Setup
-----
1. Get a FREE API token from https://www.football-data.org/client/register
2. export FOOTBALL_API_KEY=your_token_here        (Windows: set FOOTBALL_API_KEY=...)
3. One update:      python3 live_update.py
   Keep it live:    python3 live_update.py --watch 60      (refresh every 60s)

If no key is set, the dashboard simply keeps showing the latest simulation
snapshot — nothing breaks, it just isn't live.
"""

import os, sys, json, time, argparse, subprocess, urllib.request, urllib.error

# Map API team names -> the names used in simulate_worldcup.py / the dashboard.
ALIASES = {
    "Korea Republic":"South Korea", "Republic of Korea":"South Korea", "Korea":"South Korea",
    "Bosnia and Herzegovina":"Bosnia & H.", "Bosnia-Herzegovina":"Bosnia & H.", "Bosnia & Herzegovina":"Bosnia & H.",
    "Turkey":"Türkiye", "Turkiye":"Türkiye",
    "United States":"USA", "United States of America":"USA",
    "Czech Republic":"Czechia",
    "Côte d'Ivoire":"Ivory Coast", "Cote d'Ivoire":"Ivory Coast",
    "DR Congo":"DR Congo", "Congo DR":"DR Congo", "Democratic Republic of the Congo":"DR Congo",
    "Cape Verde Islands":"Cape Verde", "Cabo Verde":"Cape Verde",
    "Curacao":"Curaçao",
    "IR Iran":"Iran", "Iran":"Iran",
    "Saudi Arabia":"Saudi Arabia",
}
# the 48 names we understand (kept in sync with the simulator)
KNOWN = {
 "Spain","France","England","Argentina","Portugal","Brazil","Germany","Netherlands",
 "Belgium","Uruguay","Norway","Morocco","Croatia","Colombia","Senegal","Japan","Mexico",
 "Switzerland","USA","Ecuador","Austria","South Korea","Türkiye","Sweden","Egypt",
 "Ivory Coast","Canada","Iran","Algeria","Australia","Czechia","Scotland","Paraguay",
 "Tunisia","Bosnia & H.","Ghana","DR Congo","Uzbekistan","Qatar","Panama","Saudi Arabia",
 "South Africa","Iraq","Jordan","Cape Verde","New Zealand","Haiti","Curaçao",
}

def norm(name):
    return ALIASES.get(name, name)

def fetch_football_data(api_key, competition="WC"):
    """football-data.org v4. Returns list of normalised match dicts.
    Honours the API's rate-limit headers (free tier ~10 req/min) to avoid throttling."""
    url = f"https://api.football-data.org/v4/competitions/{competition}/matches"
    req = urllib.request.Request(url, headers={"X-Auth-Token": api_key})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)
        # Daniel's tip: watch the headers so we don't hit the rate limiter.
        remaining = r.headers.get("X-Requests-Available-Minute")
        if remaining is not None:
            try:
                if int(remaining) <= 1:
                    print("  Rate limit nearly reached — pausing 60s to reset...")
                    time.sleep(60)
            except ValueError:
                pass
    out = []
    for m in data.get("matches", []):
        grp = (m.get("group") or "").replace("GROUP_", "").strip() or None
        st = m.get("status", "")
        status = ("FINISHED" if st == "FINISHED"
                  else "LIVE" if st in ("IN_PLAY", "PAUSED")
                  else "SCHED")
        ft = (m.get("score") or {}).get("fullTime") or {}
        out.append({
            "group": grp,
            "home": norm((m.get("homeTeam") or {}).get("name", "")),
            "away": norm((m.get("awayTeam") or {}).get("name", "")),
            "status": status,
            "hs": ft.get("home"),
            "as": ft.get("away"),
            "minute": m.get("minute"),
            "utc": m.get("utcDate"),      # real kickoff (ISO 8601 UTC) for accurate dates
        })
    return out

def fetch_scorers(api_key, competition="WC", limit=25):
    """Actual top scorers so far (the real Golden Boot) from football-data."""
    url = f"https://api.football-data.org/v4/competitions/{competition}/scorers?limit={limit}"
    req = urllib.request.Request(url, headers={"X-Auth-Token": api_key})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)
    out = []
    for s in data.get("scorers", []):
        out.append({"name": (s.get("player") or {}).get("name", ""),
                    "team": norm((s.get("team") or {}).get("name", "")),
                    "goals": s.get("goals") or 0, "assists": s.get("assists") or 0})
    return out

def update_once(api_key, competition):
    try:
        matches = fetch_football_data(api_key, competition)
    except urllib.error.HTTPError as e:
        if e.code == 429:   # too many requests — respect Retry-After and skip this cycle
            wait = e.headers.get("Retry-After", "60")
            print(f"  Rate limited (429). Wait {wait}s before the next call.")
            try: time.sleep(min(120, int(wait)))
            except ValueError: time.sleep(60)
            return False
        print(f"  API error {e.code}: {e.reason}. "
              f"{'Check your FOOTBALL_API_KEY / plan.' if e.code in (401,403) else ''}")
        return False
    except Exception as e:
        print(f"  Fetch failed: {e}")
        return False

    # keep only group-stage matches we recognise, with a known group + both teams
    clean, unknown = [], set()
    for m in matches:
        if not m["group"]:
            continue
        for side in ("home", "away"):
            if m[side] and m[side] not in KNOWN:
                unknown.add(m[side])
        if m["home"] in KNOWN and m["away"] in KNOWN:
            clean.append(m)
    if unknown:
        print(f"  Note: unmapped team names (add to ALIASES): {sorted(unknown)}")

    # actual top scorers (real Golden Boot) — refreshed each cycle so it reflects
    # the game that just ended
    scorers = []
    try:
        scorers = fetch_scorers(api_key, competition)
    except Exception as e:
        print(f"  scorers fetch skipped: {e}")

    # live_data.js for the dashboard
    live = {"updated": time.strftime("%Y-%m-%d %H:%M:%S"), "matches": clean, "scorers": scorers}
    with open("live_data.js", "w", encoding="utf-8") as f:
        f.write("window.LIVE = " + json.dumps(live, ensure_ascii=False) + ";\n")

    # full schedule (correct dates/home-away/status) for the simulator
    with open("fixtures.json", "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False)

    # results_override.json for the simulator (finished games only)
    overrides = [[m["group"], m["home"], m["away"], m["hs"], m["as"]]
                 for m in clean if m["status"] == "FINISHED"
                 and m["hs"] is not None and m["as"] is not None]
    with open("results_override.json", "w", encoding="utf-8") as f:
        json.dump(overrides, f, ensure_ascii=False)

    n_live = sum(1 for m in clean if m["status"] == "LIVE")
    print(f"  {len(clean)} matches | {len(overrides)} finished | {n_live} live | "
          f"{len(scorers)} scorers -> live_data.js, results_override.json")

    # regenerate sim_results.js with reality folded in (force UTF-8 so accented
    # player names don't crash the child process on Windows cp1252 consoles)
    print("  Re-running simulation...")
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    res = subprocess.run([sys.executable, "simulate_worldcup.py"],
                         capture_output=True, text=True,
                         encoding="utf-8", errors="replace", env=env)
    if res.returncode != 0:
        print("  Simulation failed:\n" + res.stderr[-800:])
        return False
    print("  sim_results.js refreshed.")
    return True

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", type=int, default=0,
                    help="loop, refreshing every N seconds (0 = run once)")
    ap.add_argument("--competition", default="WC", help="football-data.org competition code")
    args = ap.parse_args()

    api_key = os.environ.get("FOOTBALL_API_KEY")
    if not api_key:
        print("No FOOTBALL_API_KEY set. Get a free token at "
              "https://www.football-data.org/client/register then:\n"
              "  export FOOTBALL_API_KEY=your_token\n"
              "The dashboard will keep showing the latest simulation snapshot until then.")
        sys.exit(1)

    # news (keyless) refreshes a few times/day; odds (if key) every few hours
    try:
        from news_update import main as refresh_news
    except Exception:
        refresh_news = None
    NEWS_EVERY = 2*3600
    ODDS_EVERY = 3*3600          # FanDuel odds every 3 hours

    def refresh_extras(state):
        now = time.time()
        if refresh_news and now - state.get("news", 0) >= NEWS_EVERY:
            print("  refreshing news...")
            try: refresh_news(); state["news"] = now
            except Exception as e: print("  news refresh failed:", e)
        if os.environ.get("ODDS_API_KEY") and now - state.get("odds", 0) >= ODDS_EVERY:
            print("  refreshing FanDuel odds...")
            try: subprocess.run([sys.executable, "odds_update.py"], timeout=120); state["odds"] = now
            except Exception as e: print("  odds refresh failed:", e)

    if args.watch:
        print(f"Live mode: scores every {args.watch}s, news ~2h, odds ~3h. Ctrl-C to stop.")
        state = {}
        while True:
            print(time.strftime("[%H:%M:%S] updating..."))
            update_once(api_key, args.competition)
            refresh_extras(state)
            time.sleep(args.watch)
    else:
        update_once(api_key, args.competition)
        refresh_extras({})

if __name__ == "__main__":
    main()
