#!/usr/bin/env python3
"""
World Cup 2026 Monte Carlo simulator.

Model
-----
* Each team has an Elo-style power rating (derived from bookmaker title odds +
  FIFA/Elo strength + early results).
* A match is simulated with a bivariate-Poisson-ish model: rating difference is
  turned into each side's expected goals (xG), then goals are drawn from a
  Poisson distribution. Host nations (MEX/CAN/USA) get a home boost.
* Every goal is attributed to a scorer drawn from that team's scoring-share
  table (stars carry more weight; "Others" is the rest of the squad).
* Already-played group games are FIXED to their real scorelines; only the
  remaining games are simulated, so the output is the most likely scenario
  *given what has already happened*.

Outputs
-------
* A readable report to stdout.
* sim_results.js  ->  window.SIM = {...}  consumed by worldcup.html.
"""

import math, random, json
from collections import Counter, defaultdict

random.seed(26)

SIMS_PER_GAME   = 10000   # per remaining group game (scorers / scoreline / W-D-L)
TOURNAMENT_SIMS = 10000   # full-tournament runs (qualification % + title odds)

# ---------------------------------------------------------------------------
# Power ratings  (Elo-style; higher = stronger)
# ---------------------------------------------------------------------------
RATINGS = {
 "Spain":2080,"France":2070,"England":2010,"Argentina":2010,"Portugal":2000,
 "Brazil":1995,"Germany":1990,"Netherlands":1940,"Belgium":1890,"Uruguay":1885,
 "Norway":1880,"Morocco":1875,"Croatia":1870,"Colombia":1865,"Senegal":1860,
 "Japan":1855,"Mexico":1850,"Switzerland":1850,"USA":1845,"Ecuador":1840,
 "Austria":1825,"South Korea":1820,"Türkiye":1820,"Sweden":1815,"Egypt":1810,"Ivory Coast":1810,
 "Canada":1810,"Iran":1800,"Algeria":1795,"Australia":1795,"Czechia":1790,
 "Scotland":1785,"Paraguay":1780,"Tunisia":1760,"Bosnia & H.":1760,"Ghana":1755,
 "DR Congo":1750,"Uzbekistan":1740,"Qatar":1740,"Panama":1730,"Saudi Arabia":1730,
 "South Africa":1730,"Iraq":1720,"Jordan":1710,"Cape Verde":1700,"New Zealand":1700,
 "Haiti":1670,"Curaçao":1660,
}
HOSTS = {"Mexico","Canada","USA"}

