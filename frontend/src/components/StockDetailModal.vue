<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-overlay" @click.self="close">
      <div class="modal-container">
        <div class="modal-header">
          <div class="modal-title">
            <span class="stock-code">{{ code }}</span>
            <span class="stock-name">{{ name }}</span>
            <span v-if="pctChg !== null" :class="['pct-chg', pctChg >= 0 ? 'up' : 'down']">
              {{ pctChg >= 0 ? '+' : '' }}{{ pctChg?.toFixed(2) }}%
            </span>
          </div>
          <button class="modal-close" @click="close">✕</button>
        </div>

        <div class="modal-body">
          <!-- 周期切换 -->
          <KlinePeriodSelector v-model="period" />

          <!-- K线图表区域 -->
          <div class="chart-area">
            <div v-if="loading" class="chart-loading">
              <span class="spinner"></span>
              <span>加载中...</span>
            </div>
            <div v-else-if="chartData.length === 0" class="chart-empty">
              暂无数据
            </div>
            <div v-else ref="chartContainer" class="chart-container"></div>
          </div>

          <!-- K线数据摘要 -->
          <div v-if="chartData.length > 0" class="kline-summary">
            <div class="summary-item">
              <span class="label">最新</span>
              <span class="value">{{ latestBar?.close?.toFixed(2) }}</span>
            </div>
            <div class="summary-item">
              <span class="label">最高</span>
              <span class="value up">{{ latestBar?.high?.toFixed(2) }}</span>
            </div>
            <div class="summary-item">
              <span class="label">最低</span>
              <span class="value down">{{ latestBar?.low?.toFixed(2) }}</span>
            </div>
            <div class="summary-item">
              <span class="label">成交量</span>
              <span class="value">{{ formatVolume(latestBar?.volume) }}</span>
            </div>
            <div class="summary-item">
              <span class="label">数据源</span>
              <span class="value source">{{ dataSource }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch, computed, nextTick, onMounted, onBeforeUnmount } from 'vue'
import KlinePeriodSelector from './KlinePeriodSelector.vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  code: { type: String, default: '' },
  name: { type: String, default: '' },
  pctChg: { type: Number, default: null },
})

const emit = defineEmits(['close'])

const period = ref('5')
const loading = ref(false)
const chartData = ref([])
const dataSource = ref('')
const chartContainer = ref(null)
let chartInstance = null

const latestBar = computed(() => {
  if (chartData.value.length === 0) return null
  return chartData.value[chartData.value.length - 1]
})

function close() {
  emit('close')
}

function formatVolume(v) {
  if (!v) return '-'
  if (v >= 1e8) return (v / 1e8).toFixed(2) + '亿'
  if (v >= 1e4) return (v / 1e4).toFixed(1) + '万'
  return v.toFixed(0)
}

async function loadKline() {
  if (!props.code) return
  loading.value = true
  chartData.value = []
  dataSource.value = ''

  try {
    const code6 = props.code.replace(/\./g, '').substring(0, 6)
    const interval = period.value
    const url = `/api/kline/minute/${code6}?interval=${interval}&limit=120`
    const resp = await fetch(url)
    const data = await resp.json()

    if (data.ok && data.data) {
      const items = Array.isArray(data.data) ? data.data : (data.data.items || data.data.candles || [])
      chartData.value = items.map(item => ({
        time: item.time || item.trade_date || item.date || '',
        open: Number(item.open || item.o || 0),
        high: Number(item.high || item.h || 0),
        low: Number(item.low || item.l || 0),
        close: Number(item.close || item.c || 0),
        volume: Number(item.volume || item.vol || item.v || 0),
      }))
      dataSource.value = data.source || 'local'
    }
  } catch (e) {
    console.error('K线加载失败:', e)
  } finally {
    loading.value = false
    await nextTick()
    renderChart()
  }
}

