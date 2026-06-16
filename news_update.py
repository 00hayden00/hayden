#!/usr/bin/env python3
"""
Fetch live football/World Cup news (keyless) and write news_data.js for the
dashboard. Source: BBC Sport football RSS. Run standalone (python3 news_update.py)
or let live_update.py call it a few times a day automatically.
"""
import re, json, time, html, urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

FEEDS = ["https://feeds.bbci.co.uk/sport/football/rss.xml"]

OURTEAMS = ["Mexico","South Africa","South Korea","Czechia","Canada","Bosnia & H.","Qatar","Switzerland",
 "Brazil","Morocco","Haiti","Scotland","USA","Paraguay","Australia","Türkiye","Germany","Curaçao",
 "Ivory Coast","Ecuador","Netherlands","Japan","Sweden","Tunisia","Belgium","Egypt","Iran","New Zealand",
 "Spain","Cape Verde","Saudi Arabia","Uruguay","France","Senegal","Iraq","Norway","Argentina","Algeria",
 "Austria","Jordan","Portugal","DR Congo","Uzbekistan","Colombia","England","Croatia","Ghana","Panama"]
ALIASES = {"United States":"USA","USMNT":"USA","Turkey":"Türkiye","Korea":"South Korea",
 "Czech Republic":"Czechia","Bosnia":"Bosnia & H.","Curacao":"Curaçao","Republic of Ireland":None}
# (search term, our team) sorted longest-first so specific names win
TERMS = sorted([(t, t) for t in OURTEAMS] + [(k, v) for k, v in ALIASES.items() if v],
               key=lambda x: -len(x[0]))

def strip_html(s):
    return re.sub(r"<[^>]+>", "", html.unescape(s or "")).strip()

def detect_team(text):
    low = text.lower()
    for term, team in TERMS:
        if term.lower() in low:
            return team
    return None

def fetch():
    items = []
    for url in FEEDS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            xml = urllib.request.urlopen(req, timeout=20).read()
            root = ET.fromstring(xml)
        except Exception as e:
            print(f"  feed failed ({url}): {e}"); continue
        for it in root.findall(".//item"):
            title = strip_html(it.findtext("title"))
            if not title: continue
            body = strip_html(it.findtext("description"))
            link = (it.findtext("link") or "").strip()
            pub = it.findtext("pubDate") or ""
            try:
                dt = parsedate_to_datetime(pub)
                d = dt.strftime("%Y-%m-%dT%H:%M"); when = dt.strftime("%b %d, %-I:%M %p")
            except Exception:
                d = time.strftime("%Y-%m-%dT%H:%M"); when = ""
            items.append({"title": title, "body": body, "link": link,
                          "d": d, "when": when, "team": detect_team(title + " " + body)})
    # de-dupe by title, sort newest first
    seen, uniq = set(), []
    for it in sorted(items, key=lambda x: x["d"], reverse=True):
        if it["title"] in seen: continue
        seen.add(it["title"]); uniq.append(it)
    # prioritise World Cup / participating-team stories, keep some general too
    wc = [i for i in uniq if "world cup" in (i["title"]+i["body"]).lower() or i["team"]]
    rest = [i for i in uniq if i not in wc]
    return (wc + rest)[:18]

def main():
    items = fetch()
    if not items:
        print("No news fetched."); return
    data = {"updated": time.strftime("%Y-%m-%d %H:%M:%S"), "source": "BBC Sport", "items": items}
    with open("news_data.js", "w", encoding="utf-8") as f:
        f.write("window.NEWSFEED = " + json.dumps(data, ensure_ascii=False) + ";\n")
    print(f"Wrote news_data.js — {len(items)} stories ({sum(1 for i in items if i['team'])} team-tagged)")

if __name__ == "__main__":
    main()
