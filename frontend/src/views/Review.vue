<template>
  <div>
    <div class="page-header">
      <div class="page-title">📋 复盘报告</div>
      <div class="page-subtitle">{{ date }} · 综合评分 · 多维分析</div>
    </div>

    <div class="toolbar">
      <input type="date" class="date-input" v-model="date" />
      <button class="btn btn-primary" @click="loadReport" :disabled="loading">🔍 查看报告</button>
      <button class="btn btn-success" @click="generate" :disabled="generating">
        {{ generating ? '⏳ 生成中...' : '📝 生成报告' }}
      </button>
      <button class="btn" @click="tab = 'list'; loadList()">📋 历史列表</button>
    </div>

    <div class="card">
      <div class="card-tabs">
        <div class="card-tab" :class="{ active: tab === 'detail' }" @click="tab = 'detail'">报告详情</div>
        <div class="card-tab" :class="{ active: tab === 'list' }" @click="tab = 'list'; loadList()">历史列表</div>
      </div>

      <div v-if="loading || generating" class="loading"><span class="spinner"></span></div>

      <!-- 报告详情 -->
      <div v-if="tab === 'detail' && report && !loading">
        <!-- 评分环 -->
        <div style="text-align:center;padding:20px 0 16px">
          <div class="score-ring" :style="{
            background: `conic-gradient(${scoreColor(report.overall_score)} ${report.overall_score * 3.6}deg, var(--border) 0deg)`,
            color: scoreColor(report.overall_score)
          }">
            <div style="width:74px;height:74px;border-radius:50%;background:var(--bg-card);display:flex;align-items:center;justify-content:center;flex-direction:column">
              <span style="font-size:26px;font-weight:800;line-height:1">{{ report.overall_score }}</span>
              <span style="font-size:9px;color:var(--text-muted)">综合评分</span>
            </div>
          </div>
          <div style="font-size:14px;font-weight:500;color:var(--text-primary)">{{ report.overall_comment }}</div>
          <div style="font-size:11px;color:var(--text-muted);margin-top:3px">{{ report.trade_date }}</div>
        </div>

        <!-- 模块卡片网格 -->
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px">
          <!-- 情绪 -->
          <div class="card" v-if="report.emotion_summary?.available">
            <div class="card-header"><div class="card-title">🧠 情绪周期</div><span class="tag tag-blue">{{ report.emotion_summary.cycle_phase }}</span></div>
            <div class="kpi-row" style="grid-template-columns:1fr 1fr">
              <div class="stat-card"><div class="stat-label">情绪分</div><div class="stat-value" :class="report.emotion_summary.emotion_score >= 50 ? 'up' : 'down'" style="font-size:18px">{{ report.emotion_summary.emotion_score }}</div></div>
              <div class="stat-card"><div class="stat-label">封板率</div><div class="stat-value neutral" style="font-size:18px">{{ report.emotion_summary.seal_rate }}%</div></div>
            </div>
          </div>

          <!-- 涨停 -->
          <div class="card" v-if="report.limit_up_analysis?.available">
            <div class="card-header"><div class="card-title">🔴 涨停分析</div><span class="tag tag-up">{{ report.limit_up_analysis.count }}只</span></div>
            <div style="font-size:12px;color:var(--text-secondary)">最高连板: <strong style="color:var(--color-up)">{{ report.limit_up_analysis.highest_consecutive }}板</strong></div>
            <div v-if="report.limit_up_analysis.top_industries?.length" style="margin-top:8px;display:flex;flex-wrap:wrap;gap:4px">
              <span v-for="ind in report.limit_up_analysis.top_industries" :key="ind.industry" class="tag tag-blue">{{ ind.industry }}({{ ind.count }})</span>
            </div>
          </div>

          <!-- 跌停 -->
          <div class="card" v-if="report.limit_down_analysis?.available">
            <div class="card-header"><div class="card-title">🟢 跌停分析</div><span class="tag tag-down">{{ report.limit_down_analysis.count }}只</span></div>
          </div>

          <!-- 炸板 -->
          <div class="card" v-if="report.broken_board_analysis?.available">
            <div class="card-header"><div class="card-title">💥 炸板分析</div><span class="tag tag-orange">{{ report.broken_board_analysis.count }}只</span></div>
          </div>

          <!-- 强势股 -->
          <div class="card" v-if="report.strong_stocks?.available">
            <div class="card-header"><div class="card-title">💪 强势股</div><span class="tag tag-purple">{{ report.strong_stocks.count }}只</span></div>
            <div v-if="report.strong_stocks.industry_distribution" style="display:flex;flex-wrap:wrap;gap:4px">
              <span v-for="(v, k) in report.strong_stocks.industry_distribution" :key="k" class="tag tag-blue">{{ k }}({{ v }})</span>
            </div>
          </div>

          <!-- 龙虎榜 -->
          <div class="card" v-if="report.dragon_tiger_summary?.available">
            <div class="card-header"><div class="card-title">🐉 龙虎榜</div><span class="tag tag-blue">{{ report.dragon_tiger_summary.count }}只</span></div>
            <div style="font-size:12px;color:var(--text-secondary)">净买入: <strong :class="report.dragon_tiger_summary.net_buy_total > 0 ? 'up' : 'down'">{{ fmtAmt(report.dragon_tiger_summary.net_buy_total) }}</strong></div>
          </div>
        </div>
      </div>

      <div v-if="tab === 'detail' && !report && !loading" class="empty-state">
        <div class="icon">📋</div>
        <div class="title">暂无报告</div>
        <div class="desc">点击「生成报告」创建当日复盘</div>
      </div>

      <!-- 历史列表 -->
      <div v-if="tab === 'list' && !loading">
        <div v-if="listItems.length === 0" class="empty-state"><div class="icon">📋</div><div class="title">暂无历史报告</div></div>
        <div v-else class="table-wrap">
          <table class="data-table">
            <thead><tr><th>日期</th><th class="num">评分</th><th>评语</th><th>生成时间</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="r in listItems" :key="r.trade_date">
                <td>{{ r.trade_date }}</td>
                <td class="num"><span style="font-weight:700;font-size:16px" :style="{ color: scoreColor(r.overall_score) }">{{ r.overall_score }}</span></td>
                <td style="max-width:320px;overflow:hidden;text-overflow:ellipsis">{{ r.overall_comment }}</td>
                <td style="font-size:11px;color:var(--text-muted)">{{ r.created_at }}</td>
                <td><button class="btn btn-sm" @click="date = r.trade_date; tab = 'detail'; loadReport()">查看</button></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getReviewReport, getReviewList, generateReview } from '../api'

const date = ref(new Date().toISOString().slice(0,10))
const loading = ref(false)
const generating = ref(false)
const tab = ref('detail')
const report = ref(null)
const listItems = ref([])

const scoreColor = (s) => s >= 65 ? 'var(--color-down)' : s >= 40 ? 'var(--color-orange)' : 'var(--color-up)'
const fmtAmt = (v) => { if (!v) return '-'; if (Math.abs(v) >= 1e8) return (v/1e8).toFixed(2) + '亿'; if (Math.abs(v) >= 1e4) return (v/1e4).toFixed(0) + '万'; return v?.toString() }

async function loadReport() {
  loading.value = true
  try { const { data } = await getReviewReport(date.value); report.value = data.ok ? data.report : null } catch { report.value = null }
  loading.value = false
}

async function loadList() {
  loading.value = true
  try { const { data } = await getReviewList({ limit: 50 }); listItems.value = data.items || [] } catch { listItems.value = [] }
  loading.value = false
}

async function generate() {
  generating.value = true
  try { await generateReview(date.value); await loadReport(); tab.value = 'detail' } catch {}
  generating.value = false
}

onMounted(loadReport)
</script>
