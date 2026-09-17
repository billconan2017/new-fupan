<template>
  <section class="data-sources" aria-label="数据源状态">
    <div class="toolbar">
      <div><h2>数据是否到齐，一眼看清</h2><p>查看指定日期的入库情况及量脉调用状态。</p></div>
      <div class="controls"><label>交易日期 <input type="date" v-model="date" /></label>
        <button @click="load" :disabled="loading">{{ loading ? '查询中…' : '刷新状态' }}</button></div>
    </div>
    <p v-if="error" role="alert" class="error">{{ error }}</p>
    <template v-if="report">
      <div class="metrics">
        <article><span>访问凭证</span><strong>{{ report.client.tokenConfigured ? '已配置' : '未配置' }}</strong><small>状态查询不调用行情接口</small></article>
        <article><span>上游请求</span><strong>{{ report.client.remoteCalls }}</strong><small>当前服务进程累计</small></article>
        <article><span>缓存命中 / 合并请求</span><strong>{{ report.client.cacheHits }} / {{ report.client.coalesced }}</strong><small>减少重复取数</small></article>
        <article><span>调用失败</span><strong>{{ report.client.errors }}</strong><small>{{ report.client.retryAfterSeconds > 0 ? `冷却 ${report.client.retryAfterSeconds} 秒` : '当前未限流冷却' }}</small></article>
      </div>
      <p class="note">{{ report.note }} 当前显示日期：{{ report.date }}</p>
      <div class="table-wrap"><table><caption>数据入库情况</caption><thead><tr><th>数据集</th><th>最新数据日期</th><th>所选日记录数</th><th>状态</th></tr></thead>
        <tbody><tr v-for="row in report.datasets" :key="row.table"><td>{{ row.name }}</td><td>{{ row.latestDate || '—' }}</td><td>{{ row.rowCount ?? '—' }}</td>
          <td><span :class="['badge', row.status]">{{ labels[row.status] }}</span><small v-if="row.msg"> {{ row.msg }}</small></td></tr></tbody>
      </table></div>
      <div class="table-wrap"><table><caption>最近请求</caption><thead><tr><th>接口</th><th>耗时</th><th>状态码</th><th>结果</th></tr></thead><tbody>
        <tr v-for="(row, i) in report.client.recentCalls" :key="i"><td>{{ row.api }}</td><td>{{ row.elapsedMs }} ms</td><td>{{ row.code }}</td><td>{{ !row.ok ? '失败' : row.dataMissing ? '空数据' : '成功' }}</td></tr>
        <tr v-if="!report.client.recentCalls.length"><td colspan="4">当前进程尚无请求记录。</td></tr>
      </tbody></table></div>
      <div class="table-wrap"><table><caption>采集任务 · {{ report.scheduler.running ? '运行中' : '未启动' }}</caption><thead><tr><th>任务</th><th>下次执行</th></tr></thead><tbody>
        <tr v-for="job in report.scheduler.jobs" :key="job.id"><td>{{ job.name }}</td><td>{{ job.next_run || '—' }}</td></tr>
        <tr v-if="!report.scheduler.jobs.length"><td colspan="2">暂无已启动任务。</td></tr>
      </tbody></table></div>
      <p v-for="(item, key) in report.scheduler.errors" :key="key" class="error">{{ key }}：{{ item.error }}</p>
    </template>
    <p v-else-if="loading" role="status">正在读取数据状态…</p>
  </section>
</template>
<script setup>
import { onMounted, ref } from 'vue'
import { getDataQuality } from '../api'
const date = ref(new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Shanghai' }).format(new Date()))
const report = ref(null), error = ref(''), loading = ref(false)
const labels = { available: '已入库', missing: '未入库', unavailable: '查询失败' }
async function load() {
  if (!date.value) { error.value = '请选择交易日期'; return }
  loading.value = true; error.value = ''; report.value = null
  try { report.value = (await getDataQuality(date.value)).data }
  catch { error.value = '状态查询失败，请检查后端连接后重试。' }
  finally { loading.value = false }
}
onMounted(load)
</script>
<style scoped>
.data-sources{display:grid;gap:20px}.toolbar,.controls{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap}h2{margin:0;font-size:22px}p{margin:8px 0;opacity:.8}.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px}article,.table-wrap{border:1px solid #8993a333;border-radius:12px;background:var(--bg-card,transparent)}article{padding:20px;display:grid;gap:10px}article strong{font-size:30px}small{font-size:12px;opacity:.75}.note{padding:12px;border-left:3px solid #3984d6}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;text-align:left;white-space:nowrap}caption{text-align:left;padding:16px;font-weight:600}th,td{padding:12px 16px;border-top:1px solid #8993a326}th{font-size:12px;opacity:.7}.badge{padding:4px 9px;border-radius:5px;font-size:12px}.available{color:#208357;background:#20835718}.missing{color:#9a6714;background:#9a671418}.unavailable,.error{color:#c44747}.error{padding:12px;background:#c4474710}button,input{padding:9px 12px;border-radius:6px;border:1px solid #8993a355;background:transparent;color:inherit}button{background:#2769b5;color:white;cursor:pointer}button:disabled{opacity:.5}@media(max-width:800px){.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
