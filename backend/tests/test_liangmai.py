import asyncio
from copy import deepcopy
import json
import pytest
import httpx
from app.config import Settings
from app.liangmai.client import LiangmaiClient
from app.liangmai.contracts import prepare, unpack
from app.liangmai.parsing import emotion_for_date, snapshot_records, source_date


def make_client(handler, **settings):
    config = Settings(_env_file=None, liangmai_token='private-test-token', liangmai_safe_rate=100000,
                      liangmai_peak_rate=100000, **settings)
    client = LiangmaiClient(config)
    client._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return client


async def test_new_protocol_and_canonical_cache():
    requests = []
    def upstream(req):
        requests.append(req)
        assert req.url.path == '/api/gateway/kline_history'
        assert req.url.params['interval'] == 'd'
        assert req.url.params['token'] == 'private-test-token'
        assert not req.content
        return httpx.Response(200, json={'code': 0, 'data': [{'t': '2026-09-16', 'c': 12}]})
    c = make_client(upstream)
    a = await c.call('quote_bars_history', {'full_code': '000001', 'interval': 'day'}, ttl=60)
    a['data'][0]['c'] = 999
    b = await c.call('kline_history', {'interval': 'd', 'full_code': '000001'}, ttl=60)
    assert b['ok'] and b['data'][0]['c'] == 12
    assert b['_meta']['cacheHit'] and b['_meta']['fetchedAt']
    assert b['_meta']['remoteCalls'] == 0 and len(requests) == 1
    await c.close()


@pytest.mark.parametrize('payload,ok,code', [
    ({'code': 0, 'data': {'code': 20000, 'msg': 'success', 'data': [{'name': 'x'}]}}, True, '20000'),
    ({'code': '0', 'data': {'code': '200', 'msg': 'success', 'data': []}}, True, '200'),
    ({'code': 0, 'data': {'code': 401, 'msg': 'bad', 'data': []}}, False, '401'),
    ({'code': 0, 'data': {'code': '000001', 'p': 12}}, True, '0'),
    ({'data': []}, False, 'invalid_response'),
    ({'code': 0}, False, 'invalid_response'),
    ({'code': 20000, 'data': []}, False, '20000'),
])
def test_envelopes(payload, ok, code):
    result = unpack(payload)
    assert result[:2] == (ok, code)


@pytest.mark.parametrize('api,params', [
    ('board_flow_history', {}), ('stockpool_limit_up', {'date': '2026-09-16'}),
    ('flow_sector_history', {'bkCodes': 'BK123|BK456'}),
    ('basic_stock_list', {'token': 'replacement'}),
    ('kline_history', {'full_code': '000001', 'interval': '10'}),
    ('kline_latest', {'full_code': '000001', 'lt': 6}),
    ('kline_history', {'full_code': '000001', 'interval': '5', 'cq': 'f'}),
    ('stockpool_limit_up', {'trade_date': '2026-02-30'}),
])
async def test_bad_parameters_never_spend_quota(api, params):
    def upstream(req): raise AssertionError('unexpected network')
    c = make_client(upstream)
    r = await c.call(api, params)
    assert not r['ok'] and r['code'] == 'invalid_request'
    await c.close()


async def test_concurrent_calls_and_cancellation():
    gate = asyncio.Event()
    calls = []
    async def upstream(req):
        calls.append(req)
        await gate.wait()
        return httpx.Response(200, json={'code': 0, 'data': [1]})
    c = make_client(upstream)
    first = asyncio.create_task(c.call('basic_stock_list'))
    followers = [asyncio.create_task(c.call('basic_stock_list')) for _ in range(15)]
    await asyncio.sleep(.01)
    first.cancel()
    gate.set()
    result = await asyncio.gather(*followers)
    assert len(calls) == 1 and all(x['ok'] for x in result)
    assert not c._inflight
    await c.close()