# ---------------------------------------------------------------------------
# Scoring shares per team (name, share of team goals). "Others" = rest of squad.
# ---------------------------------------------------------------------------
SQUADS = {
 "Spain":[("Yamal",.22),("Oyarzabal",.18),("Pedri",.10),("Merino",.10),("Olmo",.10),("Others",.30)],
 "France":[("Mbappé",.30),("Olise",.15),("Dembélé",.12),("Thuram",.10),("Others",.33)],
 "England":[("Kane",.28),("Bellingham",.18),("Saka",.14),("Foden",.10),("Others",.30)],
 "Argentina":[("L. Martínez",.22),("J. Álvarez",.20),("Messi",.18),("Others",.40)],
 "Portugal":[("Ronaldo",.22),("B. Fernandes",.16),("Leão",.12),("L. Félix",.12),("Others",.38)],
 "Brazil":[("Vinícius",.26),("Raphinha",.16),("Endrick",.12),("Neymar",.08),("Others",.38)],
 "Germany":[("Wirtz",.18),("Havertz",.18),("Musiala",.16),("Füllkrug",.12),("Others",.36)],
 "Netherlands":[("Gakpo",.20),("Depay",.18),("Reijnders",.10),("Others",.52)],
 "Belgium":[("Lukaku",.22),("De Bruyne",.18),("Doku",.12),("Others",.48)],
 "Uruguay":[("Núñez",.22),("Pellistri",.12),("Araújo",.10),("Others",.56)],
 "Norway":[("Haaland",.40),("Sørloth",.14),("Ødegaard",.12),("Others",.34)],
 "Morocco":[("En-Nesyri",.22),("Brahim Díaz",.12),("Ziyech",.12),("Others",.54)],
 "Croatia":[("Kramarić",.18),("Budimir",.14),("Modrić",.10),("Others",.58)],
 "Colombia":[("L. Díaz",.26),("Córdoba",.14),("James",.12),("Others",.48)],
 "Senegal":[("N. Jackson",.18),("I. Sarr",.16),("Mané",.14),("Others",.52)],
 "Japan":[("Mitoma",.18),("Ueda",.14),("Kamada",.14),("Kubo",.12),("Others",.42)],
 "Mexico":[("R. Jiménez",.20),("Quiñones",.16),("Lozano",.12),("Others",.52)],
 "Switzerland":[("Embolo",.20),("Ndoye",.12),("Vargas",.12),("Others",.56)],
 "USA":[("Balogun",.22),("Pulisic",.22),("Weah",.10),("Others",.46)],
 "Ecuador":[("E. Valencia",.22),("K. Rodríguez",.12),("Others",.66)],
 "Austria":[("Arnautović",.18),("Gregoritsch",.14),("Baumgartner",.12),("Others",.56)],
 "Sweden":[("Gyökeres",.30),("Isak",.22),("Others",.48)],
 "South Korea":[("Son",.26),("Hwang",.16),("Oh",.12),("Others",.46)],
 "Türkiye":[("A. Yılmaz",.16),("Güler",.14),("Aktürkoğlu",.12),("Others",.58)],
 "Egypt":[("Salah",.34),("Marmoush",.14),("Others",.52)],
 "Ivory Coast":[("Haller",.18),("Adingra",.12),("Krasso",.12),("Others",.58)],
 "Canada":[("J. David",.26),("Larin",.14),("Davies",.10),("Others",.50)],
 "Iran":[("Taremi",.26),("Azmoun",.16),("Others",.58)],
 "Algeria":[("Mahrez",.20),("Amoura",.14),("Slimani",.14),("Others",.52)],
 "Australia":[("Duke",.16),("Irvine",.12),("Others",.72)],
 "Czechia":[("Schick",.26),("Hložek",.14),("Others",.60)],
 "Scotland":[("McTominay",.18),("Adams",.14),("Dykes",.10),("Others",.58)],
 "Paraguay":[("Sanabria",.18),("Almirón",.14),("Others",.68)],
 "Tunisia":[("Msakni",.16),("Jebali",.12),("Others",.72)],
 "Bosnia & H.":[("Džeko",.24),("Demirović",.14),("Others",.62)],
 "Ghana":[("Kudus",.18),("J. Ayew",.16),("Semenyo",.12),("Others",.54)],
 "DR Congo":[("Bakambu",.18),("Wissa",.16),("Others",.66)],
 "Uzbekistan":[("Shomurodov",.20),("Others",.80)],
 "Qatar":[("Almoez Ali",.22),("Afif",.14),("Others",.64)],
 "Panama":[("Fajardo",.14),("Carrasquilla",.12),("Others",.74)],
 "Saudi Arabia":[("Al-Dawsari",.18),("Firas",.12),("Others",.70)],
 "South Africa":[("Zwane",.14),("Foster",.12),("Others",.74)],
 "Iraq":[("Aymen Hussein",.20),("Others",.80)],
 "Jordan":[("Al-Naimat",.16),("Al-Tamari",.14),("Others",.70)],
 "Cape Verde":[("Mendes",.16),("Tavares",.12),("Others",.72)],
 "New Zealand":[("Wood",.26),("Others",.74)],
 "Haiti":[("Pierrot",.18),("Others",.82)],
 "Curaçao":[("Bacuna",.16),("Locadia",.14),("Others",.70)],
}

