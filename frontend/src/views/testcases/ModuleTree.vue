<template>
  <aside class="module-tree">
    <div class="module-tree-head">
      <span class="module-tree-title">模块</span>
      <el-checkbox
        class="module-tree-check"
        :model-value="includeSubmodules"
        size="small"
        @change="onIncludeChange"
      >
        含子模块
      </el-checkbox>
    </div>

    <!-- 加载态 -->
    <div v-if="loading" v-loading="loading" class="module-tree-state" element-loading-text="加载中" />

    <!-- 错误态 -->
    <div v-else-if="error" class="module-tree-state">
      <p class="state-text">{{ error }}</p>
      <el-button size="small" text type="primary" @click="emit('retry')">重试</el-button>
    </div>

    <template v-else>
      <!-- 全部用例：清空模块过滤 -->
      <div
        class="tree-row all-row"
        :class="{ 'is-active': selectedId === null, 'is-drop': dragOverId === ALL_KEY }"
        @click="emit('select', null)"
        @dragenter.prevent="dragOverId = ALL_KEY"
        @dragover.prevent
        @dragleave="dragOverId = null"
        @drop.prevent="onDrop($event, null)"
      >
        <span class="tree-node-name">全部用例</span>
        <span class="tree-node-count">{{ total }}</span>
      </div>

      <!-- 空态 -->
      <div v-if="!nodes.length" class="module-tree-state">
        <p class="state-text">暂无模块，用例将归入「未分类」</p>
      </div>

      <el-tree
        v-else
        ref="treeRef"
        class="module-el-tree"
        :data="nodes"
        node-key="id"
        :props="{ children: 'children', label: 'name' }"
        :expand-on-click-node="false"
        default-expand-all
        highlight-current
        @node-click="onNodeClick"
      >
        <template #default="{ data }">
          <div
            class="tree-row"
            :class="{ 'is-drop': dragOverId === data.id }"
            @dragenter.prevent="dragOverId = data.id"
            @dragover.prevent
            @dragleave="dragOverId = null"
            @drop.prevent="onDrop($event, data.id)"
          >
            <span class="tree-node-name">{{ data.name }}</span>
            <span class="tree-node-count">{{ data.case_count }}</span>
          </div>
        </template>
      </el-tree>
    </template>
  </aside>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import type { ModuleNode } from './shared'

const props = defineProps<{
  nodes: ModuleNode[]
  total: number
  selectedId: number | null
  includeSubmodules: boolean
  loading?: boolean
  error?: string | null
}>()

const emit = defineEmits<{
  (e: 'select', id: number | null): void
  (e: 'update:includeSubmodules', value: boolean): void
  (e: 'drop-case', payload: { caseId: number; moduleId: number | null }): void
  (e: 'retry'): void
}>()

/** 「全部用例」行的拖拽高亮标记（模块节点用自身 id） */
const ALL_KEY = -1
const dragOverId = ref<number | null>(null)
const treeRef = ref<{ setCurrentKey: (key: number | undefined) => void } | null>(null)

watch(
  () => props.selectedId,
  (id) => treeRef.value?.setCurrentKey(id ?? undefined),
  { immediate: true },
)

function onNodeClick(data: ModuleNode) {
  emit('select', data.id)
}

function onIncludeChange(value: boolean | string | number) {
  emit('update:includeSubmodules', Boolean(value))
}

/** 行拖放（列表行标题拖出）→ 移动用例到目标模块 */
function onDrop(event: DragEvent, moduleId: number | null) {
  dragOverId.value = null
  const raw = event.dataTransfer?.getData('text/case-id') || event.dataTransfer?.getData('text/plain')
  const caseId = Number(raw)
  if (!raw || !Number.isFinite(caseId)) return
  emit('drop-case', { caseId, moduleId })
}
</script>

<style scoped>
.module-tree {
  width: 232px;
  flex: none;
  display: flex;
  flex-direction: column;
  background: var(--bg-surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.module-tree-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
  padding: var(--sp-2) var(--sp-3);
  border-bottom: 1px solid var(--border-light);
}

.module-tree-title {
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--text-secondary);
  letter-spacing: 0.04em;
}

.module-tree-check {
  margin-right: 0;
}

.module-tree-state {
  min-height: 120px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--sp-2);
  padding: var(--sp-4);
}

.state-text {
  margin: 0;
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
  text-align: center;
}

.all-row {
  border-bottom: 1px solid var(--border-light);
}

.tree-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
  width: 100%;
  padding: 0 var(--sp-3) 0 var(--sp-2);
  min-height: 28px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background-color var(--dur-fast) var(--ease-out);
}

.tree-row:hover {
  background: var(--bg-hover);
}

.tree-row.is-active {
  background: var(--bg-active);
}

.tree-row.is-drop {
  background: var(--accent-50);
  box-shadow: inset 0 0 0 1px var(--accent-500);
}

.tree-node-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--fs-base);
  color: var(--text-primary);
}

.tree-node-count {
  flex: none;
  font-size: var(--fs-xs);
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}

.module-el-tree {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: var(--sp-1);
  background: transparent;
}

.module-el-tree :deep(.el-tree-node__content) {
  height: 28px;
  border-radius: var(--radius-sm);
}

.module-el-tree :deep(.el-tree-node__content:hover) {
  background: transparent;
}

.module-el-tree :deep(.el-tree-node.is-current > .el-tree-node__content .tree-row) {
  background: var(--bg-active);
}
</style>
