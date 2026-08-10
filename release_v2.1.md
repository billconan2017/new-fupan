# FuPanX v2.1.0 Release Notes

> 发布日期: 2026-07-08
> 版本: 2.1.0 (功能冻结版)
> 服务端口: 9009 (FastAPI)

---

## 📋 概览

v2.1.0 是 FuPanX 系统的功能冻结版本。本次更新完成历史存量数据全量导入、数据源三级降级链路启用、APScheduler 定时任务加固，以及 Hermes 股票业务彻底清理。此后项目主干功能正式冻结，仅按需做小功能迭代与 bug 修复。

---

## 📊 历史存量数据导入

从 Hermes `market_cache.db` (18GB SQLite) 批量导入全量历史数据到 PostgreSQL：

| 数据表 | 导入行数 | 日期范围 | 说明 |
|--------|---------|---------|------|
| `stock_basic` | 5,526 | — | 全市场个股基础信息 |
| `sector_tree` | 1,456 | — | 同花顺行业板块树 |
| `limit_up_pool` | 4,215 | 2026-04-28 ~ 2026-07-07 | 涨停池 (ZT类型) |
| `capital_flow` | 3,509,140 | 2023-09-11 ~ 2026-07-07 | 个股资金流向 (675个交易日) |
| `dragon_tiger` | 23,294 | 2023-06-12 ~ 2026-07-07 | 龙虎榜 (346个交易日) |
| `sector_flow` | 56,044 | 2025-08-27 ~ 2026-06-18 | 板块资金流向 (192个交易日) |
| `emotion_cycle` | 47 | — | 情绪周期 |

**导入脚本**: `backend/scripts/import_historical.py` (幂等，可重复执行)

前端任意历史日期均可加载本地库存量数据，不再依赖上游实时接口。

---

## 🔄 数据源三级降级链路

`.env` 已配置柚子数据源连接参数：

```
YOUZI_BASE_URL=http://youzibigdata.com
YOUZI_API_KEY=<需要用户填入>
```

**降级逻辑**:
1. 本地 PostgreSQL → 有数据直接返回
2. 量脉网关 → 成功则入库并返回
3. 柚子日更接口 → 入库后返回
4. 三层全失败 → 标准化提示文案

**熔断器**: 量脉连续 3 次失败 → 当日锁定柚子源 → 次日凌晨 0 点自动恢复

⚠️ **待办**: 用户需在 `backend/.env` 填入 `YOUZI_API_KEY` 以启用柚子数据源。

---

## ⏰ APScheduler 定时任务加固

优化内容：
- ✅ 接口重试：每个任务最多 3 次重试，指数退避 (3s → 6s → 12s)
- ✅ 异常日志：完整 traceback 记录，单任务失败不阻塞其他任务
- ✅ 节假日跳过：chinesecalendar 法定假日 + 周末自动休眠
- ✅ 底库每日更新：盘前 09:14 自动更新 stock_basic + sector_tree
- ✅ 幂等校验：同一天同一任务不会重复入库

| 任务ID | 时间 | 说明 |
|--------|------|------|
| `pre_market` | 09:14 | 盘前：stock_basic + sector_tree 底库更新 |
| `auction` | 09:26 | 竞价：个股竞价、板块竞价、封单排行 |
| `intraday_11_30` | 11:30 | 盘中：涨跌停池、板块热力、资金流向 |
| `intraday_14_30` | 14:30 | 盘中：增量同步 |
| `intraday_15_00` | 15:00 | 收盘：增量同步 |
| `post_market` | 15:40 | 盘后：龙虎榜、全板块资金、复盘报告 |

---

## 🧹 Hermes 股票业务清理

- ✅ 无股票相关定时任务 (仅保留 memory backup)
- ✅ 无 8899/LocalStockAllInOne 运行进程
- ✅ 旧源码已归档（本地备份）
- ✅ 缓存已清理

**Hermes 仅保留能力**: 只读解析 8899 参考文档
**Hermes 不再具备**: 股票数据采集、定时调度、业务代码修改

---

## 🗄️ 数据库变更

新增表: `dragon_tiger_seats` (龙虎榜席位明细)
新增索引: `idx_sf_date_code` (sector_flow 唯一索引), `idx_dt_date_code` (dragon_tiger 唯一索引)

---

## 🔧 Bug 修复

- 修复 `dragon_tiger_seats` 表不存在导致龙虎榜查询 500 错误
- 修复 `sector_flow` 表缺少唯一索引导致幂等导入失败
- 修复 `dragon_tiger` 表缺少唯一索引导致重复数据

---

## 📁 项目文件结构 (最终)

```
new-fupan/
├── backend/
│   ├── app/
│   │   ├── config.py          # 配置 (含柚子/熔断)
│   │   ├── main.py            # FastAPI 入口
│   │   ├── utils.py           # 交易日判断
│   │   ├── youzi/             # 柚子客户端
│   │   ├── liangmai/          # 量脉客户端
│   │   ├── models/            # ORM 模型 (27张表)
│   │   ├── routers/           # API 路由 (15个模块)
│   │   └── services/          # 业务服务
│   │       ├── datasource_router.py   # 三层路由+熔断
│   │       ├── trading_scheduler.py   # APScheduler
│   │       ├── strategy_service.py    # 策略选股
│   │       ├── trading_service.py     # 实盘交易
│   │       └── ...                    # 其他业务服务
│   ├── scripts/
│   │   └── import_historical.py  # 历史数据导入
│   └── .env                      # 环境配置
├── frontend/
│   └── src/
│       ├── views/
│       │   ├── Strategy.vue      # 策略选股
│       │   ├── Portfolio.vue     # 实盘组合
│       │   └── ...               # 原有7个页面
│       └── App.vue               # 侧边栏 (9个菜单)
├── dist/                          # 前端编译产物
└── release.md                     # 版本说明
```

---

## ⚠️ 待办事项

1. **YOUZI_API_KEY**: 在 `backend/.env` 填入柚子 API 密钥以启用三级降级
2. **龙虎榜席位明细**: `dragon_tiger_seats` 表已创建，历史席位数据待后续补全
3. **sector_flow 历史**: 板块资金数据截至 2026-06-18，后续由定时任务自动补全

---

## 🔒 冻结声明

自 v2.1.0 起，FuPanX 项目主干功能正式冻结：
- 后端 API 接口组不再新增
- 前端页面布局、主题、菜单、组件不再修改
- 数据表结构不再变更
- 仅按需做小功能迭代与 bug 修复
