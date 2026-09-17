"""Frozen legacy stage logic. No imports, I/O or execution services.
Original app.py SHA256: 0d376fa780d8469eb6d297ace31e8f845b89646e672d06c41bf33aa2c285b81b
Only change: feature reader injected explicitly. Not the full seed/linkage engine.
"""
def _num(v, default=0.0):
    try:
        if v is None or v == '':
            return default
        return float(v)
    except Exception:
        return default

def _intraday_prev_risks(prev_daily):
    risks=[]
    if not prev_daily:
        return ['前日K线缺失']
    pct = _num(prev_daily.get('pct_chg'))
    op = _num(prev_daily.get('open'))
    hi = _num(prev_daily.get('high'))
    close = _num(prev_daily.get('close'))
    low = _num(prev_daily.get('low'))
    if pct >= 9.2:
        risks.append('前日接近涨停/过热')
    if pct <= -3:
        risks.append('前日弱势')
    if hi and close and hi > close * 1.045:
        risks.append('前日冲高回落')
    if op and close and close < op and pct < 1:
        risks.append('前日开收弱')
    if hi and low and close and (hi-low)/max(close,0.01)*100 > 12:
        risks.append('前日宽幅震荡')
    return risks

def _intraday_stage_status(row, prev_daily, stage, feature_reader):
    jjzf = _num(row.get('jjzf'))
    prev_risks = _intraday_prev_risks(prev_daily)
    hard_prev = any(x in prev_risks for x in ['前日弱势','前日冲高回落','前日开收弱'])
    if stage == '925':
        status = '观察'
        reason = '竞价强度进入观察池；09:26只观察，不直接买入'
        risks = list(prev_risks)
        if jjzf > 5.5:
            risks.append('竞价偏高')
        if hard_prev:
            status = '只观察'
        return status, reason, risks, None
    # 早盘强票窗口前移：不再等到 9:45/10:00 才给出结论。
    # stage=945 保留旧字段名做兼容，但语义改为 09:31 第一确认/轻仓试错窗口。
    f945 = feature_reader(row.get('code'), row.get('date'), '09:31', prev_close=_num(prev_daily.get('close') if prev_daily else 0))
    if stage == '945':
        risks = list(prev_risks)
        if not f945:
            return '只观察', '缺少09:31本地/实时分时，不能升级早确认池', risks + ['无足够09:31分时'], f945
        if f945['endPct'] < -0.2:
            risks.append('09:31未站稳开盘价')
        if f945['lowPct'] < -1.8:
            risks.append('09:31下探过深')
        if not f945['aboveAvg']:
            risks.append('09:31未站均价线')
        if jjzf > 6.2:
            risks.append('竞价接近过热')
        if f945['highPct'] >= 5.8 and f945['endPct'] < f945['highPct'] - 2.2:
            risks.append('早盘冲高回落')
        # 主线低开强反包：相对昨收已经 +2% 且站均价线，09:31 即可视为承接通过
        live_strong_945 = _num(f945.get('pctVsPrev')) >= 2.0 and f945.get('aboveAvg')
        if live_strong_945:
            return '早确认池', '09:31相对昨收已强反包+均线站稳，主线低开修复型确认', risks or ['低开修复型，需09:36/09:40继续验证'], f945
        hard = hard_prev or f945['endPct'] < -0.2 or f945['lowPct'] < -1.8 or (not f945['aboveAvg']) or jjzf > 6.2 or ('早盘冲高回落' in risks)
        if hard:
            return '淘汰/不买', '09:31早确认未通过，降级观察或放弃', risks, f945
        return '早确认池', '09:31承接通过；可进入轻仓试错讨论，错了快撤，不等到后面追高', risks or ['暂无硬风险'], f945
    # stage=1000 保留旧字段名做兼容，但语义改为 09:40 加仓确认/加仓窗口。
    f1000 = feature_reader(row.get('code'), row.get('date'), '09:40', prev_close=_num(prev_daily.get('close') if prev_daily else 0))
    status945, _, risks945, _ = _intraday_stage_status(row, prev_daily, '945', feature_reader)
    risks = list(risks945 or [])
    early_missed = status945 != '早确认池'
    # 09:31 是“早确认/先手窗口”，不能一票否决。
    # 例如先下探再拉回的票，09:31 未站稳但 09:40 已重新站回开盘/均线，应允许从观察池升级到加仓确认池。
    if early_missed:
        risks.append('09:31未通过但允许09:40修复确认')
    if not f1000:
        return '只观察', '缺少09:40本地/实时分时，不能升级加仓确认池', risks + ['无足够09:40分时'], f1000
    if jjzf > 5.8:
        risks.append('竞价偏高，加仓确认不追')
    live_repair = _num(f1000.get('pctVsPrev')) >= 3.0 and f1000.get('aboveAvg')
    if f1000['endPct'] < 0.5 and not live_repair:
        risks.append('09:40强度不足')
    if f1000['lowPct'] < -1.5 and not live_repair:
        risks.append('09:40前回撤过深')
    if not f1000['aboveAvg']:
        risks.append('09:40未站均价线')
    if f1000['highPct'] - f1000['endPct'] > 2.3:
        risks.append('09:40前冲高回落')
    if f1000['endPct'] > 6.5 and f1000['lowPct'] > -0.3:
        risks.append('已明显拉高，等待回踩不追')
    prev_close = _num(row.get('prev_close'))
    if prev_close and f1000.get('last') and (f1000['last'] / max(prev_close, 0.01) - 1) * 100 >= 7.0:
        risks.append('09:40相对昨收已高位，不做加仓追涨')
    if early_missed and f1000.get('high') and f1000.get('last') and f1000['last'] < f1000['high']:
        risks.append('修复升级未收在09:40阶段新高')
    hard = any(x in risks for x in ['竞价偏高，加仓确认不追','09:40强度不足','09:40前回撤过深','09:40未站均价线','09:40前冲高回落','已明显拉高，等待回踩不追','09:40相对昨收已高位，不做加仓追涨','修复升级未收在09:40阶段新高'])
    if hard:
        return '只观察', '09:40加仓确认未通过或已过追涨性价比，不进入加仓讨论', risks, f1000
    if early_missed:
        return '加仓确认池', '09:31未通过但09:40重新站回，允许从观察池升级为加仓确认；只能作为确认讨论，不追高', risks or ['09:31修复确认'], f1000
    return '加仓确认池', '09:40加仓确认通过；用于确认/加仓讨论，首次发现已太晚的不追', risks or ['暂无硬风险'], f1000
