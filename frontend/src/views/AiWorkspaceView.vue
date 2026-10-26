<template>
  <section class="page">
    <PageHeader title="AI 助手" subtitle="AI 生成用例草案、评审与检测；所有输出均为草案，人工审核后才会进入正式用例库">
      <template #actions>
        <el-button @click="refreshTasks">刷新任务记录</el-button>
      </template>
    </PageHeader>

    <!-- 审核语义提示条：AI 输出只是草案（§38 / 坑 3） -->
    <div class="review-notice">
      <span class="notice-label">审核机制</span>
      <span class="notice-text">
        AI 输出只作为草案保存在「AI 任务记录」中；人工审核「入库」后才写入正式用例库，「丢弃」后仅保留记录，任何 AI 结果都不会自动生效。
      </span>
      <span class="notice-flow">
        <span class="flow-step">AI 生成</span>
        <span class="flow-arrow">→</span>
        <span class="flow-step">草案</span>
        <span class="flow-arrow">→</span>
        <span class="flow-step">人工审核</span>
        <span class="flow-arrow">→</span>
        <span class="flow-step is-final">正式用例库</span>
      </span>
    </div>

    <GeneratePanel
      :project-id="projectId"
      @changed="refreshTasks"
      @manual-accepted="onManualAccepted"
    />

    <AiTaskPanel
      ref="taskPanelRef"
      :project-id="projectId"
      :manual-accepted-task-ids="manualAcceptedTaskIds"
      @changed="refreshTasks"
    />

    <AssistPanel :project-id="projectId" @changed="refreshTasks" />
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import PageHeader from '@/components/ui/PageHeader.vue'
import AiTaskPanel from './ai/AiTaskPanel.vue'
import AssistPanel from './ai/AssistPanel.vue'
import GeneratePanel from './ai/GeneratePanel.vue'

const route = useRoute()
const projectId = Number(route.params.projectId)

const taskPanelRef = ref<InstanceType<typeof AiTaskPanel>>()

/** 已在生成面板逐条入库的任务 id（本次会话内防止重复入库） */
const manualAcceptedTaskIds = ref(new Set<number>())

function refreshTasks() {
  taskPanelRef.value?.refresh()
}

function onManualAccepted(taskId: number) {
  manualAcceptedTaskIds.value.add(taskId)
}
</script>

<style scoped>
.page {
  padding: var(--sp-6);
}

.review-notice {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--sp-2) var(--sp-4);
  padding: var(--sp-3) var(--sp-4);
  margin-bottom: var(--sp-5);
  background: var(--accent-50);
  border: 1px solid var(--accent-100);
  border-left: 3px solid var(--accent-600);
  border-radius: var(--radius-sm);
}

.notice-label {
  flex: none;
  color: var(--accent-700);
  font-size: var(--fs-sm);
  font-weight: 600;
}

.notice-text {
  flex: 1;
  min-width: 280px;
  color: var(--text-secondary);
  font-size: var(--fs-sm);
  line-height: var(--lh-base);
}

.notice-flow {
  flex: none;
  display: flex;
  align-items: center;
  gap: var(--sp-1);
}

.flow-step {
  padding: 1px 8px;
  border: 1px solid var(--accent-100);
  border-radius: var(--radius-sm);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: var(--fs-xs);
  white-space: nowrap;
}

.flow-step.is-final {
  border-color: var(--accent-600);
  color: var(--accent-700);
  font-weight: 600;
}

.flow-arrow {
  color: var(--accent-300);
  font-size: var(--fs-xs);
}
</style>
