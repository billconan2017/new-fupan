# FuPanX · A 股复盘 + 实盘辅助系统

2026-09-17：已升级量脉路径式网关，新增请求合并、批量取数、日期校验和数据源状态页。详见 [迁移说明与验证边界](docs/LIANGMAI_MIGRATION_20260917.md)。首次部署使用独立数据库，先执行 `alembic upgrade head`，验收后再开启调度。

自建的 A 股全链路复盘与盘中辅助平台：行情数据落地 → 复盘分析 → 竞价 / 盘中监控 → 策略选股 → 实盘交易，
前后端分离，后端 **FastAPI + APScheduler + PostgreSQL + Redis**，前端 **Vue 3 + Vite + ECharts + Element Plus**。

> 量脉（liangmai）作为主数据源，内置多数据源三层路由与熔断，保证盘中稳定性。

## ✨ 功能模块

| 模块 | 说明 |
|---|---|
| 📊 复盘中心 | 每日复盘报告自动生成，涨停 / 跌停 / 炸板 / 强势股池、情绪周期、资金流向 |
| 🐉 龙虎榜 | 龙虎榜数据抓取与归档 |
| 💰 资金流向 | 大盘 / 板块 / 个股资金流 |
| 🏷 板块分析 | 行业板块行情与板块树 |
| 📈 K 线 | 个股日 / 分钟 K 线 |
| 🔨 竞价总控 | 集合竞价阶段选股与监控 |
| ⚡ 盘中实时 | 盘中行情与持仓监控 |
| 🎯 策略选股 | 策略选股引擎 |
| 💼 实盘交易 | 实盘交易接口对接与下单调度 |
| 🛡 系统 | 数据源熔断、慢查询日志、定时任务（APScheduler）看板 |

后端按 router / service 分层，共 16 个路由模块、15 个 service；数据模型与迁移用 SQLAlchemy + Alembic 管理。

## 🧱 技术栈

**后端**
- FastAPI · Uvicorn
- SQLAlchemy 2（async）· Alembic · asyncpg / psycopg2
- PostgreSQL · Redis
- APScheduler（定时抓取 / 调度）
- Pydantic Settings（`.env` 配置）

**前端**
- Vue 3 · Vue Router · Pinia
- Vite
- ECharts · Element Plus · Axios

## 🚀 快速开始

### 1. 准备依赖

```bash
sudo apt install postgresql redis-server
sudo systemctl enable --now postgresql redis-server
```

### 2. 创建数据库

```bash
sudo -u postgres psql -c "CREATE DATABASE new_fupan;"
sudo -u postgres psql -c "CREATE USER fupan WITH PASSWORD 'your_password';"
sudo -u postgres psql -c "GRANT ALL ON DATABASE new_fupan TO fupan;"
```

### 3. 后端

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# 编辑 .env，至少填入 LIANGMAI_TOKEN 与 PG_PASSWORD

# 初始化数据表
alembic upgrade head

python run.py
# 默认监听 0.0.0.0:9009
```

### 4. 前端

```bash
cd frontend
npm install
npm run dev      # 开发模式，默认 http://localhost:3000
```

生产构建：

```bash
# 在项目根目录
./deploy_frontend.sh   # 构建并把产物拷贝到 dist/
```

## ⚙️ 配置

所有配置通过 `backend/.env` 注入（见 `backend/.env.example`）：

- `LIANGMAI_TOKEN`：量脉数据源 token（必填）
- `PG_*`：PostgreSQL 连接
- `REDIS_*`：Redis 连接
- 数据源熔断、慢查询阈值、端口等见 `app/config.py`

## 📁 目录结构

```
new-fupan/
├── backend/
│   ├── app/
│   │   ├── routers/      # API 路由（竞价/资金/龙虎榜/情绪/板块/策略/交易…）
│   │   ├── services/     # 业务逻辑（数据源路由、调度器、各模块 service）
│   │   ├── models/       # SQLAlchemy 模型
│   │   ├── liangmai/     # 量脉客户端 & token 管理
│   │   ├── config.py     # Pydantic Settings
│   │   └── database.py
│   ├── alembic/          # 数据库迁移
│   ├── requirements.txt
│   └── run.py
├── frontend/
│   ├── src/
│   │   ├── pages/  views/  components/
│   │   ├── stores/  api/  router/
│   │   └── main.js
│   └── package.json
├── deploy_frontend.sh
└── README.md
```

## 📝 版本记录

- **v2.1.0**：历史数据导入 + APScheduler 加固
- **v2.0.0**：策略选股 + 实盘交易 + 数据源三层路由 + APScheduler 重构

详见 `release.md` / `release_v2.1.md`。

## ⚠️ 免责声明

本项目仅供个人学习与技术研究，不构成任何投资建议。据此操作风险自担。

## 📬 License

MIT（如需）
