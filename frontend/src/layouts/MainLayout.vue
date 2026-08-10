<template>
  <el-container class="layout">
    <el-aside width="200px" class="sidebar">
      <div class="logo">📊 A股复盘</div>
      <el-menu :default-active="$route.path" router background-color="#161b22" text-color="#c9d1d9" active-color="#448aff">
        <el-menu-item index="/dashboard"><el-icon><Monitor /></el-icon><span>仪表盘</span></el-menu-item>
        <el-menu-item index="/fupan"><el-icon><DataAnalysis /></el-icon><span>复盘中心</span></el-menu-item>
        <el-menu-item index="/auction"><el-icon><Bell /></el-icon><span>集合竞价</span></el-menu-item>
        <el-menu-item index="/realtime"><el-icon><TrendCharts /></el-icon><span>实时看板</span></el-menu-item>
        <el-menu-item index="/sector"><el-icon><Grid /></el-icon><span>板块分析</span></el-menu-item>
        <el-menu-item index="/dragon"><el-icon><Trophy /></el-icon><span>龙虎榜</span></el-menu-item>
        <el-menu-item index="/finance"><el-icon><Document /></el-icon><span>财务报告</span></el-menu-item>
        <el-menu-item index="/system"><el-icon><Setting /></el-icon><span>系统</span></el-menu-item>
      </el-menu>
    </el-aside>
    <el-main class="main">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
import { Monitor, DataAnalysis, Bell, TrendCharts, Grid, Trophy, Document, Setting } from '@element-plus/icons-vue'
</script>

<style scoped>
.layout { height: 100vh; }
.sidebar { background: #161b22; border-right: 1px solid #30363d; }
.logo { padding: 20px; font-size: 18px; font-weight: bold; color: #c9d1d9; text-align: center; }
.main { padding: 20px; background: #0d1117; }
</style>
