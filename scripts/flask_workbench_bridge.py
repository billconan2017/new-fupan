"""Attach the new workbench to an existing Flask entry without changing legacy APIs.
Call register_workbench(app, absolute_dist_path). ?legacy=1 retains the old root.
Only /api/workbench/* is proxied; credentials and arbitrary URLs are never accepted.
"""
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from flask import request, send_from_directory, Response


def register_workbench(app, dist, upstream='http://127.0.0.1:19009'):
    root=Path(dist).resolve()
    @app.after_request
    def legacy_navigation(response):
        if request.path in ('/review','/review/') and response.status_code==200 and response.mimetype=='text/html':
            response.direct_passthrough=False
            html=response.get_data(as_text=True)
            banner='''<aside id="guanmai-version-link" style="position:fixed;bottom:12px;right:16px;z-index:2147483000;max-width:calc(100vw - 32px);padding:12px 16px;border:1px solid #bfa46c;border-radius:10px;background:#142035;color:#e2e9f2;font:13px/1.6 sans-serif;box-shadow:0 6px 25px #0006">当前为旧版总控 · 原有功能保留 <a href="/" style="color:#f3d297;margin-left:12px;font-weight:600">打开新版总览与数据状态 ↗</a></aside>'''
            response.set_data(html.replace('</body>',banner+'</body>'))
            response.headers['Cache-Control']='no-store'
        return response
    @app.before_request
    def workbench_entry():
        path=request.path
        if path in ('/','/workbench') and request.method=='GET' and request.args.get('legacy')!='1':
            return send_from_directory(str(root),'index.html',max_age=0)
        if path.startswith('/assets/') and request.method=='GET':
            asset=(root/path.lstrip('/')).resolve()
            if asset.is_relative_to(root/'assets') and asset.is_file():
                return send_from_directory(str(root/'assets'),asset.name,max_age=86400)
        if path.startswith('/api/workbench/'):
            if request.method not in ('GET','POST'):
                return Response('{"detail":"Method not allowed"}',405,content_type='application/json')
            if (request.content_length or 0)>16384:
                return Response('{"detail":"Request too large"}',413,content_type='application/json')
            body=request.get_data(cache=False) if request.method=='POST' else None
            if body is not None and len(body)>16384:
                return Response('{"detail":"Request too large"}',413,content_type='application/json')
            suffix=('?'+request.query_string.decode('ascii')) if request.query_string else ''
            req=Request(upstream+path+suffix,data=body,method=request.method,headers={'Content-Type':'application/json'})
            try:
                with urlopen(req,timeout=30) as result:
                    return Response(result.read(),result.status,content_type='application/json')
            except HTTPError as e:
                return Response(e.read(),e.code,content_type='application/json')
            except (URLError,TimeoutError):
                return Response('{"detail":"Workbench backend unavailable"}',503,content_type='application/json')
