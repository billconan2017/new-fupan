<template>
  <div>
    <div class="toolbar">
      <input type="date" class="date-input" v-model="date" />
      <button class="btn btn-primary" @click="load" :disabled="loading">🔍 查询</button>
      <button class="btn btn-success" @click="fetchData" :disabled="fetching">
        {{ fetching ? '⏳ 拉取中...' : '⬇️ 拉取数据' }}
      </button>
    </div>

    <!-- 第一行：左65%评分卡 + 右35% KPI五等分 -->
    <div class="row-score-kpi" v-if="report">
      <div class="card score-card-left">
        <div style="display:flex;align-items:center;gap:24px">
          <div style="text-align:center;min-width:110px">
            <div class="score-ring" :style="{
              background: `conic-gradient(${scoreColor(report.overall_score)} ${report.overall_score * 3.6}deg, var(--border) 0deg)`,
              color: scoreColor(report.overall_score)
            }">
              <div style="width:72px;height:72px;border-radius:50%;background:var(--bg-card);display:flex;align-items:center;justify-content:center;flex-direction:column">
                <span style="font-size:24px;font-weight:800;line-height:1">{{ report.overall_score ?? '—' }}</span>
                <span style="font-size:9px;color:var(--text-muted)">综合评分</span>
              </div>
            </div>
          </div>
          <div style="flex:1">
            <div style="font-size:14px;font-weight:600;margin-bottom:6px">盘面解读</div>
            <div style="font-size:13px;color:var(--text-secondary);line-height:1.7">{{ report.overall_comment }}</div>
          </div>
        </div>
      </div>
      <div class="kpi-row-5">
        <div v-for="s in coreStats" :key="s.label" class="stat-card" :style="{ borderLeft: `3px solid ${s.color}` }">
          <div class="stat-label">{{ s.label }}</div>
          <div class="stat-value" :style="{ color: s.color, fontSize: '20px' }">{{ s.value }}</div>
        </div>
      </div>
    </div>

    <!-- 第二行：左50%情绪面板 + 右50%涨停分布 -->
    <div class="grid-2" v-if="report">
      <div class="card" v-if="emotion?.available">
        <div class="card-header">
          <div class="card-title">🧠 情绪周期</div>
          <span class="tag tag-blue">{{ emotion.cycle_phase }}</span>
        </div>
        <div class="kpi-row-5" style="grid-template-columns:repeat(4,1fr)">
          <div class="stat-card"><div class="stat-label">情绪分</div><div class="stat-value" :class="emotion.emotion_score >= 50 ? 'up' : 'down'" style="font-size:18px">{{ emotion.emotion_score }}</div></div>
          <div class="stat-card"><div class="stat-label">封板率</div><div class="stat-value neutral" style="font-size:18px">{{ emotion.seal_rate == null ? '—' : emotion.seal_rate + '%' }}</div></div>
          <div class="stat-card"><div class="stat-label">最高板</div><div class="stat-value neutral" style="font-size:18px">{{ emotion.height_board }}</div></div>
          <div class="stat-card"><div class="stat-label">连板数</div><div class="stat-value neutral" style="font-size:18px">{{ emotion.continue_count }}</div></div>
        </div>
      </div>

      <div class="card" v-if="lu?.available">
        <div class="card-header">
          <div class="card-title">🔴 涨停连板分布</div>
          <span class="tag tag-up">{{ lu.count }}只</span>
        </div>
        <div v-for="(v, k) in lu.consecutive_distribution" :key="k" style="display:flex;gap:8px;align-items:center;margin-bottom:6px">
          <span style="width:32px;text-align:right;color:var(--text-secondary);font-size:12px;font-weight:500">{{ k }}板</span>
          <div class="progress-bar" style="flex:1">
            <div class="progress-fill" :style="{ width: Math.min(v*20,100)+'%', background: 'linear-gradient(90deg, var(--color-up), #ff7875)' }"></div>
          </div>
          <span style="width:24px;color:var(--text-muted);font-size:11px">{{ v }}</span>
        </div>
        <div v-if="lu.top_industries?.length" style="margin-top:12px">
          <div class="card-subtitle" style="margin-bottom:6px">行业 Top</div>
          <div style="display:flex;flex-wrap:wrap;gap:5px">
            <span v-for="ind in lu.top_industries" :key="ind.industry" class="tag tag-blue">{{ ind.industry }}({{ ind.count }})</span>
          </div>
        </div>
      </div>
    </div>

    <div v-if="loading" class="loading"><span class="spinner"></span> 加载中...</div>
    <div v-if="!loading && !report" class="empty-state">
      <div class="icon">📊</div>
      <div class="title">暂无复盘数据</div>
      <div class="desc">点击「拉取数据」获取当日行情</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getReviewReport, triggerFetchAll } from '../api'

const date = ref(new Date().toISOString().slice(0,10))
const loading = ref(false)
const fetching = ref(false)
const report = ref(null)
const emotion = ref(null)
const lu = ref(null)

const scoreColor = (s) => s == null ? 'var(--text-muted)' : s >= 65 ? 'var(--color-down)' : s >= 40 ? 'var(--color-orange)' : 'var(--color-up)'

const coreStats = computed(() => {
  if (!report.value) return []
  const e = report.value.emotion_summary || {}
  const lu_ = report.value.limit_up_analysis || {}
  const ld_ = report.value.limit_down_analysis || {}
  const bb_ = report.value.broken_board_analysis || {}
  return [
    { label: '情绪分', value: e.emotion_score ?? '-', color: scoreColor(e.emotion_score||0) },
    { label: '涨停', value: lu_.count ?? '-', color: 'var(--color-up)' },
    { label: '跌停', value: ld_.count ?? '-', color: 'var(--color-down)' },
    { label: '炸板', value: bb_.count ?? '-', color: 'var(--color-orange)' },
    { label: '封板率', value: (e.seal_rate ?? '-') + '%', color: 'var(--color-main)' },
  ]
})

async function load() {
  loading.value = true
  try {
    const { data } = await getReviewReport(date.value)
    if (data.ok && data.report) {
      report.value = data.report
      emotion.value = data.report.emotion_summary
      lu.value = data.report.limit_up_analysis
    } else { report.value = null }
  } catch { report.value = null }
  loading.value = false
}

async function fetchData() {
  fetching.value = true
  try { await triggerFetchAll(date.value); await load() } catch {}
  fetching.value = false
}

onMounted(load)
</script>

<style scoped>
.row-score-kpi {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 20px;
}
.score-card-left {
  display: flex;
  align-items: center;
}
</style>
