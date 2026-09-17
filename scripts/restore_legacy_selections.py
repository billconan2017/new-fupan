"""Restore an empty day only, atomically and without deleting existing records.
Credentials: LEGACY_PG_DSN. Source: LEGACY_MARKET_DB. No notifications.
"""
import argparse,json,os,sqlite3
import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values
from datetime import date
from pathlib import Path

def restore(day,backup_dir=None):
    source=Path(os.environ['LEGACY_MARKET_DB']).resolve()
    with sqlite3.connect(f'file:{source}?mode=ro',uri=True,timeout=2) as sq:
        sq.row_factory=sqlite3.Row
        sources={table:[dict(r) for r in sq.execute(f'SELECT * FROM {table} WHERE trade_date=?',(day,))]
                 for table in ('intraday_selection_result','intraday_selection_batch')}
    backup=(Path(backup_dir) if backup_dir else Path(__file__).resolve().parents[1]/'data/recovery')/('legacy-selections-'+day+'.json')
    backup.parent.mkdir(parents=True,exist_ok=True)
    if not backup.exists():
        with backup.open('x') as f:os.chmod(backup,0o600);json.dump(sources,f,ensure_ascii=False)
    counts={}
    with psycopg2.connect(os.environ['LEGACY_PG_DSN'],connect_timeout=3,options='-c statement_timeout=10000') as pg:
        with pg.cursor() as q:
            q.execute('SELECT pg_advisory_xact_lock(889920260917)')
            for table,rows in sources.items():
                q.execute(sql.SQL('LOCK TABLE {} IN SHARE ROW EXCLUSIVE MODE').format(sql.Identifier(table)))
                q.execute(sql.SQL('SELECT count(*) FROM {} WHERE trade_date=%s').format(sql.Identifier(table)),(day,))
                before=q.fetchone()[0]
                if before:
                    counts[table]={'existing':before,'inserted':0,'action':'preserved'};continue
                if not rows:counts[table]={'existing':0,'inserted':0,'action':'source_empty'};continue
                q.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s",(table,))
                allowed={r[0] for r in q.fetchall()};cols=[k for k in rows[0] if k in allowed and k!='rowid']
                command=sql.SQL('INSERT INTO {} ({}) VALUES %s ON CONFLICT (id) DO NOTHING').format(sql.Identifier(table),sql.SQL(',').join(map(sql.Identifier,cols))).as_string(pg)
                execute_values(q,command,[[r.get(k) for k in cols] for r in rows])
                q.execute(sql.SQL('SELECT count(*) FROM {} WHERE trade_date=%s').format(sql.Identifier(table)),(day,))
                after=q.fetchone()[0]
                if after!=len(rows):raise RuntimeError('Row count mismatch: rollback required')
                counts[table]={'existing':before,'inserted':after,'action':'restored'}
    return counts

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--day',required=True,type=date.fromisoformat);args=parser.parse_args()
    try:print(json.dumps(restore(args.day.isoformat()),ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({'error':type(exc).__name__,'message':'恢复未完成；事务回滚，未删除原数据。'},ensure_ascii=False))
        raise SystemExit(1)
