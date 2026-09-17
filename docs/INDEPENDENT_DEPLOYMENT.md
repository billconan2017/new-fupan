# 独立版部署与前后端规划（2026-09-17）

## 当前部署

- 本机入口 http://127.0.0.1:8899/，仅本机监听。FastAPI 直接提供 Vue 构建产物及 API，不再由旧 Flask 转发。
- 源码：`/home/bill/文档/ChatGPT/股票复盘系统/new-fupan`。
- 后台服务：`guanmai-workbench.service`，启动 `deploy/serve.py`，单 worker。
- PostgreSQL：`~/.local/share/fupan-preview/cluster`，私有 Unix socket，端口标识 55439，无 TCP 监听。保留原新版库，不另造一份重复数据库。
- 凭证：`~/.config/guanmai/runtime.env`，0600，本机读取。运行时不再读取旧项目目录或旧进程环境。
- 自动采集：`guanmai-collect.timer` 每分钟唤醒 `guanmai-collect.service`。它调用本机 `/api/workbench/automation/tick`；业务时间表、交易日校验和幂等记录在后端。
- 已启用用户服务自启动，用户 linger 已开启；电脑必须开机且联网才能采集。不是云端定时任务。

## 调度与覆盖

| 时段 | 任务 |
|---|---|
| 09:26–09:29 | 采集竞价截面、证券清单、交易日历和前日热点 |
| 09:30–11:30 / 13:00–15:00 | 每5分钟行情、股池与竞价背景；之后采集最多5只重点股分时 |
| 15:45 / 17:30 / 20:30 / 22:00 | 复盘数据、最多5只分时、截至前日的趋势日线 |

量脉交易日历未核实则不执行；周末跳过。重启后只补当前盘中窗口或最近盘后批次，不伪造错过的竞价。失败任务在该窗口内最多3次重试、至少相隔5分钟；接口返回空数据记为部分缺失，在后续批次再次请求。采集互斥，行情任务不会无限堆积。

采集范围不是原36个任务的逐项等价替换：旧淘股吧正文、新闻RSS、全市场多周期历史补库、完整资金因子流程仍未移植。旧接口有效性和数据时点须逐项重新验证，不能据此声称全功能迁移完成。

## 数据库职责

```text
量脉 → 采集与校验 → PostgreSQL → FastAPI只读查询 → Vue工作台
          ↑             ├ wb_evidence：接口/日期最新证据
     systemd定时器      ├ wb_evidence_history：从本次部署起追加的采集快照
                        ├ wb_jobs：逐接口执行结果与进度
                        ├ wb_schedule_runs：定时窗口、任务、尝试次数
                        └ wb_plans：冻结观察依据
```

历史快照保存采集时点与原始业务字段，禁止把采集时间冒充行情源时间。原有日线、分钟线、资金等标准表保留；后续接入走统一代码/交易日/周期键。旧32GB目录暂作历史档案，不进入新版实时计算、不删除，不宣称已完整迁移。历史快照不追溯生成部署前数据；回测引擎尚未使用该新历史表做全市场时点回放。

## Web 规划及本次落地

1. 首页：数字行情摘要、最多5只观察对象、大分时、涨停行业分布；实际已上线。涨跌家数标为样本统计，缺失龙虎榜显示“—”。
2. 标的工作台：竞价/盘中阶段，短线与趋势切换，评分明细与来源时间。
3. 次日备选：热点池、龙虎榜等交集；与当日盘中排序分开。
4. 复盘：按日期查看情绪、涨停、资金证据，后续补连板梯队和主题传播路径。
5. 计划研究：冻结信号，按T+1、停牌/涨跌停和费用核验结果；回测不承诺持续盈利。
6. 数据运维：自动采集记录、接口覆盖和异常，默认折叠，不占首页主要空间。

参考资料：
- 同花顺官方热点复盘功能说明：https://download.10jqka.com.cn/productlog/detail/id/108/ （情绪、涨跌停、历史强势股、大盘异动）
- 财联社看盘：https://www.cls.cn/finance
- 财联社焦点复盘：https://www.cls.cn/subject/1135 （主线板块与涨停分析）

本次参考官方说明的信息结构，非复制界面或声称接入其收费行情。外部截图在当前浏览器未成功加载。

## 旧系统停用与回退

已禁用 `local-stock-review.service`；36个原启用的股票相关 Hermes 任务通过原生任务存储接口暂停，其他任务不变。旧PostgreSQL可能被其他项目共用，未停止整个数据库服务。

回退材料位于 `~/.local/share/guanmai-backup/20260917-independent/`：旧service配置、旧任务配置、新库切换前dump、暂停任务ID。此目录包含本地运维资料，不提交Git。

需要回退时先停新timer和新web，恢复旧service配置，再启动旧service；仅按暂停ID恢复旧股票任务，不覆盖Hermes全局配置。数据库迁移为增加表，不删除旧数据。

检查命令：
```sh
systemctl --user status guanmai-workbench.service guanmai-collect.timer
systemctl --user list-timers guanmai-collect.timer
curl -fsS http://127.0.0.1:8899/api/workbench/automation
```
