<template>
  <el-config-provider :locale="zhCn">
    <router-view />
    <!-- 全局命令面板 / 快捷键（Ctrl+K、?、g 前缀） -->
    <CommandPalette />
  </el-config-provider>
</template>

<script setup lang="ts">
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import CommandPalette from '@/components/CommandPalette.vue'
</script>
