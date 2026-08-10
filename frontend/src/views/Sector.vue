<template>
  <div>
    <div class="page-header">
      <div class="page-title">🔥 板块热力</div>
      <div class="page-subtitle">{{ date }} · 板块涨跌热力图 · 轮动分析</div>
    </div>

    <div class="toolbar">
      <input type="date" class="date-input" v-model="date" />
      <button class="btn btn-primary" @click="load" :disabled="loading">🔍 查询</button>
      <select class="date-input" v-model="rotationDays" @change="loadRotation">
        <option :value="3">近3天</option><option :value="5">近5天</option><option :value="10">近10天</option>
      </select>
    </div>

    <div class="card">
      <div class="card-tabs">
        <div class="card-tab" :class="{ active: tab === 'heatmap' }" @click="tab = 'heatmap'">热力图</div>
        <div class="card-tab" :class="{ active: tab === 'rotation' }" @click="tab = 'rotation'">轮动分析</div>
      </div>

      <div v-if="loading" class="loading"><span class="spinner"></span></div>

      <div v-if="tab === 'heatmap' && !loading">
        <div v-if="heatmapItems.length > 0" class="heatmap-grid">
          <div v-for="item in heatmapItems" :key="item.sector_code" class="heatmap-cell"
            :style="{
              borderLeft: `3px solid ${item.change_pct > 0 ? 'var(--color-up)' : 'var(--color-down)'}`,
              background: item.change_pct > 0 ? 'var(--bg-tag-red)' : 'var(--bg-tag-green)'
            }">
            <div style="font-size:12px;font-weight:600;margin-bottom:3px">{{ item.sector_name }}</div>
            <div :style="{ fontSize: '16px', fontWeight: '700', color: item.change_pct > 0 ? 'var(--color-up)' : 'var(--color-down)' }">
              {{ item.change_pct > 0 ? '+' : '' }}{{ item.change_pct?.toFixed(2) }}%
            </div>
            <div style="font-size:10px;color:var(--text-muted);margin-top:2px">
              主力 {{ item.main_net > 0 ? '+' : '' }}{{ fmtAmt(item.main_net) }}
            </div>
          </div>
        </div>
        <div v-else class="empty-state">
          <div class="icon">🏗️</div>
          <div class="title">板块热力数据维护中</div>
          <div class="desc">上游板块资金接口暂不可用，后续将接入备用数据源</div>
        </div>
      </div>

      <div v-if="tab === 'rotation' && !loading">
        <div v-if="rotation.length > 0" class="table-wrap">
          <table class="data-table">
            <thead><tr><th>板块</th><th class="num">累计涨幅%</th><th class="num">主力净流入</th><th class="num">天数</th><th>趋势</th></tr></thead>
            <tbody>
              <tr v-for="r in rotation" :key="r.sector_code">
                <td>{{ r.sector_name }}</td>
                <td class="num" :class="r.total_pct >= 0 ? 'up' : 'down'">{{ r.total_pct?.toFixed(2) }}%</td>
                <td class="num" :class="r.total_main_net >= 0 ? 'up' : 'down'">{{ fmtAmt(r.total_main_net) }}</td>
                <td class="num">{{ r.days_count }}</td>
                <td><span class="tag" :class="r.trend === 'rising' ? 'tag-up' : r.trend === 'falling' ? 'tag-down' : 'tag-blue'">{{ r.trend === 'rising' ? '↑ 上升' : r.trend === 'falling' ? '↓ 下降' : '→ 平稳' }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="empty-state">
          <div class="icon">📈</div>
          <div class="title">轮动数据暂不可用</div>
          <div class="desc">需要连续多日板块数据</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getSectorHeatmap, getSectorRotation } from '../api'

const date = ref(new Date().toISOString().slice(0,10))
const loading = ref(false)
const tab = ref('heatmap')
const heatmapItems = ref([])
const rotation = ref([])
const rotationDays = ref(5)

const fmtAmt = (v) => { if (!v) return '-'; if (Math.abs(v) >= 1e8) return (v/1e8).toFixed(2) + '亿'; if (Math.abs(v) >= 1e4) return (v/1e4).toFixed(0) + '万'; return v?.toString() }

async function load() {
  loading.value = true
  try { const { data } = await getSectorHeatmap(date.value); heatmapItems.value = data.items || [] } catch { heatmapItems.value = [] }
  await loadRotation()
  loading.value = false
}

async function loadRotation() {
  try { const { data } = await getSectorRotation({ days: rotationDays.value, top_n: 30 }); rotation.value = data.rotation || [] } catch { rotation.value = [] }
}

onMounted(load)
</script>
