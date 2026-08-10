<template>
  <div class="dashboard">
    <h1>📊 仪表盘</h1>
    <el-row :gutter="16">
      <el-col :span="6" v-for="card in cards" :key="card.title">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-title">{{ card.title }}</div>
          <div class="stat-value" :class="card.color">{{ card.value }}</div>
          <div class="stat-sub">{{ card.sub }}</div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const cards = ref([
  { title: '上证指数', value: '--', color: 'num', sub: '加载中...' },
  { title: '深证成指', value: '--', color: 'num', sub: '加载中...' },
  { title: '创业板指', value: '--', color: 'num', sub: '加载中...' },
  { title: '科创50', value: '--', color: 'num', sub: '加载中...' },
])
</script>

<style scoped>
.dashboard { color: var(--text); }
.stat-card { background: var(--card); border-color: var(--border); }
.stat-title { color: var(--dim); font-size: 14px; }
.stat-value { font-size: 28px; font-family: var(--mono); margin: 8px 0; }
.stat-sub { color: var(--dim); font-size: 12px; }
.up { color: var(--up); }
.down { color: var(--down); }
</style>
