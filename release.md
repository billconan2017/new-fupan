# New FuPanX v2.0.0 Release Notes

> 发布日期: 2026-07-08
> 版本: 2.0.0
> 服务端口: 9009 (FastAPI)

---

## 📋 概览

本次更新是 FuPanX 系统的一次重大升级，涵盖后端数据源架构重构、新增策略选股和实盘交易两大模块、APScheduler 定时调度器全面改造，以及前端新增两个侧边菜单页面。

---

## 🗄️ 新增数据表 (7张)

| 表名 | 说明 | 关键索引 |
|------|------|----------|
| `stock_basic` | 全市场个股基础信息底库 | code (unique), trade_date |
| `sector_tree` | 同花顺 88 行业板块树 | sector_code (unique), parent_code |
| `strategy_record` | 选股策略历史回测记录 | trade_date, (strategy_name, trade_date) |
| `account_info` | 实盘多账户配置表 | account_name (unique) |
| `position_record` | 持仓同步记录表 | (trade_date, code), (account_id, trade_date) |
| `order_record` | 委托单/成交单流水表 | trade_date, (account_id, trade_date) |
| `risk_blacklist` | 个股风控黑名单表 | code (unique) |

原有 20 张业务表完全保留，未做任何删改。

---

## 🔌 新增 API 接口清单

### 策略选股 `/api/strategy`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/strategy/screen` | 多条件筛选选股 |
| POST | `/api/strategy/save` | 保存选股方案 |
| GET | `/api/strategy/list` | 方案列表 |
| GET | `/api/strategy/detail/{id}` | 方案详情 |
| DELETE | `/api/strategy/{id}` | 删除方案 |
| POST | `/api/strategy/backtest` | 历史回测 |
| POST | `/api/strategy/export` | 导出CSV |

### 实盘交易 `/api/trading`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/trading/accounts` | 账户列表 |
| POST | `/api/trading/accounts` | 新增账户 |
| PUT | `/api/trading/accounts/{id}` | 编辑账户 |
| DELETE | `/api/trading/accounts/{id}` | 删除账户 |
| GET | `/api/trading/accounts/{id}/summary` | 账户资产汇总 |
| GET | `/api/trading/positions` | 查询持仓 |
| POST | `/api/trading/positions/sync` | 同步持仓 |
| POST | `/api/trading/orders` | 下单 (含风控) |
| DELETE | `/api/trading/orders/{id}` | 撤单 |
| DELETE | `/api/trading/orders` | 批量撤单 |
| POST | `/api/trading/clear` | 一键清仓 |
| GET | `/api/trading/orders` | 委托查询 |
| GET | `/api/trading/trades` | 成交历史 |
| GET | `/api/trading/pnl/monthly` | 月度盈亏 |
| GET | `/api/trading/review` | 交易复盘 |
| POST | `/api/trading/blacklist` | 加入黑名单 |
| DELETE | `/api/trading/blacklist/{code}` | 移出黑名单 |
| GET | `/api/trading/blacklist` | 黑名单列表 |

---

## ⏰ 定时任务清单 (APScheduler)

| 任务ID | 时间 | 说明 |
|--------|------|------|
| `pre_market` | 09:14 | 盘前：更新 stock_basic + sector_tree 底库 |
| `auction` | 09:26 | 竞价：拉取个股竞价、板块竞价、封单排行 |
| `intraday_11_30` | 11:30 | 盘中：涨跌停池、板块热力、资金流向 |
| `intraday_14_30` | 14:30 | 盘中：增量同步 |
| `intraday_15_00` | 15:00 | 收盘：增量同步 |
| `post_market` | 15:40 | 盘后：龙虎榜、全板块资金、复盘报告 |

所有任务自动跳过周末、法定节假日 (chinesecalendar)。
所有任务增加幂等校验：同一天同一任务不会重复入库。

---

## 🔄 数据源降级逻辑

