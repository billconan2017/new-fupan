<template>
  <div>
    <div class="page-header">
      <div class="page-title">🎯 策略选股</div>
      <div class="page-subtitle">{{ date }} · 多条件筛选 · 方案管理 · 历史回测</div>
    </div>

    <div class="toolbar">
      <input type="date" class="date-input" v-model="date" />
      <button class="btn btn-primary" @click="doScreen" :disabled="loading">
        {{ loading ? '⏳ 筛选中...' : '🔍 筛选' }}
      </button>
      <button class="btn" @click="doExport" :disabled="!results.length">📤 导出</button>
      <button class="btn" @click="showSave = true" :disabled="!results.length">💾 保存方案</button>
      <button class="btn" @click="showBacktest = true">📊 历史回测</button>
      <button class="btn" @click="loadStrategies">📂 加载方案</button>
    </div>

    <div class="strategy-layout">
      <!-- 左侧筛选面板 -->
      <div class="filter-panel card">
        <div class="card-header">
          <div class="card-title">筛选条件</div>
        </div>
        <div class="filter-group">
          <label>连板数 ≥</label>
          <input type="number" v-model.number="filters.min_consecutive" placeholder="如: 2" />
        </div>
        <div class="filter-group">
          <label>封单金额 ≥</label>
          <input type="number" v-model.number="filters.min_seal_amount" placeholder="万元" />
        </div>
        <div class="filter-group">
          <label>换手率</label>
          <div style="display:flex;gap:6px">
            <input type="number" v-model.number="filters.min_turnover" placeholder="最小%" style="width:45%" />
            <span style="color:var(--text-muted)">~</span>
            <input type="number" v-model.number="filters.max_turnover" placeholder="最大%" style="width:45%" />
          </div>
        </div>
        <div class="filter-group">
          <label>成交额 ≥</label>
          <input type="number" v-model.number="filters.min_amount" placeholder="万元" />
        </div>
        <div class="filter-group">
          <label>涨跌幅</label>
          <div style="display:flex;gap:6px">
            <input type="number" v-model.number="filters.min_pct_chg" placeholder="最小%" style="width:45%" />
            <span style="color:var(--text-muted)">~</span>
            <input type="number" v-model.number="filters.max_pct_chg" placeholder="最大%" style="width:45%" />
          </div>
        </div>
        <div class="filter-group">
          <label>行业板块</label>
          <input type="text" v-model="filters.industry" placeholder="如: 半导体" />
        </div>
        <div class="filter-group">
          <label>总市值</label>
          <div style="display:flex;gap:6px">
            <input type="number" v-model.number="filters.min_total_cap" placeholder="最小(亿)" style="width:45%" />
            <span style="color:var(--text-muted)">~</span>
            <input type="number" v-model.number="filters.max_total_cap" placeholder="最大(亿)" style="width:45%" />
          </div>
        </div>
        <div class="filter-group" style="display:flex;gap:16px">
          <label style="display:flex;align-items:center;gap:4px">
            <input type="checkbox" v-model="filters.exclude_st" /> 剔除ST
          </label>
          <label style="display:flex;align-items:center;gap:4px">
            <input type="checkbox" v-model="filters.exclude_blacklist" /> 剔除黑名单
          </label>
        </div>
        <button class="btn btn-primary" style="width:100%;margin-top:12px" @click="doScreen" :disabled="loading">
          执行筛选
        </button>
      </div>

      <!-- 右侧结果表格 -->
      <div class="result-panel">
        <div class="card" v-if="results.length > 0">
          <div class="card-header">
            <div class="card-title">筛选结果</div>
            <span class="tag tag-blue">{{ results.length }}只</span>
          </div>
          <div class="table-wrap">
            <table class="data-table">
              <thead><tr>
                <th>代码</th><th>名称</th><th class="num">价格</th><th class="num">涨幅%</th>
                <th class="num">成交额</th><th class="num">换手%</th><th class="num">连板</th>
                <th class="num">封单</th><th class="num">主力净流入</th><th>行业</th>
              </tr></thead>
              <tbody>
                <tr v-for="r in results" :key="r.code">
                  <td><span class="stock-code-link" @click="openStock(r.code, r.name)">{{ r.code }}</span></td>
                  <td>{{ r.name }}</td>
                  <td class="num">{{ r.price?.toFixed(2) }}</td>
                  <td class="num" :class="r.pct_chg >= 0 ? 'up' : 'down'">{{ r.pct_chg >= 0 ? '+' : '' }}{{ r.pct_chg?.toFixed(2) }}%</td>
                  <td class="num">{{ fmtAmt(r.amount) }}</td>
                  <td class="num">{{ r.turnover?.toFixed(2) }}</td>
                  <td class="num"><span v-if="r.consecutive > 1" class="tag tag-up">{{ r.consecutive }}板</span><span v-else style="color:var(--text-muted)">-</span></td>
                  <td class="num">{{ fmtAmt(r.seal_amount) }}</td>
                  <td class="num" :class="(r.main_net || 0) >= 0 ? 'up' : 'down'">{{ fmtAmt(r.main_net) }}</td>
                  <td><span class="tag tag-blue">{{ r.industry || '-' }}</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div v-else-if="!loading" class="empty-state">
          <div class="icon">🎯</div>
          <div class="title">设置筛选条件后点击"执行筛选"</div>
        </div>

        <!-- 已保存方案列表 -->
        <div class="card" v-if="strategies.length > 0" style="margin-top:16px">
          <div class="card-header">
            <div class="card-title">已保存方案</div>
          </div>
          <div class="table-wrap">
            <table class="data-table">
              <thead><tr><th>方案名</th><th>日期</th><th class="num">结果数</th><th>操作</th></tr></thead>
              <tbody>
                <tr v-for="s in strategies" :key="s.id">
                  <td>{{ s.strategy_name }}</td>
                  <td style="color:var(--text-muted)">{{ s.trade_date }}</td>
                  <td class="num">{{ s.result_count }}</td>
                  <td>
                    <button class="btn" style="font-size:11px;padding:2px 8px" @click="loadStrategyDetail(s.id)">查看</button>
                    <button class="btn" style="font-size:11px;padding:2px 8px;color:var(--down)" @click="delStrategy(s.id)">删除</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <!-- 保存方案弹窗 -->
    <div v-if="showSave" class="modal-overlay" @click.self="showSave = false">
      <div class="modal card">
        <div class="card-title" style="margin-bottom:12px">保存选股方案</div>
        <input type="text" v-model="saveName" placeholder="方案名称" style="width:100%;margin-bottom:12px" />
        <div style="display:flex;gap:8px;justify-content:flex-end">
          <button class="btn" @click="showSave = false">取消</button>
          <button class="btn btn-primary" @click="doSave">保存</button>
        </div>
      </div>
    </div>

    <!-- 回测弹窗 -->
    <div v-if="showBacktest" class="modal-overlay" @click.self="showBacktest = false">
      <div class="modal card">
        <div class="card-title" style="margin-bottom:12px">历史回测</div>
        <div style="display:flex;gap:8px;margin-bottom:12px">
          <div><label>起始日期</label><input type="date" v-model="btStart" /></div>
          <div><label>结束日期</label><input type="date" v-model="btEnd" /></div>
        </div>
        <div v-if="btResults.length" style="margin-bottom:12px">
          <div v-for="r in btResults" :key="r.date" style="display:flex;gap:12px;padding:4px 0;border-bottom:1px solid var(--border)">
            <span style="color:var(--text-muted);min-width:90px">{{ r.date }}</span>
            <span :class="r.count > 0 ? 'up' : 'down'">{{ r.count }}只</span>
          </div>
        </div>
        <div style="display:flex;gap:8px;justify-content:flex-end">
          <button class="btn" @click="showBacktest = false">关闭</button>
          <button class="btn btn-primary" @click="doBacktest" :disabled="btLoading">
            {{ btLoading ? '回测中...' : '开始回测' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { screenStocks, getStrategies, getStrategyDetail, deleteStrategy, saveStrategy, backtestStrategy, exportStocks } from '../api'

const date = ref(new Date().toISOString().slice(0, 10))
const loading = ref(false)
const results = ref([])
const strategies = ref([])

const filters = reactive({
  min_consecutive: null,
  min_seal_amount: null,
  min_turnover: null,
  max_turnover: null,
  min_amount: null,
  min_pct_chg: null,
  max_pct_chg: null,
  industry: '',
  min_total_cap: null,
  max_total_cap: null,
  exclude_st: true,
  exclude_blacklist: true,
})

const showSave = ref(false)
const saveName = ref('')
const showBacktest = ref(false)
const btStart = ref('')
const btEnd = ref('')
const btResults = ref([])
const btLoading = ref(false)

function fmtAmt(v) {
  if (!v) return '-'
  const n = Number(v)
  if (Math.abs(n) >= 1e8) return (n / 1e8).toFixed(2) + '亿'
  if (Math.abs(n) >= 1e4) return (n / 1e4).toFixed(0) + '万'
  return n.toFixed(0)
}

function openStock(code, name) {
  window.open(`https://quote.eastmoney.com/concept/${code}.html`, '_blank')
}

async function doScreen() {
  loading.value = true
  try {
    // 清理空值
    const clean = {}
    for (const [k, v] of Object.entries(filters)) {
      if (v !== null && v !== '' && v !== false) clean[k] = v
    }
    const res = await screenStocks(clean, date.value)
    results.value = res.data?.items || []
  } catch (e) {
    console.error(e)
    results.value = []
  } finally {
    loading.value = false
  }
}

async function doSave() {
  if (!saveName.value) return
  try {
    const clean = {}
    for (const [k, v] of Object.entries(filters)) {
      if (v !== null && v !== '' && v !== false) clean[k] = v
    }
    await saveStrategy(saveName.value, clean, date.value, results.value.map(r => r.code))
    showSave.value = false
    saveName.value = ''
    await loadStrategies()
  } catch (e) {
    console.error(e)
  }
}

async function loadStrategies() {
  try {
    const res = await getStrategies()
    strategies.value = res.data?.items || []
  } catch (e) {
    console.error(e)
  }
}

async function loadStrategyDetail(id) {
  try {
    const res = await getStrategyDetail(id)
    const item = res.data?.item
    if (item?.filters) {
      Object.assign(filters, item.filters)
      date.value = item.trade_date
      await doScreen()
    }
  } catch (e) {
    console.error(e)
  }
}

async function delStrategy(id) {
  try {
    await deleteStrategy(id)
    await loadStrategies()
  } catch (e) {
    console.error(e)
  }
}

async function doBacktest() {
  if (!btStart.value) return
  btLoading.value = true
  try {
    const clean = {}
    for (const [k, v] of Object.entries(filters)) {
      if (v !== null && v !== '' && v !== false) clean[k] = v
    }
    const res = await backtestStrategy(clean, btStart.value, btEnd.value || btStart.value)
    const data = res.data?.results || {}
    btResults.value = Object.entries(data).map(([d, v]) => ({ date: d, count: v.count || 0 }))
  } catch (e) {
    console.error(e)
  } finally {
    btLoading.value = false
  }
}

async function doExport() {
  try {
    const clean = {}
    for (const [k, v] of Object.entries(filters)) {
      if (v !== null && v !== '' && v !== false) clean[k] = v
    }
    const res = await exportStocks(clean, date.value)
    const data = res.data?.export || []
    // 下载CSV
    const header = Object.keys(data[0] || {}).join(',')
    const rows = data.map(r => Object.values(r).join(','))
    const csv = '\uFEFF' + header + '\n' + rows.join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `选股结果_${date.value}.csv`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    console.error(e)
  }
}
</script>

<style scoped>
.strategy-layout {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 16px;
  align-items: start;
}
.filter-panel {
  position: sticky;
  top: 80px;
}
.filter-group {
  margin-bottom: 10px;
}
.filter-group label {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 4px;
}
.filter-group input[type="number"],
.filter-group input[type="text"] {
  width: 100%;
  padding: 6px 8px;
  background: var(--bg-input, #1c2128);
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--text-primary);
  font-size: 13px;
}
.filter-group input[type="checkbox"] {
  accent-color: var(--accent);
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
  min-width: 360px;
  max-width: 500px;
  padding: 20px;
}
.modal input[type="text"],
.modal input[type="date"] {
  width: 100%;
  padding: 8px;
  background: var(--bg-input, #1c2128);
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--text-primary);
}
</style>