# ---------------------------------------------------------------------------
# Fixtures.  PLAYED = real results (fixed).  REMAINING = to be simulated.
# ---------------------------------------------------------------------------
PLAYED = [  # date, group, home, away, hs, as
 ("Thu Jun 11","A","Mexico","South Africa",2,0),
 ("Thu Jun 11","A","South Korea","Czechia",2,1),
 ("Fri Jun 12","B","Canada","Bosnia & H.",1,1),
 ("Fri Jun 12","D","USA","Paraguay",4,1),
 ("Sat Jun 13","B","Qatar","Switzerland",1,1),
 ("Sat Jun 13","C","Brazil","Morocco",1,1),
 ("Sat Jun 13","C","Haiti","Scotland",0,1),
 ("Sat Jun 13","D","Australia","Türkiye",2,0),
 ("Sun Jun 14","E","Germany","Curaçao",7,1),
 ("Sun Jun 14","F","Netherlands","Japan",2,2),
 ("Sun Jun 14","E","Ivory Coast","Ecuador",1,0),
 ("Sun Jun 14","F","Sweden","Tunisia",5,1),
]
REMAINING = [  # date, group, home, away
 ("Mon Jun 15","H","Spain","Cape Verde"),("Mon Jun 15","H","Saudi Arabia","Uruguay"),
 ("Mon Jun 15","G","Belgium","Egypt"),("Mon Jun 15","G","Iran","New Zealand"),
 ("Tue Jun 16","A","Czechia","South Africa"),("Wed Jun 17","A","Mexico","South Korea"),
 ("Sun Jun 21","A","Czechia","Mexico"),("Sun Jun 21","A","South Africa","South Korea"),
 ("Wed Jun 17","B","Switzerland","Bosnia & H."),("Wed Jun 17","B","Canada","Qatar"),
 ("Mon Jun 22","B","Switzerland","Canada"),("Mon Jun 22","B","Bosnia & H.","Qatar"),
 ("Wed Jun 18","C","Scotland","Morocco"),("Wed Jun 18","C","Brazil","Haiti"),
 ("Tue Jun 23","C","Scotland","Brazil"),("Tue Jun 23","C","Morocco","Haiti"),
 ("Thu Jun 18","D","USA","Australia"),("Thu Jun 18","D","Türkiye","Paraguay"),
 ("Tue Jun 23","D","Türkiye","USA"),("Tue Jun 23","D","Paraguay","Australia"),
 ("Fri Jun 19","E","Germany","Ivory Coast"),("Fri Jun 19","E","Ecuador","Curaçao"),
 ("Wed Jun 24","E","Curaçao","Ivory Coast"),("Wed Jun 24","E","Ecuador","Germany"),
 ("Fri Jun 19","F","Netherlands","Sweden"),("Fri Jun 19","F","Tunisia","Japan"),
 ("Wed Jun 24","F","Japan","Sweden"),("Wed Jun 24","F","Tunisia","Netherlands"),
 ("Sat Jun 20","G","Belgium","Iran"),("Sat Jun 20","G","New Zealand","Egypt"),
 ("Thu Jun 25","G","Egypt","Iran"),("Thu Jun 25","G","New Zealand","Belgium"),
 ("Sat Jun 20","H","Spain","Saudi Arabia"),("Sat Jun 20","H","Uruguay","Cape Verde"),
 ("Thu Jun 25","H","Cape Verde","Saudi Arabia"),("Thu Jun 25","H","Uruguay","Spain"),
 ("Tue Jun 16","I","France","Senegal"),("Tue Jun 16","I","Iraq","Norway"),
 ("Sun Jun 21","I","France","Iraq"),("Sun Jun 21","I","Norway","Senegal"),
 ("Fri Jun 26","I","Norway","France"),("Fri Jun 26","I","Senegal","Iraq"),
 ("Tue Jun 16","J","Argentina","Algeria"),("Tue Jun 16","J","Austria","Jordan"),
 ("Sun Jun 21","J","Argentina","Austria"),("Sun Jun 21","J","Algeria","Jordan"),
 ("Fri Jun 26","J","Algeria","Austria"),("Fri Jun 26","J","Jordan","Argentina"),
 ("Wed Jun 17","K","Portugal","DR Congo"),("Wed Jun 17","K","Uzbekistan","Colombia"),
 ("Mon Jun 22","K","Portugal","Uzbekistan"),("Mon Jun 22","K","Colombia","DR Congo"),
 ("Sat Jun 27","K","Colombia","Portugal"),("Sat Jun 27","K","DR Congo","Uzbekistan"),
 ("Wed Jun 17","L","England","Croatia"),("Wed Jun 17","L","Ghana","Panama"),
 ("Mon Jun 22","L","England","Ghana"),("Mon Jun 22","L","Panama","Croatia"),
 ("Sat Jun 27","L","Panama","England"),("Sat Jun 27","L","Croatia","Ghana"),
]