```
三层查询链路:
  ① 本地 PostgreSQL → 有数据直接返回
  ② 量脉网关 → 成功则入库并返回
  ③ 柚子日更接口 → 入库后返回
  ④ 三层全失败 → 标准化提示文案
```

**熔断机制**:
- 量脉连续 3 次失败 → 当日自动锁定柚子源
- 次日凌晨 0 点自动恢复量脉优先
- 状态可通过 `/api/scheduler/status` 查询

**已修复的历史问题**:
- 板块资金接口：自动从 `sector_tree` 表批量读取合法 `bkCode` 参数，根除 422 报错
- 龙虎榜接口：交易日 15:30 前查询直接返回提示，不发起外网请求

---

## 🖥️ 前端新增页面

### 策略选股 (`/strategy`)
- 左侧筛选条件面板，右侧结果表格
- 支持条件保存、日期回测、CSV导出
- 复用全局组件: EmptyState, StockLink

### 实盘组合 (`/live-trading`)
- **持仓总览**: 持仓列表、浮动盈亏、账户资产汇总
- **委托下单**: 快捷买入卖出面板、条件单配置
- **委托&成交**: 当日委托队列、历史成交流水、月度盈亏
- **风控设置**: 黑名单个股管理、风控规则说明

侧边栏新增 "策略与交易" 分组，包含两个新菜单项。
四套主题 (paper/dark/ocean/midnight) 全部适配。

---

## 🏗️ 技术架构变更

| 组件 | 旧版 | 新版 |
|------|------|------|
| 调度器 | asyncio 自循环 | APScheduler BackgroundScheduler |
| 数据源路由 | 量脉优先 + 本地缓存 | 三层路由(DB→量脉→柚子) + 熔断器 |
| 节假日判断 | 仅跳过周末 | chinesecalendar 法定假日 |
| 柚子客户端 | 无 | 新增 YouziClient |
| 版本号 | 1.0.0 | 2.0.0 |

---

## 📦 依赖新增

```
chinesecalendar>=1.9.0  # 法定节假日判断
```

---

## 🔒 约束遵循

- ✅ 9009 端口服务持续在线，增量迭代
- ✅ 原有 7 大页面版式完全冻结
- ✅ Hermes 所有股票定时/采集脚本永久停用
- ✅ 数据读取三级优先级: 本地库 → 量脉 → 柚子
- ✅ 全程在 new-fupan 目录内完成

---

## 📁 新增/修改文件清单

### Backend (新增)
- `app/youzi/client.py` — 柚子 API 客户端
- `app/youzi/__init__.py`
- `app/utils.py` — 交易日判断 + 工具函数
- `app/services/trading_scheduler.py` — APScheduler 调度器
- `app/services/stock_basic_service.py` — 个股基础信息服务
- `app/services/sector_tree_service.py` — 板块树服务
- `app/services/strategy_service.py` — 策略选股服务
- `app/services/trading_service.py` — 实盘交易服务
- `app/routers/strategy.py` — 策略选股 API
- `app/routers/trading.py` — 实盘交易 API
- `alembic/versions/6f773238efbd_*.py` — 数据库迁移

### Backend (修改)
- `app/config.py` — 新增柚子/熔断/慢查询配置
- `app/main.py` — 集成新调度器和路由
- `app/models/stock.py` — 新增 7 个 ORM 模型
- `app/services/datasource_router.py` — 三层路由重写
- `app/services/dragon_service.py` — 龙虎榜时间校验
- `app/services/capital_service.py` — 板块 bkCode 修复
- `app/routers/scheduler.py` — 指向新调度器
- `requirements.txt` — 新增 chinesecalendar
- `.env` — 新增柚子配置项

### Frontend (新增)
- `src/views/Strategy.vue` — 策略选股页面
- `src/views/Portfolio.vue` — 实盘组合页面

### Frontend (修改)
- `src/App.vue` — 侧边栏新增 2 个菜单
- `src/router/index.js` — 新增 2 条路由
- `src/api/index.js` — 新增策略/交易 API 函数
