"""Owner 2026-10-27 19:43 «просто воспроизводимость существующих симуляций через манифест с фронта»; 19:50 only manifests, no code; nothing new on the surfaces.
Manifest-only edit of the EMA200 w8v8 and EMA100 v7 surfaces (runs.csv untouched):
 1) the option on column w8_vote (placeholder) -> w8_vote_option.json: one weighted_vote_setup whose gates read the row's w8_vote value:
    7 = v7 simulation vote, 8 = v8 simulation vote (curves, exponents, theta 1.75 from the simulations), 6 = rejected by the Engine (premium voter).
 2) EMA200 only (column trail exists there, no option yet): the trail checkbox as on EMA500 v3vote_x_exits_6d (adx_rule + adx_trail), both options on
    column trail (trail_options.json): phase rule 1h ADX(14) rise since entry >= 1.75 with DI on the trade's side -> runner; runner stop
    initial_r_trailing_stop trigger 0.25R / distance 0.25R (simulation surf/trail/trail_out.py: DELTA 1.75, DIST 0.25). Needs template
    exit_management = managed with empty lists and research_policy.managed_policy_enabled = true (as on the EMA500 exits surface).
manifest.json edited IN PLACE (same inode), backup manifest.pre_w8opt_<ts>.json. Then Research 8095 calculate-plan for one row per
w8_vote value x touch x trail (read-only). Usage: python3 apply_w8_option.py <analysis dir> [--dry]"""
import sys, os, csv, json, shutil, datetime as dt, urllib.request, itertools
AN = sys.argv[1]; DRY = '--dry' in sys.argv; TS = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ'); HERE = os.path.dirname(os.path.abspath(__file__))
OPT = json.load(open(f'{HERE}/w8_vote_option.json', encoding='utf-8')); TRAIL = json.load(open(f'{HERE}/trail_options.json', encoding='utf-8'))
MANAGED = {'mode': 'managed', 'phase_rules': [], 'runtime_exits': [], 'stop_management': [], 'take_management': []}
SURF = [(tk, 'ema200', 'width_x_untouched_x_stop_x_ratio_x_touch_x_w8v8_6d') for tk in ('BTCUSDT.P', 'ETHUSDT.P', 'SOLUSDT.P')] + \
       [(tk, 'ema100', 'width_x_untouched_x_stop_x_ratio_x_touch_x_v7_6d') for tk in ('BTCUSDT.P', 'ETHUSDT.P', 'SOLUSDT.P')]
def plan(M, d):
    dims = M['result_schema']['dimensions']; req = []; seen = set()
    with open(f'{d}/runs.csv', newline='', encoding='utf-8') as fh:
        for r in csv.DictReader(fh):
            key = (r.get('w8_vote', ''), r.get('touch_max', ''), r.get('trail', ''))
            if key in seen or r.get('sl_atr_multiplier') not in ('4.5', '4.75', '5', '5.0', '6', '6.0'): continue
            seen.add(key); req.append({'coords': {x['id']: float(r[x['column']]) for x in dims if r.get(x['column'], '') != ''}})
    q = urllib.request.Request(f"http://127.0.0.1:8095/api/research/experiments/{M['experiment_id']}/runs/calculate-plan",
                               data=json.dumps({'rows': req}).encode(), headers={'Content-Type': 'application/json'})
    try: out = json.loads(urllib.request.urlopen(q, timeout=300).read())
    except Exception as e: out = {'error': str(e), 'body': getattr(e, 'read', lambda: b'')()[:800].decode('utf-8', 'replace')}
    print('  PLAN', M['experiment_id'], len(req), 'rows', json.dumps(req, ensure_ascii=False), flush=True)
    print('  PLAN RESULT', json.dumps(out, ensure_ascii=False)[:6000], flush=True)
for tk, ema, test in SURF:
    d = f'{AN}/{tk}/{ema}/{test}'; p = f'{d}/manifest.json'
    if not os.path.isfile(p): print('MISSING', d, flush=True); continue
    M = json.load(open(p, encoding='utf-8')); mt = M['materialize']; opts = mt['options']; tm = mt['strategy_template']['raw_spec']['trade_management']
    j = [k for k, o in enumerate(opts) if o['column'] == 'w8_vote']; assert len(j) == 1, [o['id'] for o in opts]
    has_trail = any(x.get('column') == 'trail' for x in M['result_schema']['dimensions'])
    print(tk, ema, M['experiment_id'], 'options', [(o['id'], o['insert']['item'].get('component_id')) for o in opts], 'trail dim', has_trail,
          'exit_management', tm.get('exit_management'), 'managed_policy_enabled', mt['research_policy'].get('managed_policy_enabled'), flush=True)
    if opts[j[0]]['insert']['item'].get('component_id') == 'weighted_vote_setup': print('  ALREADY DONE'); plan(M, d); continue
    opts[j[0]] = OPT
    if has_trail:
        assert not tm.get('exit_management'), tm.get('exit_management')
        tm['exit_management'] = json.loads(json.dumps(MANAGED)); mt['research_policy']['managed_policy_enabled'] = True
        assert not any(o['column'] == 'trail' for o in opts); opts.extend(TRAIL)
    M.setdefault('history', []).append({'at': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
        'event': 'calculable: w8_vote option = simulation votes by row value (7 = v7, 8 = v8, 6 rejected)' + ('; trail option = 1h ADX rise >= 1.75 + DI -> runner, trail 0.25R (as EMA500 exits)' if has_trail else '') + '; rows unchanged'})
    s = json.dumps(M, indent=2, ensure_ascii=False); json.loads(s)
    if DRY: print('  dry: new size', len(s.encode()), 'old', os.path.getsize(p)); continue
    shutil.copy2(p, f'{d}/manifest.pre_w8opt_{TS}.json'); ino = os.stat(p).st_ino
    with open(p, 'r+', encoding='utf-8') as fh: fh.seek(0); fh.write(s); fh.truncate()
    assert os.stat(p).st_ino == ino; json.load(open(p, encoding='utf-8'))
    print('  written', os.path.getsize(p), flush=True); plan(M, d)