function renderChart() {
  if (!chartContainer.value || chartData.value.length === 0) return

  // 简易Canvas K线渲染（无外部依赖）
  const container = chartContainer.value
  const canvas = container.querySelector('canvas') || document.createElement('canvas')
  if (!container.contains(canvas)) container.appendChild(canvas)

  const W = container.clientWidth || 600
  const H = container.clientHeight || 300
  canvas.width = W * 2
  canvas.height = H * 2
  canvas.style.width = W + 'px'
  canvas.style.height = H + 'px'

  const ctx = canvas.getContext('2d')
  ctx.scale(2, 2)
  ctx.clearRect(0, 0, W, H)

  const bars = chartData.value
  const n = bars.length
  if (n === 0) return

  const padding = { top: 20, right: 60, bottom: 30, left: 10 }
  const chartW = W - padding.left - padding.right
  const chartH = H - padding.top - padding.bottom

  // 价格范围
  let priceMin = Infinity, priceMax = -Infinity
  for (const b of bars) {
    if (b.low < priceMin) priceMin = b.low
    if (b.high > priceMax) priceMax = b.high
  }
  const priceRange = priceMax - priceMin || 1
  const barW = Math.max(1, (chartW / n) * 0.7)
  const gap = chartW / n

  // 背景网格
  ctx.strokeStyle = '#222'
  ctx.lineWidth = 0.5
  for (let i = 0; i <= 4; i++) {
    const y = padding.top + (chartH / 4) * i
    ctx.beginPath()
    ctx.moveTo(padding.left, y)
    ctx.lineTo(W - padding.right, y)
    ctx.stroke()
    // 价格标签
    const price = priceMax - (priceRange / 4) * i
    ctx.fillStyle = '#666'
    ctx.font = '10px monospace'
    ctx.fillText(price.toFixed(2), W - padding.right + 4, y + 4)
  }

  // K线绘制
  for (let i = 0; i < n; i++) {
    const b = bars[i]
    const x = padding.left + i * gap + gap / 2
    const isUp = b.close >= b.open

    const yHigh = padding.top + ((priceMax - b.high) / priceRange) * chartH
    const yLow = padding.top + ((priceMax - b.low) / priceRange) * chartH
    const yOpen = padding.top + ((priceMax - b.open) / priceRange) * chartH
    const yClose = padding.top + ((priceMax - b.close) / priceRange) * chartH

    // 影线
    ctx.strokeStyle = isUp ? '#ef4444' : '#22c55e'
    ctx.lineWidth = 1
    ctx.beginPath()
    ctx.moveTo(x, yHigh)
    ctx.lineTo(x, yLow)
    ctx.stroke()

    // 实体
    ctx.fillStyle = isUp ? '#ef4444' : '#22c55e'
    const bodyTop = Math.min(yOpen, yClose)
    const bodyH = Math.max(1, Math.abs(yClose - yOpen))
    if (isUp) {
      ctx.fillRect(x - barW / 2, bodyTop, barW, bodyH)
    } else {
      ctx.fillRect(x - barW / 2, bodyTop, barW, bodyH)
    }
  }

  // 成交量（底部20%区域）
  const volH = chartH * 0.15
  const volTop = padding.top + chartH - volH
  let volMax = 0
  for (const b of bars) {
    if (b.volume > volMax) volMax = b.volume
  }
  if (volMax > 0) {
    for (let i = 0; i < n; i++) {
      const b = bars[i]
      const x = padding.left + i * gap + gap / 2
      const h = (b.volume / volMax) * volH
      ctx.fillStyle = b.close >= b.open ? 'rgba(239,68,68,0.3)' : 'rgba(34,197,94,0.3)'
      ctx.fillRect(x - barW / 2, padding.top + chartH - h, barW, h)
    }
  }
}

// 监听周期变化
watch(period, () => {
  loadKline()
})

// 监听弹窗打开
watch(() => props.visible, (v) => {
  if (v && props.code) {
    period.value = '5'
    loadKline()
  } else {
    chartData.value = []
  }
})

// 窗口resize
function handleResize() {
  if (chartData.value.length > 0) renderChart()
}
onMounted(() => window.addEventListener('resize', handleResize))
onBeforeUnmount(() => window.removeEventListener('resize', handleResize))
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.6);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}
.modal-container {
  background: #1a1a2e;
  border: 1px solid #333;
  border-radius: 12px;
  width: 720px;
  max-width: 90vw;
  max-height: 85vh;
  overflow: auto;
}
.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #333;
}
.modal-title {
  display: flex;
  align-items: center;
  gap: 10px;
}
.stock-code {
  font-size: 16px;
  font-weight: 700;
  color: #448aff;
}
.stock-name {
  font-size: 14px;
  color: #ccc;
}
.pct-chg {
  font-size: 13px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
}
.pct-chg.up { color: #ef4444; background: rgba(239,68,68,0.1); }
.pct-chg.down { color: #22c55e; background: rgba(34,197,94,0.1); }
.modal-close {
  background: none;
  border: none;
  color: #999;
  font-size: 18px;
  cursor: pointer;
}
.modal-body {
  padding: 16px 20px;
}
.chart-area {
  margin-top: 12px;
  height: 300px;
  border: 1px solid #333;
  border-radius: 8px;
  overflow: hidden;
  position: relative;
}
.chart-container {
  width: 100%;
  height: 100%;
}
.chart-loading, .chart-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #666;
  font-size: 13px;
  gap: 8px;
}
.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid #333;
  border-top-color: #448aff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.kline-summary {
  display: flex;
  gap: 16px;
  margin-top: 12px;
  padding: 10px 0;
  border-top: 1px solid #222;
}
.summary-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.summary-item .label {
  font-size: 11px;
  color: #666;
}
.summary-item .value {
  font-size: 13px;
  font-weight: 600;
  color: #ccc;
}
.summary-item .value.up { color: #ef4444; }
.summary-item .value.down { color: #22c55e; }
.summary-item .value.source { font-size: 11px; color: #448aff; }
</style>
