<template>
  <el-dialog
    :model-value="modelValue"
    title="审核入库完成"
    width="520px"
    :close-on-click-modal="false"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <p class="result-tip">
      以下 {{ cases.length }} 条草案已通过人工审核并写入正式用例库（初始状态为「草稿」），可在用例管理中继续编辑与激活。
    </p>
    <ul class="case-list">
      <li v-for="item in cases" :key="item.id" class="case-item">
        <div class="case-main">
          <span class="case-key">{{ item.case_key }}</span>
          <span class="case-title">{{ item.title }}</span>
        </div>
        <div class="case-meta">
          <StatusTag :tone="priorityTone(item.priority)" :label="item.priority" />
          <span class="case-type">{{ caseTypeLabel(item.case_type) }}</span>
          <el-button link type="primary" size="small" @click="goCase(item.id)">查看用例</el-button>
        </div>
      </li>
    </ul>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">关闭</el-button>
      <el-button type="primary" @click="goList">前往用例管理</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import StatusTag from '@/components/ui/StatusTag.vue'
import { caseTypeLabel, priorityTone, type AcceptedCase } from './shared'

defineProps<{
  /** 弹窗可见性 */
  modelValue: boolean
  /** 入库成功的正式用例列表 */
  cases: AcceptedCase[]
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
}>()

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.projectId)

function goCase(caseId: number) {
  emit('update:modelValue', false)
  router.push({ name: 'testcase-detail', params: { projectId, caseId } })
}

function goList() {
  emit('update:modelValue', false)
  router.push({ name: 'testcases', params: { projectId } })
}
</script>

<style scoped>
.result-tip {
  margin: 0 0 var(--sp-3);
  color: var(--text-secondary);
  font-size: var(--fs-base);
}

.case-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
  max-height: 320px;
  overflow: auto;
}

.case-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  padding: var(--sp-2) var(--sp-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  background: var(--bg-sunken);
}

.case-main {
  display: flex;
  align-items: baseline;
  gap: var(--sp-2);
  min-width: 0;
}

.case-key {
  flex: none;
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
  color: var(--text-secondary);
}

.case-title {
  color: var(--text-primary);
  font-size: var(--fs-base);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.case-meta {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex: none;
}

.case-type {
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
}
</style>
