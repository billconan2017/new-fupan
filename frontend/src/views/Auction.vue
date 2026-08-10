<template>
  <div>
    <div class="page-header">
      <div class="page-title">🔔 竞价数据</div>
      <div class="page-subtitle">{{ date }} · 板块竞价 · 个股竞价 · 封单排行 · 一字涨停</div>
    </div>

    <div class="toolbar">
      <input type="date" class="date-input" v-model="date" />
      <button class="btn btn-primary" @click="load" :disabled="loading">🔍 查询</button>
    </div>

    <div class="card">
      <div class="card-tabs">
        <div v-for="t in tabs" :key="t.key" class="card-tab" :class="{ active: tab === t.key }" @click="tab = t.key; load()">{{ t.label }}</div>
      </div>

      <div v-if="loading" class="loading"><span class="spinner"></span></div>

      <div v-if="tab === 'stocks' && !loading">
        <div v-if="items.length === 0" class="empty-state"><div class="icon">🔔</div><div class="title">暂无竞价数据</div><div class="desc">盘后无竞价，盘前9:15-9:25可查看</div></div>
        <div v-else class="table-wrap">
          <table class="data-table">
            <thead><tr><th>代码</th><th>名称</th><th class="num">开盘价</th><th class="num">昨收</th><th class="num">涨幅%</th><th class="num">竞价额</th><th class="num">量</th></tr></thead>
            <tbody>
              <tr v-for="r in items" :key="r.code">
                <td>{{ r.code }}</td><td>{{ r.name }}</td>
                <td class="num">{{ r.open_price?.toFixed(2) }}</td>
                <td class="num">{{ r.pre_close?.toFixed(2) }}</td>
                <td class="num" :class="r.pct_chg >= 0 ? 'up' : 'down'">{{ r.pct_chg?.toFixed(2) }}%</td>
                <td class="num">{{ fmtAmt(r.amount) }}</td>
                <td class="num">{{ r.volume }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div v-if="tab === 'sectors' && !loading">
        <div v-if="items.length === 0" class="empty-state"><div class="icon">📊</div><div class="title">暂无板块竞价</div></div>
        <div v-else class="table-wrap">
          <table class="data-table">
            <thead><tr><th>板块</th><th>名称</th><th class="num">涨幅%</th><th class="num">成交额</th><th class="num">涨</th><th class="num">跌</th></tr></thead>
            <tbody>
              <tr v-for="r in items" :key="r.sector_code">
                <td>{{ r.sector_code }}</td><td>{{ r.sector_name }}</td>
                <td class="num" :class="r.pct_chg >= 0 ? 'up' : 'down'">{{ r.pct_chg?.toFixed(2) }}%</td>
                <td class="num">{{ fmtAmt(r.amount) }}</td>
                <td class="num up">{{ r.rise_count }}</td>
                <td class="num down">{{ r.fall_count }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div v-if="tab === 'tail' && !loading">
        <div class="toolbar" style="margin-top:0;margin-bottom:12px">
          <select class="date-input" v-model="tailType" @change="load">
            <option value="wt">委托</option><option value="cje">成交额</option>
            <option value="close">收盘</option><option value="zf">涨幅</option>
          </select>
        </div>
        <div v-if="items.length === 0" class="empty-state"><div class="icon">📋</div><div class="title">暂无封单数据</div></div>
        <div v-else class="table-wrap">
          <table class="data-table">
            <thead><tr><th>#</th><th>代码</th><th>名称</th><th class="num">数值</th></tr></thead>
            <tbody><tr v-for="r in items" :key="r.code"><td>{{ r.rank }}</td><td>{{ r.code }}</td><td>{{ r.name }}</td><td class="num">{{ r.value?.toFixed(2) }}</td></tr></tbody>
          </table>
        </div>
      </div>

      <div v-if="tab === 'yizi' && !loading">
        <div v-if="items.length === 0" class="empty-state"><div class="icon">🔒</div><div class="title">暂无一字涨停</div></div>
        <div v-else class="table-wrap">
          <table class="data-table">
            <thead><tr><th>代码</th><th>名称</th><th class="num">涨幅%</th><th class="num">成交额</th></tr></thead>
            <tbody><tr v-for="r in items" :key="r.code"><td>{{ r.code }}</td><td>{{ r.name }}</td><td class="num up">+{{ r.pct_chg?.toFixed(2) }}%</td><td class="num">{{ fmtAmt(r.amount) }}</td></tr></tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getAuctionStocks, getAuctionSectors, getAuctionTail, getAuctionYizi } from '../api'

const date = ref(new Date().toISOString().slice(0,10))
const loading = ref(false)
const tab = ref('stocks')
const items = ref([])
const tailType = ref('wt')

const tabs = [
  { key: 'stocks', label: '个股竞价' },
  { key: 'sectors', label: '板块竞价' },
  { key: 'tail', label: '封单排行' },
  { key: 'yizi', label: '一字涨停' },
]

const fmtAmt = (v) => { if (!v) return '-'; if (v >= 1e8) return (v/1e8).toFixed(2) + '亿'; if (v >= 1e4) return (v/1e4).toFixed(0) + '万'; return v }

async function load() {
  loading.value = true
  try {
    let data
    if (tab.value === 'stocks') ({ data } = await getAuctionStocks({ date: date.value, limit: 100 }))
    else if (tab.value === 'sectors') ({ data } = await getAuctionSectors({ date: date.value, limit: 100 }))
    else if (tab.value === 'tail') ({ data } = await getAuctionTail({ date: date.value, tail_type: tailType.value, limit: 50 }))
    else ({ data } = await getAuctionYizi(date.value))
    items.value = data.items || []
  } catch { items.value = [] }
  loading.value = false
}

onMounted(load)
</script>
