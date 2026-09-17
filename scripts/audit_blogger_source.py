"""Public article index only. No login, cookies, messages, or full article republication.
Run with Python providing requests and beautifulsoup4 (legacy crawler environment).
"""
import json,re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin,urlparse
import requests
from bs4 import BeautifulSoup

def run():
    url='https://www.tgb.cn/blog/7737030'
    response=requests.get(url,timeout=15,headers={'User-Agent':'Mozilla/5.0'})
    response.raise_for_status()
    soup=BeautifulSoup(response.content,'html.parser',from_encoding='utf-8');articles=[]
    for item in soup.select('.allblog_article .article_tittle'):
        a=item.select_one('.tittle_data a');dt=item.select_one('.tittle_fbshijian')
        if not a or not dt:continue
        link=urljoin(url,a.get('href',''));d=re.search(r'20\d{2}-\d{2}-\d{2}',dt.get_text(' ',strip=True))
        if urlparse(link).hostname!='www.tgb.cn' or not d:continue
        articles.append({'url':link,'published_date':d[0],'publication_time_verified':False})
    report={'source':url,'checked_at':datetime.now().astimezone().isoformat(),'count':len(articles),'articles':articles,
            'scope':'公开首页目录样本；只有日期，不足以证明开盘前已发布；未抓取完整原文'}
    p=Path(__file__).resolve().parents[1]/'data/research/blogger_source_audit.json'
    p.parent.mkdir(parents=True,exist_ok=True);temp=p.with_suffix('.tmp');temp.write_text(json.dumps(report,ensure_ascii=False,indent=2));temp.replace(p)
    print('Public article index:',len(articles),'latest:',articles[0]['published_date'] if articles else 'unknown')

if __name__=='__main__':run()
