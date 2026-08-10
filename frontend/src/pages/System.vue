<template>
  <div class="system">
    <h1>⚙️ 系统</h1>
    <el-row :gutter="16">
      <el-col :span="8">
        <el-card shadow="hover"><template #header>后端状态</template><p>检查中...</p></el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover"><template #header>量脉连接</template><p>检查中...</p></el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover"><template #header>Redis 缓存</template><p>检查中...</p></el-card>
      </el-col>
    </el-row>
  </div>
</template>