GROUPS = defaultdict(set)
for _,g,h,a,*_ in PLAYED: GROUPS[g].update([h,a])
for _,g,h,a in REMAINING: GROUPS[g].update([h,a])

# ---------------------------------------------------------------------------
# Live override: if live_update.py has written real results, fold them in so
# predictions reflect reality. results_override.json = [[group,home,away,hs,as],...]
# ---------------------------------------------------------------------------
import os
if os.path.exists("results_override.json"):
    with open("results_override.json", encoding="utf-8") as f:
        overrides = json.load(f)
    # base truth = hardcoded results, then augment/correct with the live overrides
    scores = {(g,h,a): (hs,as_) for _,g,h,a,hs,as_ in PLAYED}
    for o in overrides:
        scores[(o[0], o[1], o[2])] = (o[3], o[4])
    date_of = {}
    for d,g,h,a,*_ in PLAYED: date_of[(g,h,a)] = d
    for d,g,h,a in REMAINING: date_of[(g,h,a)] = d
    new_played, new_remaining = [], []
    for (g,h,a), d in date_of.items():
        if (g,h,a) in scores:
            hs, as_ = scores[(g,h,a)]; new_played.append((d,g,h,a,hs,as_))
        else:
            new_remaining.append((d,g,h,a))
    PLAYED, REMAINING = new_played, new_remaining
    print(f"Applied {len(overrides)} live override(s); {len(PLAYED)} games now final, "
          f"{len(REMAINING)} to simulate")

# ---------------------------------------------------------------------------
# Core model
# ---------------------------------------------------------------------------
def expected_goals(home, away):
    rh = RATINGS[home] + (55 if home in HOSTS else 0)
    ra = RATINGS[away] + (55 if away in HOSTS else 0)
    sup = (rh - ra) / 100.0 * 0.50          # rating diff -> goal supremacy
    total = 2.65
    return max(0.18,(total+sup)/2), max(0.18,(total-sup)/2)

def poisson(lam):
    L, k, p = math.exp(-lam), 0, 1.0
    while True:
        k += 1; p *= random.random()
        if p <= L: return k-1

def scorer(team):
    r, c = random.random(), 0.0
    for name, w in SQUADS[team]:
        c += w
        if r <= c: return name
    return "Others"

def sim_match(home, away, want_scorers=False):
    hx, ax = expected_goals(home, away)
    hg, ag = poisson(hx), poisson(ag_lam := ax)
    sc = []
    if want_scorers:
        for _ in range(hg):
            n = scorer(home)
            if n != "Others": sc.append((home, n))
        for _ in range(ag):
            n = scorer(away)
            if n != "Others": sc.append((away, n))
    return hg, ag, sc

def ko_winner(a, b):
    hg, ag, _ = sim_match(a, b)
    if hg > ag: return a
    if ag > hg: return b
    pa = 0.5 + (RATINGS[a]-RATINGS[b]) / 4000.0          # penalties, slight edge
    return a if random.random() < min(0.75,max(0.25,pa)) else b

# ---------------------------------------------------------------------------
# 1) Per-game predictions (remaining games)
# ---------------------------------------------------------------------------
print(f"Simulating {len(REMAINING)} remaining group games x {SIMS_PER_GAME:,} each...")
game_results = []
for date, g, home, away in REMAINING:
    wdl = Counter(); scores = {"H":Counter(),"D":Counter(),"A":Counter()}; goals_for = Counter()
    for _ in range(SIMS_PER_GAME):
        hg, ag, sc = sim_match(home, away, want_scorers=True)
        res = "H" if hg>ag else "A" if ag>hg else "D"
        wdl[res] += 1; scores[res][(hg,ag)] += 1
        for tm, nm in sc: goals_for[(tm,nm)] += 1
    n = SIMS_PER_GAME
    pH, pD, pA = wdl["H"]/n, wdl["D"]/n, wdl["A"]/n
    pick = "home" if pH>=pD and pH>=pA else "away" if pA>=pD else "draw"
    conf = round(100*max(pH,pD,pA))
    bucket = {"home":"H","away":"A","draw":"D"}[pick]          # modal score within the predicted result
    (mh,ma),_ = scores[bucket].most_common(1)[0]
    top = goals_for.most_common(6)
    scorers = [{"team":tm,"name":nm,"pct":round(100*c/n)} for (tm,nm),c in top]
    game_results.append({
        "date":date,"group":g,"home":home,"away":away,"status":"SCHED",
        "pHome":round(pH,3),"pDraw":round(pD,3),"pAway":round(pA,3),
        "pick":pick,"conf":conf,"ps":f"{mh}–{ma}","scorers":scorers,
    })

