from datetime import datetime
from app.services.interface_audit import inspect_response,merge_quotes,enrich_report
from app.services.data_evidence import SH

def test_lhb_nested_dates_not_misreported_as_missing():
    r=inspect_response('lhb_daily',{'ok':True,'data':{'reason':[{'thsCode':'000001','endDate':'2026-09-16'}]}},'2026-09-16')
    assert r['rows_or_keys']==1 and r['date_check']=='contains_requested'
    assert inspect_response('lhb_daily',{'ok':True,'data':{'reason':[{'thsCode':'000001','endDate':'2026-09-11'}]}},'2026-09-16')['date_check']=='other_dates'

def test_live_timestamp_is_source_not_fetch_time():
    r=inspect_response('market_quote',{'ok':True,'data':{'p':10,'t':'2026-09-17 11:31:00'},'_meta':{'fetchedAt':'2026-09-17 14:00:00'}},'2026-09-17',datetime(2026,9,17,14,0,tzinfo=SH))
    assert r['quote_states']=={'stale':1}

def test_targeted_quote_never_blends_old_volume_ratio_or_wrong_date():
    old=[{'dm':'000001','p':10,'lb':2,'t':'2026-09-17 10:00:00'}]
    new=[{'dm':'000001','p':11,'t':'2026-09-17 10:01:00'}]
    merged=merge_quotes(old,new,'2026-09-17')
    assert merged[0]['p']==11 and 'lb' not in merged[0]
    assert merge_quotes(old,[dict(new[0],t='2026-09-16 15:00:00')],'2026-09-17')[0]['p']==10

def test_smoke_categories_keep_empty_and_error_distinct():
    report=enrich_report({'items':[{'api':'a','status':'empty'},{'api':'b','status':'error'}]}, {'endpoints':{'a':{'category':'竞价'},'b':{'category':'竞价'}}})
    assert report['categories']['竞价']=={'total':2,'ready':0,'empty':1,'error':1,'untested':0}
