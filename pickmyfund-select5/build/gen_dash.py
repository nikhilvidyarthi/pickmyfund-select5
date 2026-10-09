"""PickMyFund Select 5 – dashboard generator.
Reads sched.json (quarterly model holdings) + dash_static.json (current picks, sector table),
fetches daily NAVs from api.mfapi.in, writes india_rotation5.html (Artifact page body).
Usage: python3 gen_dash.py [outdir]"""
import json, sys, os, urllib.request, datetime as dt
import pandas as pd, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else HERE
sched = json.load(open(os.path.join(HERE, 'sched.json')))
stat = json.load(open(os.path.join(HERE, 'dash_static.json')))
BENCH = {'n50': 100822, 'n500': 147626}

def nav(code):
    for _ in range(3):
        try:
            d = json.load(urllib.request.urlopen(f'https://api.mfapi.in/mf/{code}', timeout=40))
            s = pd.Series([float(x['nav']) for x in d['data']],
                          index=pd.to_datetime([x['date'] for x in d['data']], format='%d-%m-%Y')).sort_index()
            s = s[~s.index.duplicated()]
            return s[s > 0], d['meta']
        except Exception as e:
            err = e
    raise err

codes = sorted({f['code'] for q in sched for f in q['funds']} | {f['code'] for f in stat['fresh']} | set(BENCH.values()))
S, META = {}, {}
for c in codes:
    S[c], META[c] = nav(c)
start = pd.Timestamp(sched[0]['date'])
idx = pd.bdate_range(start, max(s.index[-1] for s in S.values()))
P = pd.DataFrame({c: S[c].reindex(S[c].index.union(idx)).ffill().reindex(idx) for c in codes})
last = max(S[c].index[-1] for c in codes)
P = P.loc[:last]

# --- model book: equal weight at each quarterly rebalance, 1% exit load on active funds held < 365 days
val, path, entry, qrows = 1.0, [], {}, []
rebs = [pd.Timestamp(q['date']) for q in sched]
for qi, q in enumerate(sched):
    d0 = rebs[qi]; d1 = rebs[qi + 1] if qi + 1 < len(rebs) else P.index[-1] + pd.Timedelta(days=1)
    funds = [f['code'] for f in q['funds']]
    if qi > 0:
        prev = [f['code'] for f in sched[qi - 1]['funds']]
        cost = 0.0
        for c in prev:
            if c not in funds and (d0 - entry[c]).days < 365 and 'Index' not in META[c]['scheme_name']:
                cost += wts_end.get(c, 0) * 0.01
        val *= 1 - cost
    for c in funds:
        if c not in entry or (qi > 0 and c not in [f['code'] for f in sched[qi - 1]['funds']]):
            entry[c] = d0
    base = P.loc[P.index >= d0].iloc[0][funds]
    seg = P.loc[(P.index >= d0) & (P.index < d1), funds]
    rel = seg.div(base)
    v = val * rel.mean(axis=1)
    path.append(v)
    wts_end = (rel.iloc[-1] / rel.iloc[-1].sum()).to_dict()
    qstart_val = val
    val = float(v.iloc[-1])
    qrows.append(dict(q=q['date'], sectors=q['sectors'], offshore=q.get('offshore'), funds=q['funds'], ret=val / qstart_val - 1,
                      fund_ret={str(c): float(rel.iloc[-1][c] - 1) for c in funds},
                      end=str(seg.index[-1].date())))
model = pd.concat(path)
model = model[~model.index.duplicated(keep='last')]
bn = {k: P[c] / P[c].iloc[0] for k, c in BENCH.items()}
for r in qrows:
    a, b = pd.Timestamp(r['q']), pd.Timestamp(r['end'])
    for k in bn:
        s = bn[k]; r[k] = float(s.loc[:b].iloc[-1] / s.loc[s.index >= a].iloc[0] - 1)

def stats(s):
    s = s.dropna()
    return dict(total=float(s.iloc[-1] / s.iloc[0] - 1), mdd=float((s / s.cummax() - 1).min()))