# mark the Jun 14/15 games as TODAY for the dashboard
for gr in game_results:
    if gr["date"] in ("Sun Jun 14","Mon Jun 15"): gr["status"]="TODAY"

# ---------------------------------------------------------------------------
# 2) Full-tournament Monte Carlo: qualification % + title odds
# ---------------------------------------------------------------------------
print(f"Running {TOURNAMENT_SIMS:,} full-tournament simulations...")
played_by_group = defaultdict(list)
for _,g,h,a,hs,as_ in PLAYED: played_by_group[g].append((h,a,hs,as_))
remaining_by_group = defaultdict(list)
for _,g,h,a in REMAINING: remaining_by_group[g].append((h,a))

qualify = Counter(); win_grp = Counter()
champ = Counter(); finalist = Counter(); semi = Counter(); quarter = Counter()
pts_sum = Counter()
boot_goals = Counter()   # (team, player) -> total goals across all sims
boot_wins  = Counter()   # (team, player) -> times this player was a sim's top scorer

def attribute(team, n, tally):       # spread n known goals across a team's scorers
    for _ in range(n):
        nm = scorer(team)
        if nm != "Others": tally[(team, nm)] += 1

def rank_group(g, tally):
    pts = {t:0 for t in GROUPS[g]}; gd = {t:0 for t in GROUPS[g]}; gf = {t:0 for t in GROUPS[g]}
    def apply(h,a,hs,as_):
        gd[h]+=hs-as_; gd[a]+=as_-hs; gf[h]+=hs; gf[a]+=as_
        if hs>as_: pts[h]+=3
        elif as_>hs: pts[a]+=3
        else: pts[h]+=1; pts[a]+=1
    for h,a,hs,as_ in played_by_group[g]:
        apply(h,a,hs,as_); attribute(h,hs,tally); attribute(a,as_,tally)
    for h,a in remaining_by_group[g]:
        hg,ag,sc = sim_match(h,a,want_scorers=True); apply(h,a,hg,ag)
        for tm,nm in sc: tally[(tm,nm)] += 1
    order = sorted(GROUPS[g], key=lambda t:(pts[t],gd[t],gf[t],random.random()), reverse=True)
    for t in GROUPS[g]: pts_sum[t]+=pts[t]
    return order, pts, gd, gf

def ko_play(a, b, tally):
    hg, ag, sc = sim_match(a, b, want_scorers=True)
    for tm,nm in sc: tally[(tm,nm)] += 1
    if hg > ag: return a
    if ag > hg: return b
    pa = 0.5 + (RATINGS[a]-RATINGS[b]) / 4000.0          # penalties, slight edge
    return a if random.random() < min(0.75,max(0.25,pa)) else b

