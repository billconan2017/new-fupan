<template>
  <div>
    <div class="page-header">
      <div class="page-title">💼 实盘组合</div>
      <div class="page-subtitle">{{ date }} · 持仓 · 委托 · 成交 · 风控</div>
    </div>

    <div class="toolbar">
      <input type="date" class="date-input" v-model="date" />
      <select class="date-input" v-model="selectedAccount" @change="refresh">
        <option value="">选择账户</option>
        <option v-for="a in accounts" :key="a.id" :value="a.id">{{ a.account_name }} ({{ a.broker }})</option>
      </select>
      <button class="btn btn-primary" @click="refresh" :disabled="!selectedAccount">🔄 刷新</button>
    </div>

    <!-- Tab 导航 -->
    <div class="card">
      <div class="card-tabs">
        <div v-for="t in tabs" :key="t.key" class="card-tab" :class="{ active: activeTab === t.key }" @click="activeTab = t.key; refresh()">
          {{ t.label }}
        </div>
      </div>

      <!-- ① 持仓总览 -->
      <div v-if="activeTab === 'positions'">
        <div v-if="!selectedAccount" class="empty-state"><div class="icon">📂</div><div class="title">请先选择账户</div></div>
        <div v-else>
          <!-- 资产汇总 -->
          <div class="kpi-row-4" style="margin-bottom:16px" v-if="summary">
            <div class="stat-card"><div class="stat-label">初始资金</div><div class="stat-value neutral">{{ fmtAmt(summary.initial_capital) }}</div></div>
            <div class="stat-card"><div class="stat-label">持仓市值</div><div class="stat-value neutral">{{ fmtAmt(summary.total_market_value) }}</div></div>
            <div class="stat-card"><div class="stat-label">浮动盈亏</div><div class="stat-value" :class="summary.total_profit >= 0 ? 'up' : 'down'">{{ fmtAmt(summary.total_profit) }}</div></div>
            <div class="stat-card"><div class="stat-label">总资产</div><div class="stat-value neutral">{{ fmtAmt(summary.total_assets) }}</div></div>
          </div>

          <!-- 持仓列表 -->
          <div v-if="positions.length === 0" class="empty-state"><div class="icon">📭</div><div class="title">暂无持仓</div></div>
          <div v-else class="table-wrap">
            <table class="data-table">
              <thead><tr>
                <th>代码</th><th>名称</th><th class="num">数量</th><th class="num">可用</th>
                <th class="num">成本价</th><th class="num">现价</th><th class="num">市值</th>
                <th class="num">盈亏</th><th class="num">盈亏%</th>
              </tr></thead>
              <tbody>
                <tr v-for="p in positions" :key="p.code">
                  <td><span class="stock-code-link">{{ p.code }}</span></td>
                  <td>{{ p.name }}</td>
                  <td class="num">{{ p.quantity }}</td>
                  <td class="num">{{ p.available_qty }}</td>
                  <td class="num">{{ p.cost_price?.toFixed(2) }}</td>
                  <td class="num">{{ p.current_price?.toFixed(2) }}</td>
                  <td class="num">{{ fmtAmt(p.market_value) }}</td>
                  <td class="num" :class="p.profit >= 0 ? 'up' : 'down'">{{ fmtAmt(p.profit) }}</td>
                  <td class="num" :class="p.profit_pct >= 0 ? 'up' : 'down'">{{ p.profit_pct?.toFixed(2) }}%</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ② 委托下单 -->
      <div v-if="activeTab === 'order'">
        <div v-if="!selectedAccount" class="empty-state"><div class="icon">📂</div><div class="title">请先选择账户</div></div>
        <div v-else class="order-layout">
          <!-- 快捷买入/卖出 -->
          <div class="card" style="margin-bottom:16px">
            <div class="card-header"><div class="card-title">快捷下单</div></div>
            <div class="order-form">
              <div class="order-row">
                <div class="order-field"><label>股票代码</label><input type="text" v-model="orderForm.code" placeholder="000001" /></div>
                <div class="order-field"><label>名称</label><input type="text" v-model="orderForm.name" placeholder="平安银行" /></div>
                <div class="order-field">
                  <label>方向</label>
                  <select v-model="orderForm.direction">
                    <option value="buy">买入</option>
                    <option value="sell">卖出</option>
                  </select>
                </div>
              </div>
              <div class="order-row">
                <div class="order-field"><label>委托类型</label>
                  <select v-model="orderForm.order_type">
                    <option value="limit">限价</option>
                    <option value="market">市价</option>
                    <option value="conditional">条件单</option>
                  </select>
                </div>
                <div class="order-field"><label>价格</label><input type="number" v-model.number="orderForm.price" step="0.01" /></div>
                <div class="order-field"><label>数量</label><input type="number" v-model.number="orderForm.quantity" step="100" /></div>
              </div>
              <div class="order-row" v-if="orderForm.order_type === 'conditional'">
                <div class="order-field"><label>触发价</label><input type="number" v-model.number="orderForm.trigger_price" step="0.01" /></div>
                <div class="order-field"><label>触发类型</label>
                  <select v-model="orderForm.trigger_type">
                    <option value="price_above">价格上穿</option>
                    <option value="price_below">价格下穿</option>
                    <option value="pct_above">涨幅超%</option>
                    <option value="pct_below">跌幅超%</option>
                  </select>
                </div>
                <div class="order-field"><label>备注</label><input type="text" v-model="orderForm.remark" /></div>
              </div>
              <div style="display:flex;gap:8px;margin-top:12px">
                <button class="btn btn-primary" @click="doPlaceOrder">📤 提交委托</button>
                <button class="btn" @click="doCancelAll" style="color:var(--down)">🚫 全部撤单</button>
                <button class="btn" @click="doClear" style="color:var(--down)">⚠️ 一键清仓</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ③ 委托&成交 -->
      <div v-if="activeTab === 'history'">
        <div v-if="!selectedAccount" class="empty-state"><div class="icon">📂</div><div class="title">请先选择账户</div></div>
        <div v-else>
          <div class="card-tabs" style="padding:0 16px">
            <div class="card-tab" :class="{ active: historyTab === 'orders' }" @click="historyTab = 'orders'; loadOrders()">当日委托</div>
            <div class="card-tab" :class="{ active: historyTab === 'trades' }" @click="historyTab = 'trades'; loadTrades()">历史成交</div>
            <div class="card-tab" :class="{ active: historyTab === 'pnl' }" @click="historyTab = 'pnl'; loadPnl()">月度盈亏</div>
          </div>

          <!-- 当日委托 -->
          <div v-if="historyTab === 'orders'">
            <div v-if="orders.length === 0" class="empty-state"><div class="icon">📭</div><div class="title">今日无委托</div></div>
            <div v-else class="table-wrap">
              <table class="data-table">
                <thead><tr>
                  <th>时间</th><th>代码</th><th>名称</th><th>方向</th><th>类型</th>
                  <th class="num">价格</th><th class="num">数量</th><th class="num">成交</th><th>状态</th><th>操作</th>
                </tr></thead>
                <tbody>
                  <tr v-for="o in orders" :key="o.id">
                    <td style="font-size:11px;color:var(--text-muted)">{{ o.order_time?.slice(11, 19) }}</td>
                    <td>{{ o.code }}</td>
                    <td>{{ o.name }}</td>
                    <td :class="o.direction === 'buy' ? 'up' : 'down'">{{ o.direction === 'buy' ? '买' : '卖' }}</td>
                    <td style="font-size:11px">{{ o.order_type }}</td>
                    <td class="num">{{ o.price?.toFixed(2) }}</td>
                    <td class="num">{{ o.quantity }}</td>
                    <td class="num">{{ o.filled_qty || 0 }}</td>
                    <td><span class="tag" :class="statusTag(o.status)">{{ statusText(o.status) }}</span></td>
                    <td><button v-if="o.status === 'pending'" class="btn" style="font-size:11px;padding:2px 6px" @click="doCancel(o.id)">撤单</button></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- 历史成交 -->
          <div v-if="historyTab === 'trades'">
            <div v-if="trades.length === 0" class="empty-state"><div class="icon">📭</div><div class="title">暂无成交记录</div></div>
            <div v-else class="table-wrap">
              <table class="data-table">
                <thead><tr>
                  <th>日期</th><th>代码</th><th>名称</th><th>方向</th>
                  <th class="num">成交价</th><th class="num">成交量</th><th class="num">成交额</th>
                </tr></thead>
                <tbody>
                  <tr v-for="t in trades" :key="t.id">
                    <td style="color:var(--text-muted)">{{ t.trade_date }}</td>
                    <td>{{ t.code }}</td>
                    <td>{{ t.name }}</td>
                    <td :class="t.direction === 'buy' ? 'up' : 'down'">{{ t.direction === 'buy' ? '买' : '卖' }}</td>
                    <td class="num">{{ t.filled_price?.toFixed(2) }}</td>
                    <td class="num">{{ t.filled_qty }}</td>
                    <td class="num">{{ fmtAmt(t.filled_amount) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- 月度盈亏 -->
          <div v-if="historyTab === 'pnl'">
            <div v-if="pnl" class="kpi-row-4" style="margin:16px 0">
              <div class="stat-card"><div class="stat-label">买入总额</div><div class="stat-value up">{{ fmtAmt(pnl.buy_amount) }}</div></div>
              <div class="stat-card"><div class="stat-label">卖出总额</div><div class="stat-value down">{{ fmtAmt(pnl.sell_amount) }}</div></div>
              <div class="stat-card"><div class="stat-label">净额</div><div class="stat-value" :class="pnl.net_amount >= 0 ? 'up' : 'down'">{{ fmtAmt(pnl.net_amount) }}</div></div>
              <div class="stat-card"><div class="stat-label">交易笔数</div><div class="stat-value neutral">{{ pnl.trade_count }}</div></div>
            </div>
          </div>
        </div>
      </div>

      <!-- ④ 风控设置 -->
      <div v-if="activeTab === 'risk'">
        <div class="risk-layout">
          <!-- 黑名单管理 -->
          <div class="card">
            <div class="card-header">
              <div class="card-title">🚫 个股黑名单</div>
              <button class="btn" style="font-size:12px" @click="showAddBlack = true">+ 添加</button>
            </div>
            <div v-if="blacklist.length === 0" style="padding:16px;color:var(--text-muted);text-align:center">暂无黑名单</div>
            <div v-else class="table-wrap">
              <table class="data-table">
                <thead><tr><th>代码</th><th>名称</th><th>原因</th><th>日期</th><th>操作</th></tr></thead>
                <tbody>
                  <tr v-for="b in blacklist" :key="b.code">
                    <td>{{ b.code }}</td>
                    <td>{{ b.name }}</td>
                    <td style="font-size:12px;color:var(--text-muted)">{{ b.reason || '-' }}</td>
                    <td style="font-size:11px;color:var(--text-muted)">{{ b.added_date }}</td>
                    <td><button class="btn" style="font-size:11px;padding:2px 6px;color:var(--down)" @click="doRemoveBlack(b.code)">移除</button></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- 风控规则说明 -->
          <div class="card" style="margin-top:16px">
            <div class="card-header"><div class="card-title">📋 风控规则</div></div>
            <div style="padding:12px;font-size:13px;color:var(--text-secondary);line-height:1.8">
              <div>• <strong>总仓位上限</strong>：账户初始资金的 90%</div>
              <div>• <strong>单票最大持仓</strong>：账户初始资金的 20%</div>
              <div>• <strong>黑名单个股</strong>：禁止买入，已在持仓中的可卖出</div>
              <div>• 风控规则在下单时自动执行，违规委托将被拦截</div>
            </div>
          </div>
        </div>

        <!-- 添加黑名单弹窗 -->
        <div v-if="showAddBlack" class="modal-overlay" @click.self="showAddBlack = false">
          <div class="modal card">
            <div class="card-title" style="margin-bottom:12px">添加黑名单</div>
            <input type="text" v-model="blackForm.code" placeholder="股票代码" style="width:100%;margin-bottom:8px" />
            <input type="text" v-model="blackForm.name" placeholder="股票名称" style="width:100%;margin-bottom:8px" />
            <input type="text" v-model="blackForm.reason" placeholder="原因" style="width:100%;margin-bottom:12px" />
            <div style="display:flex;gap:8px;justify-content:flex-end">
              <button class="btn" @click="showAddBlack = false">取消</button>
              <button class="btn btn-primary" @click="doAddBlack">添加</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import {
  getAccounts, getAccountSummary, getPositions, syncPositions,
  placeOrder, cancelOrder, cancelAllOrders, clearPositions,
  getOrders, getTradeHistory, getMonthlyPnl,
  addBlacklist, removeBlacklist, getBlacklist,
} from '../api'

const date = ref(new Date().toISOString().slice(0, 10))
const selectedAccount = ref('')
const accounts = ref([])
const positions = ref([])
const summary = ref(null)
const orders = ref([])
const trades = ref([])
const pnl = ref(null)
const blacklist = ref([])

const activeTab = ref('positions')
const historyTab = ref('orders')

const tabs = [
  { key: 'positions', label: '📊 持仓总览' },
  { key: 'order', label: '📝 委托下单' },
  { key: 'history', label: '📋 委托&成交' },
  { key: 'risk', label: '🛡️ 风控设置' },
]

const orderForm = reactive({
  code: '', name: '', direction: 'buy',
  order_type: 'limit', price: null, quantity: null,
  trigger_price: null, trigger_type: 'price_above', remark: '',
})

const showAddBlack = ref(false)
const blackForm = reactive({ code: '', name: '', reason: '' })

function fmtAmt(v) {
  if (!v) return '-'
  const n = Number(v)
  if (Math.abs(n) >= 1e8) return (n / 1e8).toFixed(2) + '亿'
  if (Math.abs(n) >= 1e4) return (n / 1e4).toFixed(0) + '万'
  return n.toFixed(0)
}

function statusTag(s) {
  return { pending: 'tag-blue', filled: 'tag-up', partial: 'tag-blue', cancelled: '', rejected: 'tag-down' }[s] || ''
}
function statusText(s) {
  return { pending: '挂单中', filled: '已成交', partial: '部分成交', cancelled: '已撤单', rejected: '已拒绝' }[s] || s
}

async function loadAccounts() {
  try {
    const res = await getAccounts()
    accounts.value = res.data?.items || []
    if (accounts.value.length && !selectedAccount.value) {
      selectedAccount.value = accounts.value[0].id
    }
  } catch (e) { console.error(e) }
}

async function refresh() {
  if (!selectedAccount.value) return
  const aid = selectedAccount.value
  try {
    if (activeTab.value === 'positions') {
      const [posRes, sumRes] = await Promise.all([
        getPositions({ account_id: aid, date: date.value }),
        getAccountSummary(aid, date.value),
      ])
      positions.value = posRes.data?.items || []
      summary.value = sumRes.data?.summary || null
    } else if (activeTab.value === 'history') {
      if (historyTab.value === 'orders') await loadOrders()
      else if (historyTab.value === 'trades') await loadTrades()
      else if (historyTab.value === 'pnl') await loadPnl()
    } else if (activeTab.value === 'risk') {
      await loadBlacklist()
    }
  } catch (e) { console.error(e) }
}

async function loadOrders() {
  const res = await getOrders({ account_id: selectedAccount.value, date: date.value })
  orders.value = res.data?.items || []
}
async function loadTrades() {
  const res = await getTradeHistory({ account_id: selectedAccount.value })
  trades.value = res.data?.items || []
}
async function loadPnl() {
  const now = new Date()
  const res = await getMonthlyPnl({ account_id: selectedAccount.value, year: now.getFullYear(), month: now.getMonth() + 1 })
  pnl.value = res.data || null
}
async function loadBlacklist() {
  const res = await getBlacklist()
  blacklist.value = res.data?.items || []
}

async function doPlaceOrder() {
  if (!orderForm.code || !orderForm.quantity) return
  try {
    const res = await placeOrder({ ...orderForm, account_id: selectedAccount.value })
    if (res.data?.ok) {
      orderForm.code = ''
      orderForm.name = ''
      orderForm.price = null
      orderForm.quantity = null
    }
    alert(res.data?.msg || '已提交')
  } catch (e) {
    alert('下单失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function doCancel(id) {
  try {
    await cancelOrder(id)
    await loadOrders()
  } catch (e) { console.error(e) }
}

async function doCancelAll() {
  if (!confirm('确认撤销全部挂单？')) return
  try {
    await cancelAllOrders(selectedAccount.value, date.value)
    await loadOrders()
  } catch (e) { console.error(e) }
}

async function doClear() {
  if (!confirm('确认一键清仓？')) return
  try {
    const res = await clearPositions(selectedAccount.value)
    alert(res.data?.msg || '已提交')
    await refresh()
  } catch (e) { console.error(e) }
}

async function doAddBlack() {
  if (!blackForm.code) return
  try {
    await addBlacklist(blackForm.code, blackForm.name, blackForm.reason)
    showAddBlack.value = false
    blackForm.code = ''
    blackForm.name = ''
    blackForm.reason = ''
    await loadBlacklist()
  } catch (e) { console.error(e) }
}

async function doRemoveBlack(code) {
  try {
    await removeBlacklist(code)
    await loadBlacklist()
  } catch (e) { console.error(e) }
}

onMounted(() => { loadAccounts() })
</script>

<style scoped>
.order-layout { max-width: 700px; }
.order-form { padding: 16px; }
.order-row { display: flex; gap: 12px; margin-bottom: 10px; }
.order-field { flex: 1; }
.order-field label { display: block; font-size: 12px; color: var(--text-muted); margin-bottom: 4px; }
.order-field input,
.order-field select {
  width: 100%;
  padding: 8px;
  background: var(--bg-input, #1c2128);
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--text-primary);
  font-size: 13px;
}
.risk-layout { max-width: 800px; }
.kpi-row-4 {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.modal {
  min-width: 320px;
  max-width: 400px;
  padding: 20px;
}
.modal input {
  padding: 8px;
  background: var(--bg-input, #1c2128);
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--text-primary);
}
</style>
