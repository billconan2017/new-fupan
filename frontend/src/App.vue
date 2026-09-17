<template>
  <div class="app-layout" :data-theme="currentTheme">
    <!-- 顶部窄Header (60px)：日期 + 主线 + 主题切换，仅此一行 -->
    <header class="app-header">
      <div class="header-left">
        <span class="header-logo">📊 FuPanX</span>
      </div>
      <div class="header-right">
        <input type="date" class="date-input" v-model="globalDate" />
        <select class="date-input" v-model="mainlineFilter">
          <option value="">全部主线</option>
          <option value="半导体">半导体</option>
          <option value="新能源">新能源</option>
          <option value="AI">AI</option>
          <option value="军工">军工</option>
        </select>
        <div class="theme-switch">
          <div v-for="t in themes" :key="t.key" class="theme-dot" :class="{ active: currentTheme === t.key }"
            :data-theme="t.key" :title="t.label" @click="setTheme(t.key)"></div>
        </div>
      </div>
    </header>

    <div class="app-body">
      <!-- 左侧固定菜单栏 (220px)：全部7个页面常驻 -->
      <aside class="app-sidebar">
        <div class="sidebar-label">数据总览</div>
        <router-link to="/cockpit" class="nav-item"><span class="nav-icon">◎</span><span>复盘与盘中总控</span></router-link>
        <router-link to="/" custom v-slot="{ isActive, navigate }">
          <div class="nav-item" :class="{ active: isActive }" @click="navigate">
            <span class="nav-icon">📊</span><span>大盘总览</span>
          </div>
        </router-link>

        <div class="sidebar-label">盘前竞价</div>
        <router-link to="/auction" custom v-slot="{ isActive, navigate }">
          <div class="nav-item" :class="{ active: isActive }" @click="navigate">
            <span class="nav-icon">🔔</span><span>竞价数据</span>
          </div>
        </router-link>

        <div class="sidebar-label">盘中监控</div>
        <router-link to="/pools" custom v-slot="{ isActive, navigate }">
          <div class="nav-item" :class="{ active: isActive }" @click="navigate">
            <span class="nav-icon">📈</span><span>涨跌停池</span>
          </div>
        </router-link>
        <router-link to="/sector" custom v-slot="{ isActive, navigate }">
          <div class="nav-item" :class="{ active: isActive }" @click="navigate">
            <span class="nav-icon">🔥</span><span>板块热力</span>
          </div>
        </router-link>

        <div class="sidebar-label">盘后复盘</div>
        <router-link to="/dragon" custom v-slot="{ isActive, navigate }">
          <div class="nav-item" :class="{ active: isActive }" @click="navigate">
            <span class="nav-icon">🐉</span><span>龙虎榜</span>
          </div>
        </router-link>
        <router-link to="/capital" custom v-slot="{ isActive, navigate }">
          <div class="nav-item" :class="{ active: isActive }" @click="navigate">
            <span class="nav-icon">💰</span><span>资金流向</span>
          </div>
        </router-link>
        <router-link to="/review" custom v-slot="{ isActive, navigate }">
          <div class="nav-item" :class="{ active: isActive }" @click="navigate">
            <span class="nav-icon">📋</span><span>复盘报告</span>
          </div>
        </router-link>

        <div class="sidebar-label">策略与交易</div>
        <router-link to="/strategy" custom v-slot="{ isActive, navigate }">
          <div class="nav-item" :class="{ active: isActive }" @click="navigate">
            <span class="nav-icon">🎯</span><span>策略选股</span>
          </div>
        </router-link>
        <router-link to="/live-trading" custom v-slot="{ isActive, navigate }">
          <div class="nav-item" :class="{ active: isActive }" @click="navigate">
            <span class="nav-icon">💼</span><span>实盘组合</span>
          </div>
        </router-link>
        <div class="sidebar-label">系统</div>
        <router-link to="/admin/data-sources" custom v-slot="{ isActive, navigate }">
          <div class="nav-item" :class="{ active: isActive }" @click="navigate">
            <span class="nav-icon">🗄️</span><span>数据源状态</span>
          </div>
        </router-link>
      </aside>

      <!-- 主体内容 -->
      <main class="app-main">
        <!-- 页面标题栏 -->
        <div class="page-title-bar">
          <div class="page-title">{{ currentTitle }}</div>
          <div class="page-subtitle">{{ currentSubtitle }}</div>
        </div>
        <!-- 版心容器 -->
        <div class="content-box">
          <router-view v-slot="{ Component }">
            <keep-alive :include="cachedViews">
              <component :is="Component" />
            </keep-alive>
          </router-view>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const themes = [
  { key: 'paper', label: '浅色商务' },
  { key: 'dark', label: '暗色' },
  { key: 'ocean', label: '海洋蓝' },
  { key: 'midnight', label: '午夜紫' },
]

const currentTheme = ref(localStorage.getItem('fupanx-theme') || 'paper')
const globalDate = ref(new Date().toISOString().slice(0, 10))
const mainlineFilter = ref('')
const cachedViews = ['Dashboard', 'Pools', 'Auction', 'Sector', 'Dragon', 'Capital', 'Review', 'Strategy', 'LiveTrading']

const pageTitles = {
  '/cockpit': ['复盘与盘中总控', '昨日证据 · 今日观察 · 数据时效'],
  '/admin/data-sources': ['数据源状态', '接口调用 · 数据日期 · 采集任务'],
  '/': ['大盘总览', '市场情绪 · 涨跌统计 · 复盘评分'],
  '/auction': ['竞价数据', '板块竞价 · 个股竞价 · 封单排行'],
  '/pools': ['涨跌停池', '涨停 · 跌停 · 炸板 · 强势股'],
  '/sector': ['板块热力', '板块涨跌热力图 · 轮动分析'],
  '/dragon': ['龙虎榜', '龙虎榜明细数据'],
  '/capital': ['资金流向', '个股/板块资金分析'],
  '/review': ['复盘报告', '综合评分 · 多维分析'],
  '/strategy': ['策略选股', '多条件筛选 · 方案管理 · 历史回测'],
  '/live-trading': ['实盘组合', '持仓 · 委托 · 成交 · 风控'],
}

const currentTitle = computed(() => pageTitles[route.path]?.[0] || 'FuPanX')
const currentSubtitle = computed(() => pageTitles[route.path]?.[1] || '')

function setTheme(key) {
  currentTheme.value = key
  localStorage.setItem('fupanx-theme', key)
}

onMounted(() => {
  const saved = localStorage.getItem('fupanx-theme')
  if (saved) currentTheme.value = saved
})
</script>