for _ in range(TOURNAMENT_SIMS):
    tally = Counter()
    winners=[]; runners=[]; thirds=[]
    for g in GROUPS:
        order,pts,gd,gf = rank_group(g, tally)
        winners.append(order[0]); runners.append(order[1])
        thirds.append((order[2], pts[order[2]], gd[order[2]], gf[order[2]]))
    best_thirds = [t for t,_,_,_ in sorted(thirds,key=lambda x:(x[1],x[2],x[3],random.random()),reverse=True)[:8]]
    field = winners+runners+best_thirds
    for t in winners: win_grp[t]+=1
    for t in field: qualify[t]+=1
    # seed by rating, standard single-elim bracket
    seeds = sorted(field, key=lambda t:RATINGS[t], reverse=True)
    round_teams = [(seeds[i], seeds[31-i]) for i in range(16)]
    r16 = [ko_play(a,b,tally) for a,b in round_teams]
    qf  = [ko_play(r16[i],r16[i+1],tally) for i in range(0,16,2)]
    for t in qf: quarter[t]+=1
    sf  = [ko_play(qf[i],qf[i+1],tally) for i in range(0,8,2)]
    for t in sf: semi[t]+=1
    fin = [ko_play(sf[0],sf[1],tally), ko_play(sf[2],sf[3],tally)]
    for t in fin: finalist[t]+=1
    champ[ko_play(fin[0],fin[1],tally)] += 1
    # golden boot: accumulate goals + credit this sim's leading scorer
    boot_goals.update(tally)
    if tally:
        top = max(tally.values())
        boot_wins[random.choice([k for k,v in tally.items() if v==top])] += 1

T = TOURNAMENT_SIMS
# expected standings per group (sorted by expected points)
standings = {}
for g in GROUPS:
    rows=[]
    for t in GROUPS[g]:
        q = qualify[t]/T
        rows.append([t, round(pts_sum[t]/T,1), round(100*q), round(100*win_grp[t]/T)])
    rows.sort(key=lambda r:(r[1], r[2]), reverse=True)
    standings[g]=rows

title = [[t, round(100*champ[t]/T,1), round(100*finalist[t]/T,1), round(100*semi[t]/T,1)]
         for t in sorted(champ, key=lambda t:champ[t], reverse=True)]

# Golden Boot race: expected goals + P(top scorer) per player
golden_boot = [[name, team, round(g/T,2), round(100*boot_wins[(team,name)]/T,1)]
               for (team,name),g in boot_goals.most_common(20)]

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
print("\n================  PER-GAME PREDICTIONS (sim-derived)  ================")
for gr in game_results:
    pk = "Draw" if gr["pick"]=="draw" else (gr["home"] if gr["pick"]=="home" else gr["away"])
    sc = ", ".join(f"{s['name']} {s['pct']}%" for s in gr["scorers"][:3])
    print(f"  [{gr['group']}] {gr['home']:>13} v {gr['away']:<13} -> {pk:<13} {gr['ps']}"
          f"  (H{round(gr['pHome']*100)}/D{round(gr['pDraw']*100)}/A{round(gr['pAway']*100)})  conf {gr['conf']}%  | scorers: {sc}")

print("\n================  PREDICTED GROUP TABLES (qualify %)  ================")
for g in sorted(standings):
    print(f"  Group {g}:")
    for i,(t,xp,q,w) in enumerate(standings[g]):
        tag = "WIN" if i==0 else "ADV" if i==1 else "   "
        print(f"     {i+1}. {t:<14} xPts {xp:<4} qualify {q:>3}%  winGrp {w:>3}%  {tag}")

print("\n================  TITLE ODDS (Monte Carlo)  ================")
for t,c,f,s in title[:16]:
    print(f"  {t:<14} win {c:>4}%   final {f:>4}%   semi {s:>4}%")

print("\n================  GOLDEN BOOT RACE (Monte Carlo)  ================")
for name,team,xg,p in golden_boot[:12]:
    print(f"  {name:<16} ({team:<13}) xGoals {xg:>4}   win boot {p:>4}%")

# ---------------------------------------------------------------------------
# Emit sim_results.js for the dashboard
# ---------------------------------------------------------------------------
SIM = {
 "generated": "2026-06-15 (Monte Carlo)",
 "sims_per_game": SIMS_PER_GAME, "tournament_sims": TOURNAMENT_SIMS,
 "played": [{"date":d,"group":g,"home":h,"away":a,"hs":hs,"as":as_,"status":"FT"}
            for d,g,h,a,hs,as_ in PLAYED],
 "games": game_results,
 "standings": standings,
 "title": title,
 "golden_boot": golden_boot,
}
with open("sim_results.js","w",encoding="utf-8") as f:
    f.write("window.SIM = " + json.dumps(SIM, ensure_ascii=False) + ";\n")
print("\nWrote sim_results.js  ->  load worldcup.html to see the dashboard.")
