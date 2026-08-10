<template>
  <div class="stock-detail">
    <h1>📊 个股详情 - {{ $route.params.code }}</h1>
    <el-card shadow="hover"><template #header>行情数据</template><p>加载中...</p></el-card>
  </div>
</template>