async def test_batch_45_no_truncation_and_missing_report():
    batches = []
    def upstream(req):
        codes = req.url.params['stock_codes'].split(','); batches.append(codes)
        return httpx.Response(200, json={'code': 0, 'data': [{'dm': x} for x in codes]})
    c = make_client(upstream)
    codes = [f'{i:06}' for i in range(45)]
    r = await c.call('stock_realtime_multi', {'stock_codes': ','.join(codes)})
    assert r['ok'] and len(r['data']) == 45 and [len(x) for x in batches] == [20,20,5]
    assert r['_meta']['remoteCalls'] == 3
    await c.close()


async def test_partial_batch_not_cached():
    count = 0
    def upstream(req):
        nonlocal count; count += 1
        codes = req.url.params['stock_codes'].split(',')
        return httpx.Response(200, json={'code': 0, 'data': [{'dm': x} for x in codes[:-1]]})
    c = make_client(upstream)
    r = await c.call('market_quote_multi', {'stock_codes': ','.join(f'{i:06}' for i in range(21))}, ttl=60)
    assert not r['ok'] and r['code'] == 'partial_data' and r['_meta']['missingCodes'] == ['000019','000020']
    assert not c._cache
    await c.close()


@pytest.mark.parametrize('http_status,body', [(429, {}),(200, {'code': 0,'data': {'code': 60036,'msg':'limit','data':None}})])
async def test_rate_limit_stops_retry_and_shared_pause(http_status,body):
    calls = []
    def upstream(req):
        calls.append(req)
        return httpx.Response(http_status, json=body, headers={'Retry-After':'120'})
    c = make_client(upstream)
    r = await c.call('basic_stock_list')
    second = await c.call('basic_index_list')
    assert not r['ok'] and not second['ok'] and len(calls) == 1
    assert r['_meta']['retryAfterSeconds'] == 120
    await c.close()


async def test_total_deadline_including_upstream():
    async def upstream(req):
        await asyncio.sleep(1)
        return httpx.Response(200, json={'code':0,'data':[]})
    c = make_client(upstream, liangmai_total_timeout=.02)
    r = await c.call('basic_stock_list')
    assert r['code'] == 'deadline_exceeded' and not c._inflight
    await c.close()


async def test_transient_server_failure_retries():
    calls = []
    def upstream(req):
        calls.append(req)
        return httpx.Response(200, json={'code':500,'data':None}) if len(calls)==1 else httpx.Response(200,json={'code':0,'data':[1]})
    c = make_client(upstream)
    r = await c.call('basic_stock_list')
    assert r['ok'] and len(calls)==2
    await c.close()


async def test_error_does_not_expose_credential(caplog):
    def upstream(req):
        raise httpx.ConnectError(str(req.url),request=req)
    c = make_client(upstream,liangmai_max_attempts=1)
    r = await c.call('basic_stock_list')
    assert 'private-test-token' not in json.dumps(r)+json.dumps(c.get_status())+caplog.text
    await c.close()


async def test_cache_bounded_and_empty_not_cached():
    def upstream(req):
        return httpx.Response(200,json={'code':0,'data':[] if req.url.path.endswith('basic_stock_list') else [1]})
    c=make_client(upstream,liangmai_cache_max_entries=2)
    for api in ['basic_index_list','basic_hs_list','basic_etf_list','basic_stock_list']:
        await c.call(api,ttl=60)
    assert len(c._cache)==2
    await c.close()


def test_date_selection_never_relabels_latest():
    data={'colNameList':['date1','ztjs'],'contentList':[[20260915,60],[20260916,89]]}
    assert emotion_for_date(data,'2026-09-15')['ztjs']==60
    assert emotion_for_date(data,'2026-09-17') is None


def test_snapshot_code_index_and_source_date():
    assert snapshot_records({'600519':{'p':12}})==[{'p':12,'code':'600519'}]
    assert snapshot_records([{'p':12}])==[]
    assert source_date('20260916')=='2026-09-16'
