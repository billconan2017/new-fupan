"""Pinned public endpoint contracts; wire field names stay case-sensitive."""
import json
from datetime import datetime
from pathlib import Path

CATALOG = json.loads(Path(__file__).with_name('catalog.json').read_text())
ENDPOINTS = CATALOG['endpoints']
ALIASES = {
    'stock_list': 'basic_stock_list', 'sector_tree': 'sector_catalog',
    'sector_constituents': 'sector_members',
    'market_realtime_all_network': 'market_snapshot_all',
    'market_realtime_all': 'market_quote_all',
    'stock_realtime': 'market_quote', 'stock_realtime_multi': 'market_quote_multi',
    'quote_realtime_broker': 'market_quote_pro',
    'quote_bars_history': 'kline_history', 'quote_bars_latest': 'kline_latest',
    'pool_limit_up': 'stockpool_limit_up', 'pool_limit_down': 'stockpool_limit_down',
    'pool_broken_board': 'stockpool_broken_board', 'pool_strong': 'stockpool_strong',
    'company_profile': 'corp_profile', 'company_holders_top10': 'corp_top10_holders',
    'company_dividend': 'corp_dividend',
    'fin_balance_sheet': 'finance_balance_sheet',
    'fin_income_statement': 'finance_income_statement',
    'fin_cashflow_statement': 'finance_cashflow_statement',
    'tech_macd': 'indicator_macd', 'tech_ma': 'indicator_ma',
    'tech_boll': 'indicator_boll', 'tech_kdj': 'indicator_kdj',
    'base_bkjj': 'auction_morning_sector', 'base_bkjjzq': 'auction_morning_sector_pro',
    'base_jjqc': 'auction_morning_grab_amount',
    'base_jjqc_tail_wt': 'auction_tail_grab_amount',
    'base_jjqc_tail_cje': 'auction_tail_grab_turnover',
    'base_jjqc_tail_close': 'auction_tail_grab_close',
    'base_jjqc_tail_zf': 'auction_tail_grab_change',
    'jjyizi_list': 'auction_one_word_limit',
    'base_emotional_cycle': 'anomaly_emotion_cycle',
    'base_bk_flow_history': 'flow_sector_history',
    'base_code_flow': 'flow_stock_history',
    'dragonTiger': 'lhb_daily', 'hotmoney_all': 'lhb_trader_records',
    'hotmoney_stock': 'lhb_stock_trader_records',
    'hotmoney_name': 'lhb_trader_record_history',
}


def prepare(api: str, params: dict | None) -> tuple[str, dict]:
    name = ALIASES.get(api, api)
    if name not in ENDPOINTS:
        raise ValueError('接口不在已核对的量脉目录中')
    p = {k: v for k, v in (params or {}).items() if v is not None and v != ''}
    if 'token' in p or 'api' in p:
        raise ValueError('业务参数不能覆盖认证或接口名')
    schema = ENDPOINTS[name]['params']
    if api != name:
        if name.startswith('stockpool_') and 'date' in p:
            p['trade_date'] = p.pop('date')
        if name == 'sector_members' and 'bkCode' in p:
            p['sector_code'] = p.pop('bkCode')
        if 'full_code' in schema and 'ts_code' in p:
            p['full_code'] = p.pop('ts_code')
        if p.get('interval') == 'day':
            p['interval'] = 'd'
    for key, rule in schema.items():
        if rule.get('required') and key not in p:
            raise ValueError(f'缺少必填参数: {key}')
    unknown = set(p) - set(schema)
    if unknown:
        raise ValueError('不支持的参数: ' + ', '.join(sorted(unknown)))
    for key, value in list(p.items()):
        rule = schema[key]
        if 'enum' in rule and str(value) not in {str(x) for x in rule['enum']}:
            raise ValueError(f'参数 {key} 不在支持范围内')
        if rule.get('type') == 'integer':
            if isinstance(value, bool) or not str(value).isdigit() or int(value) < 1:
                raise ValueError(f'参数 {key} 必须是正整数')
            p[key] = int(value)
        if rule.get('format') == 'date':
            raw = str(value)
            # Official parameter examples and live probes require compact dates for ticks.
            # Accept ISO at our boundary and normalize only these two vendor endpoints.
            if name in {'market_tick_history','market_tick_bj_history'} and key=='trade_date':
                raw=raw.replace('-','')
                if not _valid_date(raw,'%Y%m%d'):raise ValueError('历史逐笔日期格式无效')
                p[key]=raw
                continue
            formats = ('%Y%m%d', '%Y%m%d%H%M%S') if key in {'st', 'et'} else ('%Y-%m-%d',)
            if not any(_valid_date(raw, f) for f in formats):
                raise ValueError(f'参数 {key} 日期格式无效')
    if name == 'kline_latest' and int(p.get('lt', 5)) > 5:
        raise ValueError('最新K线最多5条，请使用 kline_history')
    if 'interval' in schema and str(p.get('interval', 'd')).isdigit() and p.get('cq', 'n') != 'n':
        raise ValueError('分钟线仅支持不复权 cq=n')
    if 'st' in p and 'et' in p and str(p['st']).ljust(14, '0') > str(p['et']).ljust(14, '9'):
        raise ValueError('起始日期不能晚于结束日期')
    return name, p


def _valid_date(value: str, fmt: str) -> bool:
    try:
        return datetime.strptime(value, fmt).strftime(fmt) == value
    except ValueError:
        return False


def unpack(payload):
    """Unwrap only status envelopes, never rename arbitrary business fields."""
    codes = []
    for _ in range(5):
        if not isinstance(payload, dict) or 'code' not in payload:
            break
        # A business stock record may itself contain a `code` field.
        if codes and ('data' not in payload or not ('msg' in payload or 'message' in payload)):
            break
        code = str(payload['code'])
        codes.append(code)
        if code not in {'0', '200'} and not (len(codes) > 1 and code == '20000'):
            return False, code, None, codes
        if 'data' not in payload:
            return False, 'invalid_response', None, codes
        payload = payload['data']
    if not codes:
        return False, 'invalid_response', None, codes
    return True, codes[-1], payload, codes
