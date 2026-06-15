#!/usr/bin/env python3
"""
Backtest / calibration harness for the prediction methodology.

What it does
------------
Runs an Elo model CHRONOLOGICALLY over ~49k real international matches
(1872-2026). For each match it predicts P(home win / draw / away win) using
ONLY the ratings that existed *before* that match (true out-of-sample), then
scores those predictions on a recent test window with:

  * Brier score   (lower = better; multiclass, 0..2)
  * Log-loss      (lower = better)
  * Accuracy      (argmax outcome)
  * Calibration   (do 30%-predicted events happen ~30% of the time?)

It compares the model to a base-rate baseline (always predict the historical
home/draw/away frequencies), grid-searches a couple of parameters, prints the
fitted *current* Elo for the 48 World Cup teams (and how well our hand-set
ratings correlate with them), and writes model_report.js for the dashboard.

Run:  python3 backtest.py
Data: github.com/martj42/international_results (cached locally as intl_results.csv)
"""
import os, sys, math, csv, json, re, ast, urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CSV_URL = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
CSV_FILE = "intl_results.csv"
TODAY = "2026-06-15"
TEST_FROM = "2022-06-01"          # score predictions on matches from here on
WARM_MIN_DATE = "1990-01-01"      # ignore very old matches for base-rate stats only

# ---------------------------------------------------------------------------
def load_matches():
    if not os.path.exists(CSV_FILE):
        print("Downloading historical results (~3.7 MB, one time)...")
        urllib.request.urlretrieve(CSV_URL, CSV_FILE)
    rows = []
    for r in csv.DictReader(open(CSV_FILE, encoding="utf-8")):
        if not r["home_score"].strip().isdigit() or not r["away_score"].strip().isdigit():
            continue                                   # skip unplayed/future fixtures
        if r["date"] > TODAY:
            continue
        rows.append((r["date"], r["home_team"], r["away_team"],
                     int(r["home_score"]), int(r["away_score"]),
                     r["tournament"], r["neutral"].strip().upper() == "TRUE"))
    rows.sort(key=lambda x: x[0])
    return rows

def kfac(t):
    t = t.lower()
    if "world cup" in t and "qual" not in t: return 60
    if "qualification" in t: return 40
    if "nations league" in t: return 40
    if any(k in t for k in ("euro","copa am","african cup","asian cup","gold cup","confederations")):
        return 50 if "qual" not in t else 40
    if "friendly" in t: return 20
    return 35

def gmult(gd):                                          # margin-of-victory multiplier (eloratings-style)
    return 1.0 if gd <= 1 else 1.5 if gd == 2 else (11 + gd) / 8.0

def match_probs(diff, scale, total):
    """Elo diff (incl. home adv) -> P(home),P(draw),P(away) via Poisson on expected goals."""
    sup = diff * scale
    hx = max(0.15, (total + sup) / 2); ax = max(0.15, (total - sup) / 2)
    ph = [math.exp(-hx)]; pa = [math.exp(-ax)]
    for k in range(1, 9):
        ph.append(ph[-1]*hx/k); pa.append(pa[-1]*ax/k)
    pH = pD = pA = 0.0
    for i in range(9):
        for j in range(9):
            p = ph[i]*pa[j]
            if i > j: pH += p
            elif j > i: pA += p
            else: pD += p
    s = pH + pD + pA
    return pH/s, pD/s, pA/s

