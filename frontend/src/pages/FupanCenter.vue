<template>
  <div class="fupan">
    <h1>📋 复盘中心</h1>
    <el-row :gutter="16">
      <el-col :span="12">
        <el-card shadow="hover"><template #header>涨停池</template><p>加载中...</p></el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover"><template #header>跌停池</template><p>加载中...</p></el-card>
      </el-col>
    </el-row>
    <el-row :gutter="16" style="margin-top:16px">
      <el-col :span="12">
        <el-card shadow="hover"><template #header>强势股池</template><p>加载中...</p></el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover"><template #header>炸板池</template><p>加载中...</p></el-card>
      </el-col>
    </el-row>
  </div>
</template>
