import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'Dashboard', component: () => import('../views/Dashboard.vue'), meta: { title: '大盘总览', icon: '📊' } },
  { path: '/auction', name: 'Auction', component: () => import('../views/Auction.vue'), meta: { title: '竞价数据', icon: '🔔' } },
  { path: '/pools', name: 'Pools', component: () => import('../views/Pools.vue'), meta: { title: '涨跌停池', icon: '📈' } },
  { path: '/sector', name: 'Sector', component: () => import('../views/Sector.vue'), meta: { title: '板块热力', icon: '🔥' } },
  { path: '/dragon', name: 'Dragon', component: () => import('../views/Dragon.vue'), meta: { title: '龙虎榜', icon: '🐉' } },
  { path: '/capital', name: 'Capital', component: () => import('../views/Capital.vue'), meta: { title: '资金流向', icon: '💰' } },
  { path: '/review', name: 'Review', component: () => import('../views/Review.vue'), meta: { title: '复盘报告', icon: '📋' } },
  { path: '/live/emotion', name: 'LiveEmotion', component: () => import('../views/Placeholder.vue'), meta: { title: '情绪监控', icon: '🧠', api: 'emotion_realtime' } },
  { path: '/live/limit-board', name: 'LimitBoard', component: () => import('../views/Placeholder.vue'), meta: { title: '涨跌看板', icon: '📋', api: 'limit_board_realtime' } },
  { path: '/portfolio', name: 'Portfolio', component: () => import('../views/Placeholder.vue'), meta: { title: '持仓管理', icon: '💼', api: 'portfolio' } },
  { path: '/strategy', name: 'Strategy', component: () => import('../views/Strategy.vue'), meta: { title: '策略选股', icon: '🎯' } },
  { path: '/live-trading', name: 'LiveTrading', component: () => import('../views/Portfolio.vue'), meta: { title: '实盘组合', icon: '💼' } },
  { path: '/admin/data-sources', name: 'DataSources', component: () => import('../views/Placeholder.vue'), meta: { title: '数据源管理', icon: '🗄️', api: 'data_source_lineage' } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
export { routes }
