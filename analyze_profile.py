import csv
p = r'D:\Users\lzl_k\PycharmProjects\backtrader\results\v5_profile_full.csv'
with open(p, 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

FEATURES = ['daily_vol','annual_vol','atr_pct','hl_ratio','above_sma120_pct',
    'trend_slope','up_day_ratio','macd_pos_pct','macd_histo_mean',
    'macd_histo_std','macd_cross_freq','avg_volume_m','volume_cv',
    'max_dd','price_range','price_position']

def corr(xs, ys):
    n = len(xs)
    mx = sum(xs)/n; my = sum(ys)/n
    sx = (sum((x-mx)**2 for x in xs)/n)**0.5
    sy = (sum((y-my)**2 for y in ys)/n)**0.5
    if sx==0 or sy==0: return 0
    return sum((x-mx)*(y-my) for x,y in zip(xs,ys))/(n*sx*sy)

v5 = [float(r['v5_return']) for r in rows]
bh = [float(r['bh_return']) for r in rows]

print('=== Correlations with v5_return ===')
corrs = []
for c in FEATURES:
    vals = [float(r[c]) for r in rows]
    c_v5 = corr(vals, v5)
    c_bh = corr(vals, bh)
    corrs.append((c, c_v5, c_bh))
corrs.sort(key=lambda x: -abs(x[1]))
for name, cv, cb in corrs:
    bar = '+'*max(0,int(cv*20)) if cv>0 else '-'*max(0,int(-cv*20))
    print('  %-24s v5_r=%+.3f %s  bh_r=%+.3f' % (name, cv, bar, cb))

print()
print('=== Top 15 v5 ===')
sr = sorted(rows, key=lambda r: -float(r['v5_return']))
for r in sr[:15]:
    v = float(r['v5_return']); b = float(r['bh_return'])
    print('  %s %-10s %-12s BH:%+7.1f%% V5:%+7.1f%%' % (r['code'], r['name'], r['group'], b, v))

print()
print('=== Bottom 15 v5 ===')
for r in sr[-15:]:
    v = float(r['v5_return']); b = float(r['bh_return'])
    print('  %s %-10s %-12s BH:%+7.1f%% V5:%+7.1f%%' % (r['code'], r['name'], r['group'], b, v))

print()
print('=== Sector analysis ===')
groups = {}
for r in rows:
    g = r['group']
    if g not in groups: groups[g] = []
    groups[g].append(float(r['v5_return']))
for g in sorted(groups.keys()):
    vals = groups[g]
    print('  %-15s n=%2d  mean=%+6.1f%%  median=%+6.1f%%  min=%+7.1f%%  max=%+7.1f%%' % (
        g, len(vals), sum(vals)/len(vals),
        sorted(vals)[len(vals)//2], min(vals), max(vals)))

print()
print('=== v5 vs BH quadrant ===')
q = {'v5+BH+':0, 'v5+BH-':0, 'v5-BH+':0, 'v5-BH-':0}
for r in rows:
    v = float(r['v5_return']); b = float(r['bh_return'])
    if v>0 and b>0: q['v5+BH+'] += 1
    if v>0 and b<=0: q['v5+BH-'] += 1
    if v<=0 and b>0: q['v5-BH+'] += 1
    if v<=0 and b<=0: q['v5-BH-'] += 1
for k, n in q.items():
    print('  %s: %d' % (k, n))
