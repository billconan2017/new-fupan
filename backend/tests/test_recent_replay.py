from app.services.recent_replay import choose_candidates,evaluate

def fixture():
 days=['2026-09-11','2026-09-14','2026-09-15','2026-09-16']
 def bar(t,o=10,c=10):return {'t':t,'o':o,'h':12,'l':9,'c':c,'pc':10,'sf':0,'v':100}
 minute=[bar(days[0]+' 09:35:00',9.8,10),bar(days[0]+' 09:45:00')]
 daily=[bar(d) for d in days];limits=[{'t':d,'h':11,'l':9} for d in days]
 return {'signal_date':days[0],'code':'000001'},days,minute,daily,limits

def test_candidate_selection_exact_day_and_no_future_ranking():
 base={'name':'测试','code':'000001','time':'2026-09-11','qczf':5,'qccje':5e7,'qcwtje':1e8}
 assert choose_candidates([base],'2026-09-11',{'000001'})[0]['score']==100
 assert not choose_candidates([base],'2026-09-10',{'000001'})
 assert not choose_candidates([{**base,'qczf':9}],'2026-09-11',{'000001'})
 assert not choose_candidates([base],'2026-09-11',set())

def test_t1_weekend_costs_and_pending_not_losses():
 args=fixture();r=evaluate(*args,'2026-09-14')
 assert r['entry_status']=='simulated' and r['shares']==900
 assert r['paths'][0]['exit_date']=='2026-09-14'
 assert r['paths'][0]['pnl']<0 and r['paths'][0]['gross_pct']==0
 assert r['paths'][1]['status']=='pending' and 'pnl' not in r['paths'][1]

def test_first_bar_filter_independent_of_later_winners():
 candidate,days,minute,daily,limits=fixture();minute[0]['c']=9.7
 assert evaluate(candidate,days,minute,daily,limits,days[-1])['entry_status']=='not_entered'

def test_missing_limits_not_assumed_fill_and_down_limit_not_realized_loss():
 args=fixture();assert evaluate(*args[:-1],[],args[1][-1])['entry_status']=='unknown'
 candidate,days,minute,daily,limits=args;limits[1]['l']=10
 r=evaluate(*args,days[-1]);assert r['paths'][0]['status']=='blocked' and 'pnl' not in r['paths'][0]

def test_later_minute_candles_cannot_change_entry():
 args=list(fixture());r=evaluate(*args,args[1][-1]);args[2].append({'t':'2026-09-11 09:50:00','o':10000,'c':10000})
 assert evaluate(*args,args[1][-1])==r

def test_missing_minutes_are_unknown_not_a_rejected_signal():
 candidate,days,minute,daily,limits=fixture()
 assert evaluate(candidate,days,[],daily,limits,days[-1])['entry_status']=='unknown'
