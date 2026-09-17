"""Verify restoration only against the disposable integration database."""
import os,sqlite3,importlib.util
from pathlib import Path
import pytest
import psycopg2
from psycopg2.extensions import make_dsn

@pytest.mark.skipif(os.environ.get('FUPAN_TEST_DB')!='1',reason='disposable database only')
def test_restore_is_additive_and_conflicting_ids_roll_back(monkeypatch,tmp_path):
    path=Path(__file__).resolve().parents[2]/'scripts/restore_legacy_selections.py'
    spec=importlib.util.spec_from_file_location('restore_test',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    dsn=make_dsn(host=os.environ['PG_HOST'],port=os.environ['PG_PORT'],user=os.environ['PG_USER'],dbname=os.environ['PG_DATABASE'])
    source=tmp_path/'source.db';tables=('intraday_selection_result','intraday_selection_batch')
    with sqlite3.connect(source) as c:
        for t in tables:
            c.execute(f'create table {t}(id int primary key,trade_date text)')
            c.execute(f'insert into {t} values(1,?)',('2026-09-17',))
    monkeypatch.setenv('LEGACY_PG_DSN',dsn);monkeypatch.setenv('LEGACY_MARKET_DB',str(source))
    pg=psycopg2.connect(dsn);pg.autocommit=True
    try:
        with pg.cursor() as q:
            for t in tables:q.execute(f'CREATE TABLE {t}(id int primary key,trade_date text)')
        r=m.restore('2026-09-17',tmp_path/'backup')
        assert all(v['inserted']==1 for v in r.values())
        assert all(v['action']=='preserved' for v in m.restore('2026-09-17',tmp_path/'backup').values())
        with sqlite3.connect(source) as c:
            for t in tables:c.execute(f'update {t} set trade_date=?',('2026-09-18',))
        with pytest.raises(RuntimeError):m.restore('2026-09-18',tmp_path/'backup')
        with pg.cursor() as q:
            for t in tables:
                q.execute(f'SELECT trade_date FROM {t}');assert q.fetchall()==[('2026-09-17',)]
    finally:
        with pg.cursor() as q:
            for t in tables:q.execute(f'DROP TABLE IF EXISTS {t}')
        pg.close()
