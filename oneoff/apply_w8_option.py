"""Owner 2026-10-27 19:43: «просто воспроизводимость существующих симуляций через манифест с фронта», nothing new on the surfaces.
Replaces ONLY the materialize option on column w8_vote (the not-calculable placeholder) in the manifests of the EMA200 w8v8 and EMA100 v7
surfaces by w8_vote_option.json: one weighted_vote_setup whose gates read the row's w8_vote value: 7 = v7 simulation, 8 = v8 simulation
(curves, exponents, theta 1.75 from the simulations), 6 = rejected by the Engine. runs.csv and everything else untouched.
manifest.json edited IN PLACE (same inode), backup manifest.pre_w8opt_<ts>.json. Then asks Research 8095 calculate-plan for one row per
w8_vote value (read-only). Usage: python3 apply_w8_option.py <analysis dir> [--dry]"""
import sys, os, csv, json, shutil, datetime as dt, urllib.request
AN = sys.argv[1]; DRY = '--dry' in sys.argv; TS = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
OPT = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'w8_vote_option.json'), encoding='utf-8'))
SURF = [(tk, 'ema200', 'width_x_untouched_x_stop_x_ratio_x_touch_x_w8v8_6d') for tk in ('BTCUSDT.P', 'ETHUSDT.P', 'SOLUSDT.P')] + \
       [(tk, 'ema100', 'width_x_untouched_x_stop_x_ratio_x_touch_x_v7_6d') for tk in ('BTCUSDT.P', 'ETHUSDT.P', 'SOLUSDT.P')]
def plan(M, d):
    dims = M['result_schema']['dimensions']; req = []
    with open(f'{d}/runs.csv', newline='', encoding='utf-8') as fh: rows = list(csv.DictReader(fh))
    for want in ('', '6', '7', '8'):
        cand = [r for r in rows if r.get('w8_vote', '') == want and not r['candidate_id'].endswith('-tr')]
        if cand:
            r = cand[len(cand) // 2]; req.append({'coords': {x['id']: float(r[x['column']]) for x in dims if r.get(x['column'], '') != ''}})
    q = urllib.request.Request(f"http://127.0.0.1:8095/api/research/experiments/{M['experiment_id']}/runs/calculate-plan",
                               data=json.dumps({'rows': req}).encode(), headers={'Content-Type': 'application/json'})
    try: out = json.loads(urllib.request.urlopen(q, timeout=180).read())
    except Exception as e: out = {'error': str(e), 'body': getattr(e, 'read', lambda: b'')()[:800].decode('utf-8', 'replace')}
    print('  PLAN', M['experiment_id'], json.dumps(req, ensure_ascii=False), json.dumps(out, ensure_ascii=False)[:2500], flush=True)
for tk, ema, test in SURF:
    d = f'{AN}/{tk}/{ema}/{test}'; p = f'{d}/manifest.json'
    if not os.path.isfile(p): print('MISSING', d, flush=True); continue
    M = json.load(open(p, encoding='utf-8')); opts = M['materialize']['options']
    j = [k for k, o in enumerate(opts) if o['column'] == 'w8_vote']; assert len(j) == 1, [o['id'] for o in opts]
    dim = [x for x in M['result_schema']['dimensions'] if x.get('column') == 'w8_vote']
    print(tk, ema, M['experiment_id'], 'options', [(o['id'], o['insert']['item'].get('component_id')) for o in opts], 'w8_vote dim', dim, flush=True)
    if opts[j[0]]['insert']['item'].get('component_id') == 'weighted_vote_setup': print('  ALREADY DONE'); plan(M, d); continue
    opts[j[0]] = OPT
    M.setdefault('history', []).append({'at': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
        'event': 'w8_vote option calculable: one weighted_vote_setup with simulation curves/exponents/theta 1.75; row value 7 = v7, 8 = v8, 6 rejected by Engine (premium voter); rows unchanged'})
    s = json.dumps(M, indent=2, ensure_ascii=False); json.loads(s)
    if DRY: print('  dry: new size', len(s.encode()), 'old', os.path.getsize(p)); continue
    shutil.copy2(p, f'{d}/manifest.pre_w8opt_{TS}.json'); ino = os.stat(p).st_ino
    with open(p, 'r+', encoding='utf-8') as fh: fh.seek(0); fh.write(s); fh.truncate()
    assert os.stat(p).st_ino == ino; json.load(open(p, encoding='utf-8'))
    print('  written', os.path.getsize(p), flush=True); plan(M, d)