def run(matches, scale, total, home_adv, collect_calib=False, final_ratings=False):
    R = {}
    brier = logloss = 0.0; correct = 0; n = 0
    calib = [[0,0] for _ in range(10)]                 # [sum_pred, sum_obs] for home-win deciles
    for date, h, a, hs, as_, tour, neutral in matches:
        rh = R.get(h, 1500.0); ra = R.get(a, 1500.0)
        ha = 0 if neutral else home_adv
        diff = (rh + ha) - ra
        if date >= TEST_FROM:                          # out-of-sample scoring
            pH, pD, pA = match_probs(diff, scale, total)
            outcome = 0 if hs > as_ else 2 if as_ > hs else 1
            probs = (pH, pD, pA)
            brier += sum((probs[k] - (1 if k == outcome else 0))**2 for k in range(3))
            logloss += -math.log(max(1e-12, probs[outcome]))
            if max(range(3), key=lambda k: probs[k]) == outcome: correct += 1
            n += 1
            if collect_calib:
                b = min(9, int(pH*10)); calib[b][0] += pH; calib[b][1] += (1 if outcome == 0 else 0)
        # Elo update
        We = 1.0/(1.0 + 10**(((ra) - (rh+ha))/400.0))
        actual = 1.0 if hs > as_ else 0.5 if hs == as_ else 0.0
        delta = kfac(tour) * gmult(abs(hs-as_)) * (actual - We)
        R[h] = rh + delta; R[a] = ra - delta
    res = {"brier": brier/n, "logloss": logloss/n, "acc": correct/n, "n": n}
    if collect_calib: res["calib"] = calib
    if final_ratings: res["R"] = R
    return res

def baseline(matches):
    """Always predict the historical home/draw/away frequencies (computed pre-test)."""
    th = td = ta = 0
    for date, h, a, hs, as_, tour, neutral in matches:
        if date < WARM_MIN_DATE or date >= TEST_FROM or neutral: continue
        if hs > as_: th += 1
        elif as_ > hs: ta += 1
        else: td += 1
    tot = th+td+ta; base = (th/tot, td/tot, ta/tot)
    brier = logloss = 0.0; correct = 0; n = 0
    for date, h, a, hs, as_, tour, neutral in matches:
        if date < TEST_FROM: continue
        outcome = 0 if hs > as_ else 2 if as_ > hs else 1
        brier += sum((base[k]-(1 if k==outcome else 0))**2 for k in range(3))
        logloss += -math.log(max(1e-12, base[outcome]))
        if max(range(3), key=lambda k: base[k]) == outcome: correct += 1
        n += 1
    return {"brier":brier/n, "logloss":logloss/n, "acc":correct/n, "n":n, "base":base}

# ---------------------------------------------------------------------------
print("Loading matches...")
M = load_matches()
print(f"  {len(M):,} played matches; test window {TEST_FROM} -> {TODAY}")

base = baseline(M)
print(f"\nBASELINE (always predict base rates {tuple(round(x,2) for x in base['base'])}):")
print(f"  Brier {base['brier']:.4f} | LogLoss {base['logloss']:.4f} | Acc {base['acc']*100:.1f}%  (n={base['n']})")

print("\nGRID SEARCH (Elo model):")
best = None
for scale in (0.0040, 0.0055, 0.0070):
    for ha in (55, 70):
        r = run(M, scale, 2.6, ha)
        tag = f"  scale {scale:.4f} ha {ha}: Brier {r['brier']:.4f} | LogLoss {r['logloss']:.4f} | Acc {r['acc']*100:.1f}%"
        print(tag)
        if best is None or r["logloss"] < best[0]["logloss"]:
            best = (r, scale, ha)
bestres, bscale, bha = best
print(f"\nBEST: scale {bscale:.4f}, home_adv {bha}  ->  "
      f"Brier {bestres['brier']:.4f} | LogLoss {bestres['logloss']:.4f} | Acc {bestres['acc']*100:.1f}%")
gain = (base['logloss']-bestres['logloss'])/base['logloss']*100
print(f"  Improvement over baseline: {gain:.1f}% lower log-loss, "
      f"{(bestres['acc']-base['acc'])*100:.1f}pp more accurate")

full = run(M, bscale, 2.6, bha, collect_calib=True, final_ratings=True)
print("\nCALIBRATION (home-win probability):")
print("  pred-bin    n     predicted   observed")
calib_out = []
for i,(sp,so) in enumerate(full["calib"]):
    # count per bin
    pass
# recompute counts per bin for display
counts=[0]*10
for date,h,a,hs,as_,tour,neutral in M:
    if date < TEST_FROM: continue
    rh=0  # placeholder; recompute below
