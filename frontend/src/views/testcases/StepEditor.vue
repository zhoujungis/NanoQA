<template>
  <div class="step-editor">
    <div class="step-head">
      <span class="col-index">序号</span>
      <span class="col-text">操作</span>
      <span class="col-text">预期结果</span>
      <span class="col-actions">排序 / 操作</span>
    </div>

    <div
      v-for="(row, index) in rows"
      :key="row.key"
      class="step-row"
      :class="{ 'is-dragging': draggingKey === row.key, 'is-drop': dropKey === row.key }"
      @dragover.prevent="dropKey = row.key"
      @dragleave="dropKey = null"
      @drop.prevent="onDrop(index)"
    >
      <span
        class="drag-handle"
        draggable="true"
        title="拖动排序"
        @dragstart="onDragStart($event, row.key)"
        @dragend="onDragEnd"
      >
        <el-icon><Rank /></el-icon>
      </span>
      <span class="col-index step-index">{{ index + 1 }}</span>
      <div class="col-text">
        <el-input
          v-model="row.action"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 6 }"
          placeholder="操作描述，如：输入手机号 13800138000"
          @input="emitChange"
        />
      </div>
      <div class="col-text">
        <el-input
          v-model="row.expected"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 6 }"
          placeholder="预期结果，如：输入成功，进入首页"
          @input="emitChange"
        />
      </div>
      <div class="col-actions">
        <el-button
          class="icon-btn"
          text
          size="small"
          title="上移"
          :disabled="index === 0"
          @click="moveStep(index, -1)"
        >
          <el-icon><Top /></el-icon>
        </el-button>
        <el-button
          class="icon-btn"
          text
          size="small"
          title="下移"
          :disabled="index === rows.length - 1"
          @click="moveStep(index, 1)"
        >
          <el-icon><Bottom /></el-icon>
        </el-button>
        <el-button class="icon-btn" text size="small" title="复制本步" @click="duplicateStep(index)">
          <el-icon><CopyDocument /></el-icon>
        </el-button>
        <el-button
          class="icon-btn danger"
          text
          size="small"
          title="删除本步"
          @click="removeStep(index)"
        >
          <el-icon><Delete /></el-icon>
        </el-button>
      </div>
    </div>

    <div class="step-foot">
      <el-button size="small" plain @click="addStep">
        <el-icon><Plus /></el-icon>
        <span class="btn-text">添加步骤</span>
      </el-button>
      <span v-if="!rows.length" class="step-empty-hint">至少需要 1 个步骤</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Bottom, CopyDocument, Delete, Plus, Rank, Top } from '@element-plus/icons-vue'
import type { StepItem } from './shared'

const props = defineProps<{
  modelValue: StepItem[]
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: StepItem[]): void
}>()

/** 本地行数据：额外带渲染 key，保证拖拽/排序时输入框状态稳定 */
interface EditRow {
  key: number
  action: string
  expected: string
}

const rows = ref<EditRow[]>([])
const draggingKey = ref<number | null>(null)
const dropKey = ref<number | null>(null)
let keySeed = 0

watch(
  () => props.modelValue,
  (value) => {
    const next = (value || []).map((item) => ({
      key: ++keySeed,
      action: item.action,
      expected: item.expected,
    }))
    // 内容一致则不重建，避免输入时光标跳动
    const same =
      next.length === rows.value.length &&
      next.every(
        (row, index) =>
          row.action === rows.value[index].action && row.expected === rows.value[index].expected,
      )
    if (!same) rows.value = next
  },
  { immediate: true },
)

function emitChange() {
  emit(
    'update:modelValue',
    rows.value.map((row, index) => ({
      order: index + 1,
      action: row.action,
      expected: row.expected,
    })),
  )
}

function addStep() {
  rows.value.push({ key: ++keySeed, action: '', expected: '' })
  emitChange()
}

function removeStep(index: number) {
  rows.value.splice(index, 1)
  emitChange()
}

function duplicateStep(index: number) {
  const source = rows.value[index]
  rows.value.splice(index + 1, 0, { key: ++keySeed, action: source.action, expected: source.expected })
  emitChange()
}

function moveStep(index: number, delta: number) {
  const target = index + delta
  if (target < 0 || target >= rows.value.length) return
  const [row] = rows.value.splice(index, 1)
  rows.value.splice(target, 0, row)
  emitChange()
}

function onDragStart(event: DragEvent, key: number) {
  draggingKey.value = key
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', String(key))
  }
}

function onDragEnd() {
  draggingKey.value = null
  dropKey.value = null
}

/** 原生拖拽排序：拖到目标行即插入其位置 */
function onDrop(index: number) {
  dropKey.value = null
  const fromKey = draggingKey.value
  draggingKey.value = null
  if (fromKey === null) return
  const from = rows.value.findIndex((row) => row.key === fromKey)
  if (from < 0 || from === index) return
  const [row] = rows.value.splice(from, 1)
  rows.value.splice(index, 0, row)
  emitChange()
}
</script>

<style scoped>
.step-editor {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.step-head,
.step-row {
  display: grid;
  grid-template-columns: 28px 32px minmax(0, 1fr) minmax(0, 1fr) 128px;
  align-items: start;
  gap: var(--sp-2);
  padding: var(--sp-2) var(--sp-3);
}

.step-head {
  background: var(--bg-sunken);
  border-bottom: 1px solid var(--border-light);
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--text-secondary);
  align-items: center;
}

.step-row {
  border-bottom: 1px solid var(--border-light);
  transition: background-color var(--dur-fast) var(--ease-out);
}

.step-row:last-of-type {
  border-bottom: none;
}

.step-row:hover {
  background: var(--bg-hover);
}

.step-row.is-dragging {
  opacity: 0.55;
}

.step-row.is-drop {
  box-shadow: inset 0 2px 0 -1px var(--accent-500);
}

.drag-handle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 24px;
  margin-top: 2px;
  color: var(--text-placeholder);
  cursor: grab;
}

.drag-handle:hover {
  color: var(--text-secondary);
}

.step-index {
  font-variant-numeric: tabular-nums;
  color: var(--text-tertiary);
  line-height: 24px;
  text-align: center;
}

.col-actions {
  display: flex;
  align-items: center;
  gap: 0;
  line-height: 24px;
}

.col-actions .icon-btn {
  padding: 2px;
  margin: 0;
  height: 22px;
  color: var(--text-tertiary);
}

.col-actions .icon-btn:hover {
  color: var(--accent-600);
}

.col-actions .icon-btn.danger:hover {
  color: var(--danger-600);
}

.step-foot {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-2) var(--sp-3);
  border-top: 1px solid var(--border-light);
  background: var(--bg-surface);
}

.btn-text {
  margin-left: 4px;
}

.step-empty-hint {
  color: var(--danger-600);
  font-size: var(--fs-sm);
}
</style>
