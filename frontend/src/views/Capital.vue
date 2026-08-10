<template>
  <div>
    <div class="page-header">
      <div class="page-title">💰 资金流向</div>
      <div class="page-subtitle">{{ date }} · 个股/板块资金分析</div>
    </div>

    <div class="toolbar">
      <input type="date" class="date-input" v-model="date" />
      <button class="btn btn-primary" @click="load" :disabled="loading">🔍 查询</button>
    </div>

    <div class="card">
      <div class="card-tabs">
        <div class="card-tab" :class="{ active: tab === 'stock' }" @click="tab = 'stock'; load()">个股资金</div>
        <div class="card-tab" :class="{ active: tab === 'sector' }" @click="tab = 'sector'; load()">板块资金</div>
      </div>

      <div v-if="loading" class="loading"><span class="spinner"></span></div>

      <div v-if="tab === 'stock' && !loading">
        <div v-if="stockItems.length > 0">
          <div class="toolbar" style="margin-top:0;margin-bottom:12px">
            <select class="date-input" v-model="sortBy" @change="load">
              <option value="main_net">主力净流入</option>
              <option value="super_large_net">超大单</option>
              <option value="large_net">大单</option>
            </select>
            <select class="date-input" v-model="direction" @change="load">
              <option value="desc">净流入 ↓</option>
              <option value="asc">净流出 ↓</option>
            </select>
          </div>
          <div class="table-wrap">
            <table class="data-table">
              <thead><tr><th>代码</th><th>名称</th><th class="num">主力净流入</th><th class="num">超大单</th><th class="num">大单</th><th class="num">中单</th><th class="num">小单</th><th class="num">主力占比</th></tr></thead>
              <tbody>
                <tr v-for="r in stockItems" :key="r.code">
                  <td>{{ r.code }}</td><td>{{ r.name }}</td>
                  <td class="num" :class="r.main_net >= 0 ? 'up' : 'down'">{{ fmtAmt(r.main_net) }}</td>
                  <td class="num" :class="r.super_large_net >= 0 ? 'up' : 'down'">{{ fmtAmt(r.super_large_net) }}</td>
                  <td class="num" :class="r.large_net >= 0 ? 'up' : 'down'">{{ fmtAmt(r.large_net) }}</td>
                  <td class="num" :class="r.medium_net >= 0 ? 'up' : 'down'">{{ fmtAmt(r.medium_net) }}</td>
                  <td class="num" :class="r.small_net >= 0 ? 'up' : 'down'">{{ fmtAmt(r.small_net) }}</td>
                  <td class="num">{{ r.main_pct?.toFixed(2) }}%</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        <div v-else class="empty-state">
          <div class="icon">📊</div>
          <div class="title">暂无资金数据</div>
          <div class="desc">上游数据源暂不可用，请稍后再试</div>
        </div>
      </div>

      <div v-if="tab === 'sector' && !loading">
        <div v-if="sectorItems.length > 0" class="table-wrap">
          <table class="data-table">
            <thead><tr><th>板块</th><th class="num">涨幅%</th><th class="num">主力净流入</th><th class="num">总净流入</th><th class="num">涨</th><th class="num">跌</th><th>领涨股</th><th class="num">领涨%</th></tr></thead>
            <tbody>
              <tr v-for="r in sectorItems" :key="r.sector_code">
                <td>{{ r.sector_name }}</td>
                <td class="num" :class="r.change_pct >= 0 ? 'up' : 'down'">{{ r.change_pct?.toFixed(2) }}%</td>
                <td class="num" :class="r.main_net >= 0 ? 'up' : 'down'">{{ fmtAmt(r.main_net) }}</td>
                <td class="num" :class="r.total_net >= 0 ? 'up' : 'down'">{{ fmtAmt(r.total_net) }}</td>
                <td class="num up">{{ r.rise_count }}</td>
                <td class="num down">{{ r.fall_count }}</td>
                <td>{{ r.leader_name || '-' }}</td>
                <td class="num up">{{ r.leader_pct?.toFixed(2) }}%</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="empty-state">
          <div class="icon">🏗️</div>
          <div class="title">板块资金数据暂不可用</div>
          <div class="desc">上游板块资金接口维护中</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getCapitalFlow, getSectorFlow } from '../api'

const date = ref(new Date().toISOString().slice(0,10))
const loading = ref(false)
const tab = ref('stock')
const stockItems = ref([])
const sectorItems = ref([])
const sortBy = ref('main_net')
const direction = ref('desc')

const fmtAmt = (v) => { if (!v) return '-'; if (Math.abs(v) >= 1e8) return (v/1e8).toFixed(2) + '亿'; if (Math.abs(v) >= 1e4) return (v/1e4).toFixed(0) + '万'; return v?.toString() }

async function load() {
  loading.value = true
  if (tab.value === 'stock') {
    try { const { data } = await getCapitalFlow({ date: date.value, limit: 100, sort_by: sortBy.value, direction: direction.value }); stockItems.value = data.items || [] } catch { stockItems.value = [] }
  } else {
    try { const { data } = await getSectorFlow({ date: date.value, limit: 100 }); sectorItems.value = data.items || [] } catch { sectorItems.value = [] }
  }
  loading.value = false
}

onMounted(load)
</script>
