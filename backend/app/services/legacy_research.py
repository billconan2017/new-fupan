"""Read-only legacy evidence. Stored selections are not verified recommendations/fills."""
import json, os, re, sqlite3
from pathlib import Path

RULES=[
 {'name':'情绪先行','source':'market_emotion_analyzer.py → intraday_selector_v2.py','logic':'昨日涨停少于50，或涨停股中开板比例大于60%，该引擎冻结出手。其他选股引擎是否遵守需分别验证。'},
 {'name':'主线与早封板','source':'intraday_selector_v2.py / time_strength_scorer.py','logic':'博主方向、盘中主线、防守轮动合并；昨日10点前首次封板且开板少于3次加分，午后首次封板降权。'},
 {'name':'开盘承接','source':'app.py / _intraday_stage_status','logic':'09:31检查开盘价、回撤、均价线和竞价过热；09:40检查修复、新高、冲高回落及板块联动。旧945/1000字段实际已改为09:31/09:40。'},
 {'name':'博主观点选股','source':'build_blogger_view_library.py → build_blogger_stock_picks.py','logic':'文章关键词整理为方向和纪律，再匹配行业、流动性、资金与换手；目前是规则提取，不是经验证的预测模型。'},
]

def report(day):
    result={'day':day,'rules':RULES,'views':None,'selections':[],'stage_counts':[],
      'issues':['旧联动辅助判断可被“板块、核心、竞价”等文字触发，不能等同真实量价共振。',
                '旧分钟均价缺失时用最新价替代，会使站上均价线自动通过；迁移时必须保留缺失。',
                '文章日期可能从文件名或修改时间推断，缺少原始发布时间时不能参与历史入场判断。',
                '近五日简化竞价回溯不是旧策略回测；不能用其收益评价这些旧规则。'],
      'note':'只读旧SQLite镜像；不代表已核对旧PostgreSQL、当前定时任务或真实成交。以下规则尚未完整迁移到新版评分。'}
    public=Path(__file__).resolve().parents[3]/'data/research/blogger_source_audit.json'
    if public.exists():result['public_source']=json.loads(public.read_text())
    path=os.environ.get('LEGACY_MARKET_DB')
    if not path or not Path(path).is_file():
        result['error']='旧库未配置或不存在';return result
    try:
        with sqlite3.connect(f'file:{Path(path).resolve()}?mode=ro',uri=True,timeout=2) as c:
            c.row_factory=sqlite3.Row
            c.set_progress_handler(lambda:1,5_000_000)
            row=c.execute('SELECT trade_date,article_count,model_version,updated_at FROM blogger_daily_views WHERE trade_date<=? ORDER BY trade_date DESC LIMIT 1',(day,)).fetchone()
            if row:result['views']=dict(row)|{'publication_time_verified':False}
            result['stage_counts']=[dict(r) for r in c.execute('SELECT stage,count(*) AS count FROM intraday_selection_result WHERE trade_date=? GROUP BY stage',(day,))]
            result['selections']=[dict(r) for r in c.execute('SELECT stock_code,stock_name,stage,status,score,selected_time,created_at,updated_at FROM intraday_selection_result WHERE trade_date=? ORDER BY stage,rank_no LIMIT 30',(day,))]
    except sqlite3.Error as e:
        result['error']='旧库读取未完成：'+type(e).__name__
    return result
