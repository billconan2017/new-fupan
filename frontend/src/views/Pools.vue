<template>
  <div>
    <div class="page-header">
      <div class="page-title">📈 涨跌停池</div>
      <div class="page-subtitle">{{ date }} · 涨停 · 跌停 · 炸板 · 强势股</div>
    </div>

    <div class="toolbar">
      <input type="date" class="date-input" v-model="date" />
      <button class="btn btn-primary" @click="load" :disabled="loading">🔍 查询</button>
      <button class="btn" @click="fetchData" :disabled="fetching">{{ fetching ? '拉取中...' : '⬇️ 拉取' }}</button>
    </div>

    <!-- Tab + 表格统一卡片容器 -->
    <div class="card">
      <div class="card-tabs">
        <div v-for="t in tabs" :key="t.key" class="card-tab" :class="{ active: activeTab === t.key }" @click="activeTab = t.key; offset = 0; load()">
          {{ t.label }} <span v-if="counts[t.key]" style="color:var(--text-muted);font-size:11px">({{ counts[t.key] }})</span>
        </div>
      </div>

      <div v-if="loading" class="loading"><span class="spinner"></span></div>

      <!-- 涨停池 -->
      <div v-if="activeTab === 'limit_up' && !loading">
        <div v-if="items.length === 0" class="empty-state"><div class="icon">📭</div><div class="title">暂无涨停数据</div></div>
        <div v-else class="table-wrap">
          <table class="data-table">
            <thead><tr>
              <th>代码</th><th>名称</th><th class="num">价格</th><th class="num">涨幅%</th>
              <th class="num">成交额</th><th class="num">换手%</th><th class="num">连板</th>
              <th class="num">封板资金</th><th>行业</th><th>首封</th>
            </tr></thead>
            <tbody>
              <tr v-for="r in items" :key="r.code">
                <td><span class="stock-code-link" @click="openStock(r.code, r.name)">{{ r.code }}</span></td>
                <td>{{ r.name }}</td>
                <td class="num">{{ r.price?.toFixed(2) }}</td>
                <td class="num up">+{{ r.pct_chg?.toFixed(2) }}%</td>
                <td class="num">{{ fmtAmt(r.amount) }}</td>
                <td class="num">{{ r.turnover?.toFixed(2) }}</td>
                <td class="num"><span v-if="r.consecutive > 1" class="tag tag-up">{{ r.consecutive }}板</span><span v-else style="color:var(--text-muted)">-</span></td>
                <td class="num">{{ fmtAmt(r.seal_amount) }}</td>
                <td><span class="tag tag-blue">{{ r.industry || '-' }}</span></td>
                <td style="font-size:11px;color:var(--text-muted)">{{ r.first_seal_time || '-' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 跌停池 -->
      <div v-if="activeTab === 'limit_down' && !loading">
        <div v-if="items.length === 0" class="empty-state"><div class="icon">📭</div><div class="title">暂无跌停数据</div></div>
        <div v-else class="table-wrap">
          <table class="data-table">
            <thead><tr><th>代码</th><th>名称</th><th class="num">价格</th><th class="num">跌幅%</th><th class="num">成交额</th><th class="num">换手%</th></tr></thead>
            <tbody>
              <tr v-for="r in items" :key="r.code">
                <td><span class="stock-code-link" @click="openStock(r.code, r.name)">{{ r.code }}</span></td>
                <td>{{ r.name }}</td>
                <td class="num">{{ r.price?.toFixed(2) }}</td>
                <td class="num down">{{ r.pct_chg?.toFixed(2) }}%</td>
                <td class="num">{{ fmtAmt(r.amount) }}</td>
                <td class="num">{{ r.turnover?.toFixed(2) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 炸板池 -->
      <div v-if="activeTab === 'broken_board' && !loading">
        <div v-if="items.length === 0" class="empty-state"><div class="icon">📭</div><div class="title">暂无炸板数据</div></div>
        <div v-else class="table-wrap">
          <table class="data-table">
            <thead><tr><th>代码</th><th>名称</th><th class="num">价格</th><th class="num">涨幅%</th><th class="num">成交额</th><th class="num">炸板次</th><th>行业</th></tr></thead>
            <tbody>
              <tr v-for="r in items" :key="r.code">
                <td><span class="stock-code-link" @click="openStock(r.code, r.name)">{{ r.code }}</span></td>
                <td>{{ r.name }}</td>
                <td class="num">{{ r.price?.toFixed(2) }}</td>
                <td class="num up">+{{ r.pct_chg?.toFixed(2) }}%</td>
                <td class="num">{{ fmtAmt(r.amount) }}</td>
                <td class="num">{{ r.broken_count || '-' }}</td>
                <td><span class="tag tag-orange">{{ r.industry || '-' }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 强势股池 -->
      <div v-if="activeTab === 'strong' && !loading">
        <div v-if="items.length === 0" class="empty-state"><div class="icon">📭</div><div class="title">暂无强势股数据</div></div>
        <div v-else class="table-wrap">
          <table class="data-table">
            <thead><tr><th>代码</th><th>名称</th><th class="num">价格</th><th class="num">涨幅%</th><th class="num">成交额</th><th class="num">换手%</th><th class="num">量比</th><th>行业</th></tr></thead>
            <tbody>
              <tr v-for="r in items" :key="r.code">
                <td><span class="stock-code-link" @click="openStock(r.code, r.name)">{{ r.code }}</span></td>
                <td>{{ r.name }}</td>
                <td class="num">{{ r.price?.toFixed(2) }}</td>
                <td class="num up">+{{ r.pct_chg?.toFixed(2) }}%</td>
                <td class="num">{{ fmtAmt(r.amount) }}</td>
                <td class="num">{{ r.turnover?.toFixed(2) }}</td>
                <td class="num">{{ r.volume_ratio?.toFixed(2) }}</td>
                <td><span class="tag tag-purple">{{ r.industry || '-' }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 分页 -->
      <div v-if="total > limit" class="pagination">
        <button :disabled="offset === 0" @click="offset = 0; load()">首页</button>
        <button :disabled="offset === 0" @click="offset -= limit; load()">上一页</button>
        <span class="current">{{ Math.floor(offset/limit)+1 }} / {{ Math.ceil(total/limit) }}</span>
        <button :disabled="offset+limit >= total" @click="offset += limit; load()">下一页</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { getLimitUp, getLimitDown, getBrokenBoard, getStrong, fetchPools } from '../api'

const date = ref(new Date().toISOString().slice(0,10))
const loading = ref(false)
const fetching = ref(false)
const activeTab = ref('limit_up')
const items = ref([])
const total = ref(0)
const offset = ref(0)
const limit = 50
const counts = ref({})

const tabs = [
  { key: 'limit_up', label: '涨停池' },
  { key: 'limit_down', label: '跌停池' },
  { key: 'broken_board', label: '炸板池' },
  { key: 'strong', label: '强势股池' },
]

const apiMap = { limit_up: getLimitUp, limit_down: getLimitDown, broken_board: getBrokenBoard, strong: getStrong }

const fmtAmt = (v) => { if (!v) return '-'; if (v >= 1e8) return (v/1e8).toFixed(2) + '亿'; if (v >= 1e4) return (v/1e4).toFixed(0) + '万'; return v.toString() }

function openStock(code, name) { console.log('Stock:', code, name) }

async function load() {
  loading.value = true
  try {
    const fn = apiMap[activeTab.value]
    const { data } = await fn({ date: date.value, limit, offset: offset.value })
    items.value = data.items || []
    total.value = data.total || 0
    counts.value[activeTab.value] = data.total || 0
  } catch { items.value = [] }
  loading.value = false
}

async function fetchData() {
  fetching.value = true
  try { await fetchPools(date.value); await load() } catch {}
  fetching.value = false
}

watch(activeTab, () => { offset.value = 0; load() })
onMounted(load)
</script>

<style scoped>
.stock-code-link {
  color: var(--color-main);
  cursor: pointer;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}
.stock-code-link:hover { text-decoration: underline; }
</style>
