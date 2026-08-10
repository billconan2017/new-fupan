<template>
  <div>
    <div class="page-header">
      <div class="page-title">🐉 龙虎榜</div>
      <div class="page-subtitle">{{ date }} · 龙虎榜明细数据</div>
    </div>

    <div class="toolbar">
      <input type="date" class="date-input" v-model="date" />
      <button class="btn btn-primary" @click="load" :disabled="loading">🔍 查询</button>
    </div>

    <div class="card">
      <div v-if="loading" class="loading"><span class="spinner"></span></div>

      <div v-if="!loading && items.length === 0" class="empty-state">
        <div class="icon">🐉</div>
        <div class="title">今日暂无龙虎榜单数据</div>
        <div class="desc">龙虎榜通常在收盘后公布</div>
      </div>

      <div v-if="!loading && items.length > 0">
        <div class="table-wrap">
          <table class="data-table">
            <thead><tr>
              <th>代码</th><th>名称</th><th class="num">收盘</th><th class="num">涨幅%</th>
              <th class="num">买入额</th><th class="num">卖出额</th><th class="num">净额</th>
              <th>上榜原因</th>
            </tr></thead>
            <tbody>
              <tr v-for="r in items" :key="r.code">
                <td>{{ r.code }}</td><td>{{ r.name }}</td>
                <td class="num">{{ r.close?.toFixed(2) }}</td>
                <td class="num" :class="r.pct_chg >= 0 ? 'up' : 'down'">{{ r.pct_chg?.toFixed(2) }}%</td>
                <td class="num up">{{ fmtAmt(r.buy_amount) }}</td>
                <td class="num down">{{ fmtAmt(r.sell_amount) }}</td>
                <td class="num" :class="r.net_amount >= 0 ? 'up' : 'down'">{{ fmtAmt(r.net_amount) }}</td>
                <td style="max-width:220px;overflow:hidden;text-overflow:ellipsis" :title="r.reason">{{ r.reason || '-' }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="total > limit" class="pagination">
          <button :disabled="offset === 0" @click="offset = 0; load()">首页</button>
          <button :disabled="offset === 0" @click="offset -= limit; load()">上一页</button>
          <span class="current">{{ Math.floor(offset/limit)+1 }} / {{ Math.ceil(total/limit) }}</span>
          <button :disabled="offset+limit >= total" @click="offset += limit; load()">下一页</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getDragonTiger } from '../api'

const date = ref(new Date().toISOString().slice(0,10))
const loading = ref(false)
const items = ref([])
const total = ref(0)
const offset = ref(0)
const limit = 50

const fmtAmt = (v) => { if (!v) return '-'; if (Math.abs(v) >= 1e8) return (v/1e8).toFixed(2) + '亿'; if (Math.abs(v) >= 1e4) return (v/1e4).toFixed(0) + '万'; return v?.toString() }

async function load() {
  loading.value = true
  try {
    const { data } = await getDragonTiger({ date: date.value, limit, offset: offset.value })
    items.value = data.items || []
    total.value = data.total || 0
  } catch { items.value = [] }
  loading.value = false
}

onMounted(load)
</script>
