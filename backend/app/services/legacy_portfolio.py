"""Preserved user-entered real trade ledger; read-only, separate from simulations."""
import os,sqlite3
from pathlib import Path
from collections import Counter

def report(path=None):
    path=Path(path or os.environ.get('LEGACY_PORTFOLIO_DB',str(Path.home()/'.local/share/guanmai/legacy/portfolio.db')))
    result={'holdings':[],'trades':[],'summary':{},'note':'继承旧系统的真实交易手工台账，尚未与券商交割单核对。持仓状态是旧库最后记录，不能代表当前账户。旧记录利润的手续费口径未核验，时间字段可能是录入时间。'}
    if not path.is_file():return {**result,'error':'尚未保存旧交易台账'}
    try:
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=2) as c:
            c.row_factory=sqlite3.Row;c.execute('PRAGMA query_only=ON')
            result['holdings']=[dict(r) for r in c.execute('SELECT id,code,name,cost,shares,buy_date,buy_time,status,stop_loss,take_profit,strategy_tags FROM holdings ORDER BY buy_date DESC,id DESC')]
            result['trades']=[dict(r) for r in c.execute('SELECT id,code,name,action,price,shares,trade_date,trade_time,profit,profit_pct FROM trades ORDER BY trade_date DESC,trade_time DESC,id DESC')]
        trades=result['trades']
        ledger=Counter();active=Counter()
        for t in trades:
            if t['action'] in ('buy','sell'):ledger[t['code']]+=(1 if t['action']=='buy' else -1)*(t['shares'] or 0)
        for h in result['holdings']:
            if h['status']=='holding':active[h['code']]+=h['shares'] or 0
        result['reconciliation']=[{'code':code,'ledger_net_shares':ledger[code],'holding_shares':active[code]} for code in sorted(set(ledger)|set(active)) if ledger[code]!=active[code]]
        profits=[t['profit'] for t in trades if t['action']=='sell' and t['profit'] is not None]
        result['summary']={'holding_records':len(result['holdings']),'open_records':sum(h['status']=='holding' for h in result['holdings']),'trade_count':len(trades),'actions':dict(Counter(t['action'] for t in trades)),'last_trade_date':max((t['trade_date'] for t in trades),default=None),'recorded_profit_sum':round(sum(profits),2) if profits else None,'sell_records_with_profit':len(profits)}
    except sqlite3.Error:result['error']='旧交易快照读取失败'
    return result
