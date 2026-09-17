"""Tables used by data services that were missing from the original migrations."""
from sqlalchemy import Table, Column, BigInteger, Integer, Float, String, DateTime, Text, UniqueConstraint, func
from app.database import Base


def table(name, fields, unique=()):
    return Table(name, Base.metadata,
                 Column('id', BigInteger, primary_key=True, autoincrement=True),
                 *(Column(k, t) for k, t in fields.items()),
                 *( [UniqueConstraint(*unique)] if unique else []))


table('stock_daily_kline', {'code': String(10), 'trade_date': String(10),
    **{k: Float for k in ('open','high','low','close','volume','amount','pct_chg')},
    'source': String(20), 'updated_at': DateTime}, ('code','trade_date'))
table('stock_minute_kline', {'code': String(10), 'trade_date': String(10), 'time': String(32), 'period': Integer,
    **{k: Float for k in ('open','high','low','close','volume','amount','avg')},
    'source': String(20), 'updated_at': DateTime}, ('code','trade_date','time','period'))
table('sector_flow', {'trade_date': String(10), 'sector_code': String(80), 'sector_name': String(120),
    **{k: BigInteger for k in ('main_net','retail_net','total_net')},
    **{k: Float for k in ('change_pct','leader_pct')},
    **{k: Integer for k in ('rise_count','fall_count')},
    'leader_code': String(10), 'leader_name': String(60)}, ('trade_date','sector_code'))
table('auction_sector', {'trade_date': String(10), 'sector_code': String(80), 'sector_name': String(120),
    'pct_chg': Float, 'amount': BigInteger, 'rise_count': Integer, 'fall_count': Integer}, ('trade_date','sector_code'))
table('auction_tail', {'trade_date': String(10), 'code': String(10), 'name': String(60),
    'tail_type': String(20), 'value': Float, 'rank': Integer})
table('auction_yizi', {'trade_date': String(10), 'code': String(10), 'name': String(60),
    'pct_chg': Float, 'amount': BigInteger}, ('trade_date','code'))
table('dragon_tiger_seats', {'trade_date': String(10), 'code': String(10), 'seat_name': String(200),
    'seat_type': String(20), 'amount': BigInteger, 'rank': Integer})
table('youzi_info', {'youzi_id': String(100), 'youzi_name': String(100), 'youzi_type': String(50),
    'updated_at': DateTime}, ('youzi_id',))
table('youzi_trades', {'trade_date': String(10), 'youzi_id': String(100), 'youzi_name': String(100),
    'code': String(10), 'name': String(60), 'direction': String(20), 'amount': BigInteger})

# Missing nullable service fields in the original ORM models.
ADDITIONS = {
    'limit_up_pool': {'limit_type': String(40), 'limit_reason': Text, 'flow_net': BigInteger},
    'broken_board_pool': {'break_time': String(32)},
    'strong_pool': {'continuous_days': Integer},
    'emotion_cycle': {**{k: Integer for k in ('rise_count','fall_count','height_board','continue_count','broken_count')},
                      'avg_change_pct': Float, 'turnover_avg': Float},
}
for name, fields in ADDITIONS.items():
    for key, typ in fields.items():
        Base.metadata.tables[name].append_column(Column(key, typ))