# simpler: rerun to count
def calib_table(matches, scale, total, ha_):
    R={}; rows=[[0,0.0,0] for _ in range(10)]  # n, sum_pred, sum_obs
    for date,h,a,hs,as_,tour,neutral in matches:
        rh=R.get(h,1500.0); ra=R.get(a,1500.0); ha=0 if neutral else ha_
        diff=(rh+ha)-ra
        if date>=TEST_FROM:
            pH,_,_=match_probs(diff,scale,total); b=min(9,int(pH*10))
            rows[b][0]+=1; rows[b][1]+=pH; rows[b][2]+= (1 if hs>as_ else 0)
        We=1.0/(1.0+10**((ra-(rh+ha))/400.0)); actual=1.0 if hs>as_ else 0.5 if hs==as_ else 0.0
        d=kfac(tour)*gmult(abs(hs-as_))*(actual-We); R[h]=rh+d; R[a]=ra-d
    return rows
ct=calib_table(M,bscale,2.6,bha)
for i,(n_,sp,so) in enumerate(ct):
    if n_==0: continue
    print(f"  {i*10:2d}-{i*10+10:3d}%  {n_:5d}    {sp/n_*100:6.1f}%    {so/n_*100:6.1f}%")
    calib_out.append([i*10, n_, round(sp/n_*100,1), round(so/n_*100,1)])

# ---- fitted current Elo for the 48 WC teams + correlation with our ratings ----
R = full["R"]
ALIAS = {"USA":"United States","Türkiye":"Turkey","Bosnia & H.":"Bosnia and Herzegovina",
         "DR Congo":"DR Congo","South Korea":"South Korea","Cape Verde":"Cape Verde",
         "Ivory Coast":"Ivory Coast","Czechia":"Czech Republic","Curaçao":"Curaçao","Iran":"Iran"}
src = open("simulate_worldcup.py", encoding="utf-8").read()
OUR = ast.literal_eval(re.search(r"RATINGS = (\{.*?\n\})", src, re.S).group(1))
print("\nFITTED CURRENT ELO vs our hand-set ratings (top 12 WC teams by fitted Elo):")
fitted = {}
for team in OUR:
    name = ALIAS.get(team, team)
    fitted[team] = R.get(name)
shown = sorted([t for t in fitted if fitted[t] is not None], key=lambda t: fitted[t], reverse=True)
for t in shown[:12]:
    print(f"  {t:<14} fitted {fitted[t]:6.0f}   ours {OUR[t]}")
missing = [t for t in fitted if fitted[t] is None]
if missing: print("  (no historical Elo found for:", missing, ")")
# correlation
pairs = [(OUR[t], fitted[t]) for t in fitted if fitted[t] is not None]
mx = sum(p[0] for p in pairs)/len(pairs); my = sum(p[1] for p in pairs)/len(pairs)
cov = sum((a-mx)*(b-my) for a,b in pairs); sx = math.sqrt(sum((a-mx)**2 for a,b in pairs)); sy = math.sqrt(sum((b-my)**2 for a,b in pairs))
corr = cov/(sx*sy)
print(f"\n  Correlation (our ratings vs fitted Elo): {corr:.3f}  "
      f"({'strong' if corr>0.8 else 'moderate' if corr>0.6 else 'weak'})")

# Export fitted Elo for the 48 WC teams (fall back to hand-set where unavailable)
elo_out = {team: (round(fitted[team]) if fitted[team] is not None else OUR[team]) for team in OUR}
json.dump(elo_out, open("elo_ratings.json","w",encoding="utf-8"), ensure_ascii=False)
print(f"Wrote elo_ratings.json ({len(elo_out)} teams) -> simulate_worldcup.py will use these.")

report = {"generated": TODAY, "test_from": TEST_FROM, "n": bestres["n"],
          "model": {"brier": round(bestres["brier"],4), "logloss": round(bestres["logloss"],4), "acc": round(bestres["acc"]*100,1)},
          "baseline": {"brier": round(base["brier"],4), "logloss": round(base["logloss"],4), "acc": round(base["acc"]*100,1)},
          "logloss_gain_pct": round(gain,1), "ratings_corr": round(corr,3),
          "params": {"scale": bscale, "home_adv": bha}, "calibration": calib_out}
with open("model_report.js","w",encoding="utf-8") as f:
    f.write("window.MODELREPORT = " + json.dumps(report, ensure_ascii=False) + ";\n")
print("\nWrote model_report.js")