k_model, k50, k500 = stats(model), stats(bn['n50']), stats(bn['n500'])
d_last, d_prev = model.index[-1], model.index[-2]
day = float(model.iloc[-1] / model.iloc[-2] - 1)
qtd = qrows[-1]['ret']

# current model holdings
cur = sched[-1]
qb = P.loc[P.index >= pd.Timestamp(cur['date'])].iloc[0]
hold = []
rel_now = {f['code']: float(P[f['code']].iloc[-1] / qb[f['code']]) for f in cur['funds']}
tot = sum(rel_now.values())
for f in cur['funds']:
    c = f['code']; s = S[c]
    hold.append(dict(name=META[c]['scheme_name'], role=f['role'], theme=f['theme'], nav=float(s.iloc[-1]),
                     navdate=s.index[-1].strftime('%d %b'), d1=float(s.iloc[-1] / s.iloc[-2] - 1),
                     qtd=rel_now[c] - 1, w=rel_now[c] / tot))
fresh = []
for f in stat['fresh']:
    c = f['code']; s = S[c]
    y = s.loc[:s.index[-1] - pd.Timedelta(days=365)]
    fresh.append(dict(name=META[c]['scheme_name'], role=f['role'], group=f['group'], aum=f['aum'], ter=f['ter'],
                      nav=float(s.iloc[-1]), navdate=s.index[-1].strftime('%d %b'), d1=float(s.iloc[-1] / s.iloc[-2] - 1),
                      y1=float(s.iloc[-1] / y.iloc[-1] - 1) if len(y) else None))
series = dict(dates=[d.strftime('%Y-%m-%d') for d in model.index],
              model=[round(float(x) * 100, 3) for x in model.values],
              n50=[round(float(x) * 100, 3) for x in bn['n50'].reindex(model.index).values],
              n500=[round(float(x) * 100, 3) for x in bn['n500'].reindex(model.index).values])
DATA = dict(updated=dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).strftime('%d %b %Y, %H:%M IST'),
            navdate=d_last.strftime('%d %b %Y'), start=start.strftime('%d %b %Y'),
            k=dict(model=k_model, n50=k50, n500=k500, day=day, qtd=qtd),
            series=series, quarters=qrows, hold=hold, fresh=fresh, sectors=stat['sectors'], sect_asof=stat['asof'],
            regions=stat.get('regions'), arb6=stat.get('arb6'), closed_note=stat.get('closed_note'),
            names={str(c): META[c]['scheme_name'] for c in codes})
tpl = open(os.path.join(HERE, 'dash_template.html')).read()
html = tpl.replace('/*__DATA__*/null', json.dumps(DATA, separators=(',', ':')))
open(os.path.join(OUT, 'india_rotation5.html'), 'w').write(html)

# standalone copy for Netlify (full HTML document)
FAV = "data:image/svg+xml," + __import__('urllib.parse').parse.quote('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 140 140"><rect width="140" height="140" rx="28" fill="#0A1517"/><g transform="translate(6,4)"><path d="M14 22 C14 12 22 6 31 11 L110 55 C119 60 119 72 110 77 L31 121 C22 126 14 120 14 110 Z" fill="none" stroke="#C9A44C" stroke-width="8" stroke-linejoin="round"/><rect x="27" y="74" width="12" height="18" rx="2" fill="#C9A44C"/><rect x="45" y="61" width="12" height="31" rx="2" fill="#C9A44C"/><rect x="63" y="48" width="12" height="44" rx="2" fill="#C9A44C"/></g></svg>')
head = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        '<meta name="robots" content="noindex,nofollow">'
        f'<link rel="icon" href="{FAV}">'
        '<style>:root{box-sizing:border-box}body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>'
        '</head><body>')
os.makedirs(os.path.join(OUT, 'netlify'), exist_ok=True)
open(os.path.join(OUT, 'netlify', 'index.html'), 'w').write(head + html + '</body></html>')
print('model', k_model, 'n50', k50, 'n500', k500, 'day', day, 'qtd', qtd, 'nav date', d_last.date())
