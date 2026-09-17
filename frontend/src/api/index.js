import axios from 'axios'

const api = axios.create({ baseURL: '/api', timeout: 30000 })

// ── 通用 ──
export const getHealth = () => api.get('/health')

// ── 调度器 ──
export const getSchedulerStatus = () => api.get('/scheduler/status')
export const triggerPostMarket = (date) => api.post('/scheduler/trigger/post-market', null, { params: { date } })
export const triggerFetchAll = (date) => api.post('/scheduler/fetch-all', null, { params: { date } })
export const triggerBackfill = (start, end) => api.post('/scheduler/backfill', null, { params: { start_date: start, end_date: end } })

// ── 股池 ──
export const getLimitUp = (params) => api.get('/pools/limit-up', { params })
export const getLimitDown = (params) => api.get('/pools/limit-down', { params })
export const getBrokenBoard = (params) => api.get('/pools/broken-board', { params })
export const getStrong = (params) => api.get('/pools/strong', { params })
export const fetchPools = (date) => api.post('/pools/fetch-all', null, { params: { date } })

// ── 龙虎榜 ──
export const getDragonTiger = (params) => api.get('/dragon/tiger', { params })
export const getYouziList = (date) => api.get('/dragon/youzi', { params: { date } })
export const getYouziDetail = (id, days) => api.get(`/dragon/youzi/${id}`, { params: { days } })

// ── 竞价 ──
export const getAuctionStocks = (params) => api.get('/auction/stocks', { params })
export const getAuctionSectors = (params) => api.get('/auction/sectors', { params })
export const getAuctionTail = (params) => api.get('/auction/tail', { params })
export const getAuctionYizi = (date) => api.get('/auction/yizi', { params: { date } })

// ── 情绪 ──
export const getEmotionCycle = (params) => api.get('/emotion/cycle', { params })
export const getEmotionSummary = (date) => api.get('/emotion/summary', { params: { date } })

// ── 资金流 ──
export const getCapitalFlow = (params) => api.get('/capital/flow', { params })
export const getSectorFlow = (params) => api.get('/capital/sectors', { params })

// ── 板块 ──
export const getSectorHeatmap = (date) => api.get('/sector/heatmap', { params: { date } })
export const getSectorRotation = (params) => api.get('/sector/rotation', { params })

// ── 复盘报告 ──
export const getReviewReport = (date) => api.get('/review/report', { params: { date } })
export const getReviewList = (params) => api.get('/review/list', { params })
export const generateReview = (date) => api.post('/review/generate', null, { params: { date } })

export default api

// ── 策略选股 ──
export const screenStocks = (filters, date) => api.post('/strategy/screen', filters, { params: { date } })
export const saveStrategy = (name, filters, date, results) => api.post('/strategy/save', results || [], { params: { name, date }, headers: { 'Content-Type': 'application/json' } })
export const getStrategies = (params) => api.get('/strategy/list', { params })
export const getStrategyDetail = (id) => api.get(`/strategy/detail/${id}`)
export const deleteStrategy = (id) => api.delete(`/strategy/${id}`)
export const backtestStrategy = (filters, start, end) => api.post('/strategy/backtest', filters, { params: { start_date: start, end_date: end } })
export const exportStocks = (filters, date) => api.post('/strategy/export', filters, { params: { date } })

// ── 实盘交易 ──
export const getAccounts = () => api.get('/trading/accounts')
export const addAccount = (data) => api.post('/trading/accounts', data)
export const updateAccount = (id, data) => api.put(`/trading/accounts/${id}`, data)
export const deleteAccount = (id) => api.delete(`/trading/accounts/${id}`)
export const getAccountSummary = (id, date) => api.get(`/trading/accounts/${id}/summary`, { params: { date } })
export const getPositions = (params) => api.get('/trading/positions', { params })
export const syncPositions = (accountId, positions) => api.post('/trading/positions/sync', positions, { params: { account_id: accountId } })
export const placeOrder = (data) => api.post('/trading/orders', data)
export const cancelOrder = (id) => api.delete(`/trading/orders/${id}`)
export const cancelAllOrders = (accountId, date) => api.delete('/trading/orders', { params: { account_id: accountId, date } })
export const clearPositions = (accountId) => api.post('/trading/clear', null, { params: { account_id: accountId } })
export const getOrders = (params) => api.get('/trading/orders', { params })
export const getTradeHistory = (params) => api.get('/trading/trades', { params })
export const getMonthlyPnl = (params) => api.get('/trading/pnl/monthly', { params })
export const getTradeReview = (accountId, date) => api.get('/trading/review', { params: { account_id: accountId, date } })
export const addBlacklist = (code, name, reason) => api.post('/trading/blacklist', null, { params: { code, name, reason } })
export const removeBlacklist = (code) => api.delete(`/trading/blacklist/${code}`)
export const getBlacklist = () => api.get('/trading/blacklist')

// ── 基础数据 ──
export const getStockBasic = (params) => api.get('/stock-basic', { params })
export const getSectorTree = (params) => api.get('/sector/tree', { params })

export const getDataQuality = (date) => api.get("/data-quality/status", { params: { date } })
