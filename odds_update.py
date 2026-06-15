#!/usr/bin/env python3
"""
Fetch real bookmaker odds (FanDuel) and write odds_data.js for the dashboard's
Value tab, which compares them to the model's probabilities.

IMPORTANT / READ THIS
---------------------
FanDuel's traders are sharper than this hobby model. When the model "disagrees"
with FanDuel, that is almost always the MODEL being wrong, not real value. Treat
the Value tab as a curiosity for spotting where the toy diverges from the market
-- NOT as a betting signal. Don't bet money you can't afford to lose.

Setup
-----
1. Free API key: https://the-odds-api.com  (500 requests/month)
2. export ODDS_API_KEY=your_key     (PowerShell: $env:ODDS_API_KEY="your_key")
3. python3 odds_update.py            # match-winner odds (1 request)
   python3 odds_update.py --props    # also anytime-goalscorer props (1 req PER game!)

Match-winner odds cost ~1 request. Goalscorer props cost one request per game,
so --props can eat your monthly quota quickly -- it only pulls upcoming games.
"""

import os, sys, json, argparse, urllib.request, urllib.error
from datetime import datetime, timezone
try:
    from live_update import norm, KNOWN            # reuse team-name mapping
except Exception:
    def norm(x): return x
    KNOWN = set()

API = "https://api.the-odds-api.com/v4"
BOOK = "fanduel"

def _get(url):
    with urllib.request.urlopen(url, timeout=25) as r:
        remaining = r.headers.get("x-requests-remaining")
        return json.load(r), remaining

def wc_sport_key(key):
    try:
        data, _ = _get(f"{API}/sports/?apiKey={key}")
        for s in data:
            if "world cup" in s.get("title","").lower() or "world_cup" in s.get("key",""):
                return s["key"]
    except Exception:
        pass
    return "soccer_fifa_world_cup"

def fanduel_market(event, market_key):
    for b in event.get("bookmakers", []):
        if b.get("key") == BOOK:
            for m in b.get("markets", []):
                if m.get("key") == market_key:
                    return m.get("outcomes", [])
    return None

def fetch_h2h(key, sport):
    url = f"{API}/sports/{sport}/odds/?apiKey={key}&regions=us&markets=h2h&oddsFormat=decimal&bookmakers={BOOK}"
    events, remaining = _get(url)
    now = datetime.now(timezone.utc)
    out, skipped_live = [], 0
    for e in events:
        # skip games already kicked off — their odds are LIVE/in-play, not pre-match,
        # so they can't be compared to the model's pre-match probabilities.
        ct = e.get("commence_time")
        if ct:
            try:
                if datetime.fromisoformat(ct.replace("Z","+00:00")) <= now:
                    skipped_live += 1; continue
            except ValueError:
                pass
        oc = fanduel_market(e, "h2h")
        if not oc:
            continue
        home = norm(e.get("home_team","")); away = norm(e.get("away_team",""))
        prices = {}
        for o in oc:
            nm = o.get("name","")
            if nm == e.get("home_team"): prices["H"] = o["price"]
            elif nm == e.get("away_team"): prices["A"] = o["price"]
            elif nm.lower() == "draw": prices["D"] = o["price"]
        if home in KNOWN and away in KNOWN and len(prices) == 3:
            out.append({"home":home, "away":away, "h2h":prices, "id":e.get("id"), "utc":ct})
    return out, remaining, skipped_live

def fetch_props(key, sport, events, limit=10):
    """Anytime-goalscorer odds per game. One request per event -> uses quota."""
    scorers, used = [], 0
    for ev in events[:limit]:
        if not ev.get("id"):
            continue
        url = (f"{API}/sports/{sport}/events/{ev['id']}/odds/?apiKey={key}"
               f"&regions=us&markets=player_goal_scorer_anytime&oddsFormat=decimal&bookmakers={BOOK}")
        try:
            e, _ = _get(url); used += 1
        except urllib.error.HTTPError as ex:
            print(f"  props for {ev['home']} v {ev['away']}: HTTP {ex.code} (market may be unavailable)")
            continue
        oc = fanduel_market(e, "player_goal_scorer_anytime")
        if not oc:
            continue
        for o in oc:
            scorers.append({"home":ev["home"], "away":ev["away"],
                            "name":o.get("description") or o.get("name",""), "price":o["price"]})
    return scorers, used

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--props", action="store_true", help="also fetch anytime-goalscorer odds (1 request per game)")
    ap.add_argument("--props-limit", type=int, default=8, help="max games to pull props for")
    args = ap.parse_args()

    key = os.environ.get("ODDS_API_KEY")
    if not key:
        print("No ODDS_API_KEY set. Get a free key at https://the-odds-api.com then:\n"
              "  export ODDS_API_KEY=your_key   (PowerShell: $env:ODDS_API_KEY=\"your_key\")")
        sys.exit(1)

    sport = wc_sport_key(key)
    print(f"Sport key: {sport}")
    try:
        matches, remaining, skipped = fetch_h2h(key, sport)
    except urllib.error.HTTPError as e:
        print(f"Odds API error {e.code}: {e.reason}"); sys.exit(1)
    print(f"  {len(matches)} upcoming (pre-match) markets from FanDuel; skipped {skipped} "
          f"already-started/in-play  (requests remaining: {remaining})")

    scorers = []
    if args.props and matches:
        scorers, used = fetch_props(key, sport, matches, args.props_limit)
        print(f"  {len(scorers)} goalscorer prices over {used} games")

    import time
    data = {"updated": time.strftime("%Y-%m-%d %H:%M:%S"), "book": "FanDuel",
            "matches": matches, "scorers": scorers}
    with open("odds_data.js", "w", encoding="utf-8") as f:
        f.write("window.ODDS = " + json.dumps(data, ensure_ascii=False) + ";\n")
    print("Wrote odds_data.js -> open the dashboard's Value tab.")

if __name__ == "__main__":
    main()
