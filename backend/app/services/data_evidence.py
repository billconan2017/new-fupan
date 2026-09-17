"""Timestamp and completeness rules shared by review and intraday views."""
from datetime import datetime, time
from zoneinfo import ZoneInfo

SH = ZoneInfo('Asia/Shanghai')


def quote_time(value):
    """Only accept a full source timestamp, never substitute collection time."""
    if isinstance(value, datetime):
        result = value
    else:
        raw = str(value or '')
        if len(raw) < 14:
            return None
        try:
            result = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        except ValueError:
            try:
                result = datetime.strptime(raw, '%Y%m%d%H%M%S')
            except ValueError:
                return None
    return result.replace(tzinfo=SH) if result.tzinfo is None else result.astimezone(SH)


def freshness(value, target, now=None):
    now = now or datetime.now(SH)
    dt = quote_time(value)
    if not dt:
        return {'state': 'unknown', 'label': '源时间缺失', 'source_at': None, 'age_seconds': None}
    age = (now - dt).total_seconds()
    state, label = 'stale', '行情已过期'
    if dt.date().isoformat() != target:
        state, label = 'mismatch', '日期不匹配'
    elif age < -30:
        state, label = 'invalid', '源时间异常'
    elif target < now.date().isoformat():
        state, label = 'history', '历史行情'
    elif now.weekday() >= 5 or not (time(9,15) <= now.time() <= time(11,30) or time(13) <= now.time() <= time(15)):
        state, label = 'off_session', '非连续更新时段'
    elif age <= 120:
        state, label = 'fresh', '两分钟内行情'
    return {'state': state, 'label': label, 'source_at': dt.isoformat(), 'age_seconds': max(0, round(age))}


def report_quality(report):
    fields = {'market_overview':'市场快照', 'emotion_summary':'情绪', 'limit_up_analysis':'涨停池',
              'limit_down_analysis':'跌停池', 'broken_board_analysis':'炸板池',
              'dragon_tiger_summary':'龙虎榜', 'capital_summary':'资金流'}
    missing = [name for key, name in fields.items() if not (report.get(key) or {}).get('available')]
    return {'status': 'partial' if missing else 'recorded', 'missing': missing,
            'recorded_modules': len(fields)-len(missing), 'total_modules': len(fields),
            'note': '有记录不等于全市场完整覆盖；综合分仅为规则统计，不是收益预测。'}
