# 量脉新版接入与数据链路改造

## 基准选择

以 GitHub `billconan2017/new-fupan` 的 FastAPI + Vue 项目为开发基准。原因是已有独立业务服务、异步请求层及 Alembic 迁移，适合建立接口契约测试。本地 LocalStockAllInOne 功能更丰富，但依赖旧绝对路径、多份缓存及重复请求出口，继续原地叠加修复的维护成本较高。

本次交付是新版数据链路及可观测性改造，不代表已将本地 Flask 系统的全部策略、页面、缓存和 32GB 历史数据迁入新库。生产 8899 服务未切换。

## 官方资料核对

- [开发者文档](https://liangmai.pro/docs#description/introduction)
- [MCP 接入说明](https://liangmai.pro/mcp)
- [官方页面指定的 liangmai-mcp 包 0.2.0](https://pypi.org/project/liangmai-mcp/0.2.0/)

核对日期为 2026-09-17。动态文档内嵌的 OpenAPI 列出 255 个接口；MCP 展示页仍写 254，版本标记存在不同步。代码中的 catalog.json 只保存接口名和参数 schema，用于本地校验，不包含凭证和行情。

官方 MCP 包 0.2.0 源码使用 `POST /api/gateway/{api}`，通过 query 传 token 与业务参数。文档中的部分描述仍引用旧别名。新版客户端以 operationId、参数 schema、MCP 实现和少量真实响应交叉核对；没有断言旧网关已停用。

`/mcp` 是接入说明网页，并非可直接替代行情 REST 网关的远程 MCP URL。MCP 通过 `uvx liangmai-mcp` 启动本地服务；复盘系统后端仍直接访问 REST API，以便控制采集调度、预算、错误处理和数据落库。

| 原接口 | 新接口 | 需注意的参数或数据 |
| --- | --- | --- |
| stock_list | basic_stock_list | 不传旧的 dm 参数 |
| stock_realtime_multi | market_quote_multi | 每批最多 20 只，超过时分批合并 |
| market_realtime_all_network | market_snapshot_all | 每分钟最多一次；支持代码作为字典键的响应 |
| quote_bars_history | kline_history | 日线 interval=d；st/et 为紧凑日期；时间字段 t |
| quote_bars_latest | kline_latest | 最多 5 条，更多历史用 history |
| pool_limit_up 等 | stockpool_limit_up 等 | 日期参数为 trade_date |
| dragonTiger | lhb_daily | 嵌套业务状态、thsCode、金额万元转元 |
| base_emotional_cycle | anomaly_emotion_cycle | 无 tradeDate 参数；返回多日序列，按 date1 匹配 |
| base_bk_flow_history | flow_sector_history | 必填单个 bkCode，不能伪造 bkCodes 批量参数 |
| base_code_flow | flow_stock_history | st/et 限定日期，读取 jlr* 分档字段 |
| fin_balance_sheet 等 | finance_balance_sheet 等 | 股票参数改用 full_code |

文档主要描述成功码 0/200；真实龙虎榜、情绪等响应是外层 code=0、内层 code=20000。客户端仅在嵌套状态包接受 20000，内层失败不会被外层成功掩盖。业务字段大小写保持原样，按服务明确解析，不全局改写字典键。

## 已实现

- 新协议与已核对的旧名兼容映射；本地校验必填参数、枚举、日期和未知参数。
- 相同并发请求合并，调用者取消不会中断其他等待者。
- 有限数量的缓存条目、独立返回副本、缓存年龄和获取时间；失败、缺失和部分批量结果不缓存。
- 每进程限速；429/业务限流立即返回冷却状态，支持 Retry-After。仅瞬时网络错误/5xx 重试；每次调用总预算默认 25 秒。
- 批量股票按 20 只分组，返回缺失股票清单；大批量受同一总预算限制，避免无限阻塞。
- 请求日志及错误不输出包含 token 的 URL；禁用 httpx INFO 级 URL 日志。
- 修正日期回填、早盘竞价 period=0、一字板 todayList、资金日期匹配、龙虎榜 INSERT 缺失绑定字段、K线 t 字段与历史范围。
- 快照只接纳能确认股票代码、且源时间属于当日的记录；不使用数组序号猜股票代码。
- 调度器改用 FastAPI 所在事件循环，减少跨事件循环复用连接的问题；失败不登记为当日成功；增加 22:00 晚间补采。
- 资金采集不再先删除全日数据后只写成功的少数股票；按成功标的更新。
- `/api/data-quality/status` 与 `/admin/data-sources` 页面：查看入库日期、条数、请求/缓存/失败、采集任务。查看状态不消耗量脉额度。
- 补齐服务使用但原迁移遗漏的表及可空字段，数据库连接遵循 PG_* 配置；修复快照 datetime 参数和报告 Decimal 序列化。

## 验证与边界

已执行单元回归、隔离 PostgreSQL 全新迁移/采集入库/复盘生成/诊断 API 测试，以及 Vue 生产构建、浏览器状态页检查。隔离集成测试的上游行情采用固定模拟数据，用于验证逻辑与 SQL，不代表真实数据完整率。

另以现有 LIANGMAI_TOKEN 做少量真实只读验证：股票列表 5566 条、2026-09-16 涨停池 89 条、龙虎榜 71 条、情绪序列 43 日，以及两只股票批量行情和两条日K线。数量为验证时快照，不是稳定承诺。未对全部 255 个接口逐个消耗额度测试。

验证时 `sector_plate_code` 返回空数组，系统应报告未取得目录。板块历史资金接口没有热力图所需的涨跌幅、上涨家数，相关字段保留缺失；不能据此宣称热力图功能已完整恢复。全量游资、竞价、财务等主要完成协议与解析改造，仍需使用实际账户数据验收各场景。

限速、缓存、请求合并与任务成功记录当前为进程内状态，部署只启动一个 worker/采集进程；多实例需要另行接入 Redis 分布式限流和任务锁。失败降级的 K 线显式标记 stale；数据页“已入库”只说明有记录，不证明完整或实时。旧策略/复盘评分模型未在本轮重新验证。

## 安装与回滚

1. 使用独立新库验证，先配置 backend/.env；不要直接复用运行中旧库。不要提交 .env。
2. 安装 `backend/requirements.txt`，在 backend 下运行 `alembic upgrade head`。新增迁移为增量建表/加列，不清空历史；既有手工建表若字段类型不同，应先比对 schema。
3. 初次启动设置 `SCHEDULER_ENABLED=false`，配置 LIANGMAI_TOKEN 和 PG_*。验证数据与日期后启用调度。
4. 前端 `npm ci && npm run build`；后端可直接读取 frontend/dist，也兼容原 dist 发布目录。建议 Node 22，锁文件中 Sass 要求 Node >=20.19。
5. 如需撤回，切回先前 Git 提交并停止新版采集。该次迁移 downgrade 保留新增表/列，以免误删原本已手工创建的历史表；它不是物理 schema 逆操作。

测试：

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements-dev.txt
cd backend
../.venv/bin/python -m pytest -q
cd ..
# 需本机 PostgreSQL initdb/pg_ctl，使用独立临时集群，不接触原有数据库
.venv/bin/python scripts/check_isolated_pipeline.py
```
