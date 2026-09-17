import json,sqlite3
from app.services.integration_status import task_summary,sqlite_coverage,legacy_candidates

def test_tasks_never_expose_prompt_error_credentials_or_delivery_targets():
    rows=[{'name':'股票同步','enabled':True,'last_status':'error','last_error':"No module named 'bs4' secret=password123",'prompt':'private','deliver':'private','schedule':{'expr':'30 8 * * *'}},{'name':'非相关备份'}]
    r=task_summary(rows)
    assert len(r)==1 and r[0]['reason']=='缺少依赖：bs4'
    assert all(s not in json.dumps(r) for s in ('password123','private','last_error'))

def test_legacy_selection_is_exact_date_deduplicated_read_only(tmp_path):
    p=tmp_path/'legacy.db'
    with sqlite3.connect(p) as c:
        c.execute('create table intraday_selection_result(trade_date text,stock_code text,stock_name text,stage text,status text,score real,industry text,selected_time text,reason_text text,rank_no int)')
        for code,day,stage in [('000001','2026-09-17','accept945'),('000001','2026-09-17','confirm1000'),('000002','2026-09-16','confirm1000')]:
            c.execute('insert into intraday_selection_result values(?,?,?,?,?,?,?,?,?,?)',(day,code,'样本',stage,'观察',80,'行业',day+' 09:40','记录',1))
    before=p.read_bytes()
    r=legacy_candidates(str(p),'2026-09-17')
    assert len(r)==1 and r[0]['stage']=='confirm1000'
    coverage=sqlite_coverage(str(p),'2026-09-17')
    assert next(r for r in coverage if r.get('table')=='intraday_selection_result')['day_rows']==2
    assert p.read_bytes()==before
