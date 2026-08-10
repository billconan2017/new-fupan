# FuPanX Phase 3 前端改造完成

## 改造清单

### 1. 设计系统 (8899_design_tokens.css)
- 四主题切换: paper(默认浅色) / dark / ocean / midnight
- 完整CSS变量体系: 颜色、阴影、圆角、间距
- 涨跌色统一: #ff2d2d(红涨) / #16b957(绿跌)
- 表格: 交替行色、hover高亮、sticky表头
- 卡片: 白底、细灰边框、hover阴影

### 2. 全局布局 (App.vue)
- 顶部导航栏: 6大业务动线入口
- 左侧边栏: 分组菜单(数据总览/盘前/盘中/盘后)
- 右上角: 日期选择 + 主题切换(4色圆点)
- keep-alive缓存: 7个页面组件

### 3. Pinia状态管理
- useFilterStore: 全局日期/主线/风险筛选
- useMarketStore: 市场情绪/复盘报告缓存
- useIndustryStore: 板块选择联动

### 4. 全局组件
- StockLink: 股票代码链接(点击弹窗)
- ReviewCard: 统一数据卡片
- ReviewTable: 固定表头表格
- KpiCard: 大数字KPI卡片
- EmptyState: 空状态占位

### 5. 路由更新
- 保留原有7个页面
- 新增占位路由: /live/emotion, /live/limit-board, /portfolio
- Placeholder.vue: 通用建设中页面

### 6. 页面样式对齐
- Dashboard: 评分环 + 6指标卡片 + 情绪/涨停双栏
- Pools: 4 tab涨跌停池 + 分页
- Auction: 4 tab竞价数据
- Sector: 热力图 + 轮动分析
- Dragon: 龙虎榜(删除游资Tab)
- Capital: 资金流向 + 降级提示
- Review: 复盘报告 + 历史列表

## 文件改动清单

```
frontend/src/
├── 8899_design_tokens.css    [新增] 34KB设计系统
├── main.js                   [修改] 引入Pinia+设计系统
├── App.vue                   [重写] 顶部导航+侧边栏布局
├── router/index.js           [修改] 新增占位路由
├── stores/
│   ├── filter.js             [新增] 全局筛选状态
│   ├── market.js             [新增] 市场数据缓存
│   └── industry.js           [新增] 板块选择状态
├── components/
│   ├── StockLink.vue         [新增] 股票链接组件
│   ├── ReviewCard.vue        [新增] 数据卡片
│   ├── ReviewTable.vue       [新增] 固定表头表格
│   ├── KpiCard.vue           [新增] KPI大数字
│   └── EmptyState.vue        [新增] 空状态占位
├── views/
│   ├── Dashboard.vue         [重写] 评分环+指标卡片
│   ├── Pools.vue             [重写] 4Tab涨跌停池
│   ├── Auction.vue           [重写] 4Tab竞价数据
│   ├── Sector.vue            [重写] 热力图+轮动
│   ├── Dragon.vue            [重写] 龙虎榜
│   ├── Capital.vue           [重写] 资金流+降级提示
│   ├── Review.vue            [重写] 复盘报告+历史
│   └── Placeholder.vue       [新增] 建设中占位页
└── api/index.js              [保留] 接口封装不变
```

## 主题切换
- 点击右上角4个彩色圆点切换主题
- 默认paper浅色商务风
- 主题保存到localStorage

## 待后端接口的新增页面
- /live/emotion → 需要 emotion_realtime API
- /live/limit-board → 需要 limit_board_realtime API  
- /portfolio → 需要 portfolio API

## 部署方式
```bash
cd frontend && npm run build
cp -r dist/* ../dist/
# 刷新浏览器即可，无需重启9009
```
