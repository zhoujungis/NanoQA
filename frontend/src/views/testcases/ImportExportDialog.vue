<template>
  <el-dialog
    :model-value="modelValue"
    :title="mode === 'import' ? '导入测试用例' : '导出测试用例'"
    :width="mode === 'import' ? '880px' : '440px'"
    top="6vh"
    destroy-on-close
    class="ie-dialog"
    @update:model-value="emit('update:modelValue', $event)"
    @closed="reset"
  >
    <!-- ================= 导入向导：上传 → 映射 → 预览 → 确认 ================= -->
    <template v-if="mode === 'import'">
      <el-steps :active="step" simple class="wizard-steps">
        <el-step title="上传文件" />
        <el-step title="字段映射" />
        <el-step title="预览校验" />
        <el-step title="确认导入" />
      </el-steps>

      <!-- 步骤一：上传文件 -->
      <div v-if="step === 0" class="step-pane">
        <el-upload
          class="upload-area"
          drag
          accept=".csv,.xlsx"
          :auto-upload="false"
          :show-file-list="false"
          :limit="1"
          :on-change="onFileChange"
        >
          <div class="upload-inner">
            <p class="upload-title">拖拽文件到此处，或点击选择文件</p>
            <p class="upload-hint">支持 CSV / XLSX，单个文件不超过 10MB；上传后先预览校验，确认无误才写入</p>
          </div>
        </el-upload>
        <div v-if="importing || previewReady" class="file-card">
          <span class="file-name">{{ fileName }}</span>
          <span v-if="importing" class="file-status">解析中…</span>
          <span v-else class="file-status">
            共 {{ preview.total }} 行 · 可导入 {{ preview.valid }} · 非法 {{ preview.invalid }}
          </span>
        </div>
        <div v-if="importError" class="error-panel">
          <p class="error-text">{{ importError }}</p>
          <el-button size="small" type="primary" plain @click="runPreview()">重试</el-button>
        </div>
      </div>

      <!-- 步骤二：字段映射 -->
      <div v-else-if="step === 1" class="step-pane">
        <p class="pane-hint">
          已按中英文常见表头自动匹配，请确认或调整文件列与系统字段的对应关系（「标题」必填）。
        </p>
        <div class="mapping-grid">
          <template v-for="field in IMPORT_FIELDS" :key="field.key">
            <span class="mapping-label">
              <span v-if="field.required" class="required-mark">*</span>{{ field.label }}
            </span>
            <el-select
              v-model="mapping[field.key]"
              clearable
              :placeholder="`选择「${field.label}」对应的文件列`"
            >
              <el-option v-for="header in headers" :key="header" :label="header" :value="header" />
            </el-select>
          </template>
        </div>
      </div>

      <!-- 步骤三：预览校验 -->
      <div v-else-if="step === 2" class="step-pane">
        <div class="summary-bar">
          <span class="summary-item">共 <b>{{ preview.total }}</b> 行</span>
          <span class="summary-item ok">可导入 <b>{{ preview.valid }}</b> 行</span>
          <span class="summary-item bad">非法 <b>{{ preview.invalid }}</b> 行</span>
          <span class="summary-tip">非法行将在导入时跳过，其余行正常入库</span>
        </div>
        <el-table
          v-loading="importing"
          class="preview-table"
          :data="preview.rows"
          height="360px"
          :row-class-name="rowClassName"
          element-loading-text="校验中"
        >
          <el-table-column label="行号" prop="line" width="64" align="center" />
          <el-table-column label="动作" width="76" align="center">
            <template #default="{ row }">
              <StatusTag :tone="actionTone(row.action)" :label="actionLabel(row.action)" />
            </template>
          </el-table-column>
          <el-table-column label="标题" prop="data.title" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">{{ row.data.title || '—' }}</template>
          </el-table-column>
          <el-table-column label="模块路径" width="140" show-overflow-tooltip>
            <template #default="{ row }">{{ row.data.module || '—' }}</template>
          </el-table-column>
          <el-table-column label="优先级" width="64" align="center">
            <template #default="{ row }">{{ row.data.priority }}</template>
          </el-table-column>
          <el-table-column label="状态" width="64" align="center">
            <template #default="{ row }">{{ statusLabel(row.data.status) }}</template>
          </el-table-column>
          <el-table-column label="校验结果" min-width="220">
            <template #default="{ row }">
              <span v-if="row.errors.length" class="row-errors">{{ row.errors.join('；') }}</span>
              <span v-else class="row-ok">校验通过</span>
            </template>
          </el-table-column>
          <template #empty>
            <p class="empty-text">文件没有可导入的数据</p>
          </template>
        </el-table>
      </div>

      <!-- 步骤四：导入结果 -->
      <div v-else class="step-pane">
        <div class="result-grid">
          <div class="result-card">
            <span class="result-num">{{ result.created }}</span>
            <span class="result-label">新建</span>
          </div>
          <div class="result-card">
            <span class="result-num">{{ result.updated }}</span>
            <span class="result-label">更新</span>
          </div>
          <div class="result-card">
            <span class="result-num">{{ result.skipped }}</span>
            <span class="result-label">跳过</span>
          </div>
          <div class="result-card">
            <span class="result-num" :class="{ 'num-bad': result.failed.length }">{{ result.failed.length }}</span>
            <span class="result-label">失败</span>
          </div>
        </div>
        <template v-if="result.failed.length">
          <p class="pane-hint">以下行未能导入：</p>
          <div class="failed-list">
            <p v-for="item in result.failed" :key="item.line" class="failed-item">
              {{ item.errors.join('；') }}
            </p>
          </div>
        </template>
      </div>

    </template>

    <!-- ================= 导出 ================= -->
    <template v-else>
      <div class="export-form">
        <p class="pane-hint">选择导出格式与筛选条件，导出内容与当前用例列表口径一致。</p>
        <div class="export-row">
          <span class="mapping-label">导出格式</span>
          <el-radio-group v-model="exportForm.format">
            <el-radio value="xlsx">Excel（XLSX）</el-radio>
            <el-radio value="csv">CSV</el-radio>
          </el-radio-group>
        </div>
        <div class="export-row">
          <span class="mapping-label">模块</span>
          <el-tree-select
            v-model="exportForm.module_id"
            class="full-control"
            :data="modules"
            :props="{ value: 'id', label: 'name', children: 'children' }"
            node-key="id"
            check-strictly
            clearable
            :render-after-expand="false"
            placeholder="全部模块"
          />
        </div>
        <div class="export-row">
          <span class="mapping-label">优先级</span>
          <el-select v-model="exportForm.priority" class="full-control" clearable placeholder="全部优先级">
            <el-option v-for="item in PRIORITY_OPTIONS" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </div>
        <div class="export-row">
          <span class="mapping-label">状态</span>
          <el-select v-model="exportForm.status" class="full-control" clearable placeholder="全部状态">
            <el-option v-for="item in STATUS_OPTIONS" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </div>
        <div v-if="exportError" class="error-panel">
          <p class="error-text">{{ exportError }}</p>
        </div>
      </div>
    </template>

    <!-- footer 统一放在此处：具名插槽不能定义在 v-if/v-else 分支内部 -->
    <template #footer>
      <template v-if="mode === 'import'">
        <template v-if="step === 0">
          <el-button @click="close">取消</el-button>
          <el-button type="primary" :disabled="!previewReady" :loading="importing" @click="step = 1">
            下一步
          </el-button>
        </template>
        <template v-else-if="step === 1">
          <el-button @click="step = 0">上一步</el-button>
          <el-button type="primary" :loading="importing" @click="goPreview">校验数据</el-button>
        </template>
        <template v-else-if="step === 2">
          <el-button @click="step = 1">上一步</el-button>
          <el-button type="primary" :disabled="!preview.valid" :loading="importing" @click="confirmImport">
            确认导入{{ preview.valid }}条
          </el-button>
        </template>
        <template v-else>
          <el-button type="primary" @click="close">完成</el-button>
        </template>
      </template>
      <template v-else>
        <el-button @click="close">取消</el-button>
        <el-button type="primary" :loading="exporting" @click="runExport">导出文件</el-button>
      </template>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import type { UploadFile } from 'element-plus'
import { ElMessage } from 'element-plus'
import { api, notifyError, tokenStore, ApiError } from '@/api/client'
import StatusTag from '@/components/ui/StatusTag.vue'
import {
  PRIORITY_OPTIONS,
  STATUS_LABELS,
  STATUS_OPTIONS,
  type CaseStatus,
  type ModuleNode,
} from './shared'

type Mode = 'import' | 'export'
type ImportAction = 'create' | 'update' | 'skip'

const props = defineProps<{
  mode: Mode
  projectId: number
  modules: ModuleNode[]
  modelValue: boolean
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
  (event: 'refresh'): void
}>()

/** 导入字段（key 与后端 FIELD_LABELS 一致） */
const IMPORT_FIELDS: { key: string; label: string; required?: boolean }[] = [
  { key: 'title', label: '标题', required: true },
  { key: 'case_key', label: '用例编号' },
  { key: 'module', label: '模块路径' },
  { key: 'priority', label: '优先级' },
  { key: 'case_type', label: '类型' },
  { key: 'status', label: '状态' },
  { key: 'precondition', label: '前置条件' },
  { key: 'steps', label: '步骤' },
  { key: 'expected_result', label: '预期结果' },
  { key: 'tags', label: '标签' },
  { key: 'owner', label: '负责人' },
  { key: 'description', label: '描述' },
]

const ACTION_LABELS: Record<ImportAction, string> = {
  create: '新建',
  update: '更新',
  skip: '跳过',
}

const ACTION_TONE: Record<ImportAction, 'accent' | 'info' | 'neutral'> = {
  create: 'accent',
  update: 'info',
  skip: 'neutral',
}

interface ImportRow {
  line: number
  action: ImportAction
  errors: string[]
  data: {
    case_key: string
    title: string
    module: string
    priority: string
    case_type: string
    status: string
    precondition: string
    steps: { order: number; action: string; expected: string }[]
    expected_result: string
    tags: string[]
    owner: string
    description: string
  }
}

interface ImportPreview {
  total: number
  valid: number
  invalid: number
  headers: string[]
  mapping: Record<string, string>
  rows: ImportRow[]
}

interface ImportResult extends ImportPreview {
  created: number
  updated: number
  skipped: number
  failed: { line: number; errors: string[] }[]
}

/* ---------------- 导入向导 ---------------- */
const step = ref(0)
const fileName = ref('')
const file = ref<File | null>(null)
const headers = ref<string[]>([])
const mapping = reactive<Record<string, string>>({})
const preview = ref<ImportPreview>(emptyPreview())
const previewReady = ref(false)
const result = ref<ImportResult>(emptyResult())
const importing = ref(false)
const importError = ref<string | null>(null)

function emptyPreview(): ImportPreview {
  return { total: 0, valid: 0, invalid: 0, headers: [], mapping: {}, rows: [] }
}

function emptyResult(): ImportResult {
  return { ...emptyPreview(), created: 0, updated: 0, skipped: 0, failed: [] }
}

function statusLabel(status: string): string {
  return STATUS_LABELS[status as CaseStatus] || status
}

function rowClassName({ row }: { row: ImportRow }): string {
  return row.errors.length ? 'row-invalid' : ''
}

function actionTone(action: string): 'accent' | 'info' | 'neutral' {
  return ACTION_TONE[action as ImportAction] ?? 'neutral'
}

function actionLabel(action: string): string {
  return ACTION_LABELS[action as ImportAction] ?? action
}

function onFileChange(uploadFile: UploadFile) {
  const raw = uploadFile.raw
  if (!raw) return
  if (!/\.(csv|xlsx)$/i.test(raw.name)) {
    ElMessage.error('仅支持 CSV 或 XLSX 格式的文件')
    return
  }
  if (raw.size > 10 * 1024 * 1024) {
    ElMessage.error('文件大小不能超过 10MB')
    return
  }
  file.value = raw
  fileName.value = raw.name
  importError.value = null
  result.value = emptyResult()
  runPreview()
}

function buildFormData(dryRun: boolean): FormData {
  const formData = new FormData()
  if (file.value) formData.append('file', file.value)
  formData.append('dry_run', dryRun ? 'true' : 'false')
  const mapped: Record<string, string> = {}
  for (const field of IMPORT_FIELDS) {
    const header = mapping[field.key]
    if (header) mapped[field.key] = header
  }
  if (Object.keys(mapped).length) formData.append('mapping', JSON.stringify(mapped))
  return formData
}

function applyPreview(data: ImportPreview) {
  preview.value = data
  previewReady.value = true
  headers.value = data.headers
  for (const field of IMPORT_FIELDS) {
    mapping[field.key] = data.mapping[field.key] ?? ''
  }
}

async function runPreview() {
  if (!file.value) return
  importing.value = true
  importError.value = null
  try {
    const data = await api.post<ImportPreview>(
      `/projects/${props.projectId}/import/testcases/`,
      buildFormData(true),
    )
    applyPreview(data)
    if (step.value === 0) step.value = 1
  } catch (err) {
    importError.value = err instanceof ApiError ? err.message : '文件解析失败，请检查文件格式'
  } finally {
    importing.value = false
  }
}

async function goPreview() {
  await runPreview()
  if (importError.value) return
  if (!mapping.title) {
    ElMessage.warning('请先映射「标题」字段')
    return
  }
  step.value = 2
}

async function confirmImport() {
  importing.value = true
  try {
    result.value = await api.post<ImportResult>(
      `/projects/${props.projectId}/import/testcases/`,
      buildFormData(false),
    )
    step.value = 3
    if (result.value.created || result.value.updated) emit('refresh')
  } catch (err) {
    notifyError(err)
  } finally {
    importing.value = false
  }
}

/* ---------------- 导出 ---------------- */
const exportForm = reactive({
  format: 'xlsx' as 'csv' | 'xlsx',
  module_id: null as number | null,
  priority: '',
  status: '',
})
const exporting = ref(false)
const exportError = ref<string | null>(null)

async function runExport() {
  exporting.value = true
  exportError.value = null
  try {
    const params = new URLSearchParams({ format: exportForm.format })
    if (exportForm.module_id != null) params.set('module_id', String(exportForm.module_id))
    if (exportForm.priority) params.set('priority', exportForm.priority)
    if (exportForm.status) params.set('status', exportForm.status)
    const response = await fetch(
      `/api/v1/projects/${props.projectId}/export/testcases/?${params.toString()}`,
      { headers: { Authorization: `Bearer ${tokenStore.access}` } },
    )
    if (!response.ok) {
      let message = '导出失败，请稍后重试'
      try {
        const body = await response.json()
        message = body?.message || message
      } catch {
        // 响应不是 JSON（如网络层错误）时使用默认文案
      }
      throw new Error(message)
    }
    const blob = await response.blob()
    const disposition = response.headers.get('Content-Disposition') || ''
    const matched = disposition.match(/filename="?([^";]+)"?/)
    const filename = matched ? decodeURIComponent(matched[1]) : `测试用例.${exportForm.format}`
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
    ElMessage.success('导出完成，文件已开始下载')
    close()
  } catch (err) {
    exportError.value = err instanceof Error ? err.message : '导出失败，请稍后重试'
  } finally {
    exporting.value = false
  }
}

/* ---------------- 通用 ---------------- */
function close() {
  emit('update:modelValue', false)
}

function reset() {
  step.value = 0
  file.value = null
  fileName.value = ''
  headers.value = []
  preview.value = emptyPreview()
  previewReady.value = false
  result.value = emptyResult()
  importError.value = null
  exportError.value = null
  for (const field of IMPORT_FIELDS) delete mapping[field.key]
}
</script>

<style scoped>
.wizard-steps {
  margin-bottom: var(--sp-4);
}

.step-pane {
  min-height: 220px;
}

.pane-hint {
  margin: 0 0 var(--sp-3);
  color: var(--text-secondary);
  font-size: var(--fs-sm);
}

/* ---- 上传 ---- */
.upload-area {
  width: 100%;
}

.upload-inner {
  padding: var(--sp-2) 0;
}

.upload-title {
  margin: 0;
  color: var(--text-primary);
  font-size: var(--fs-md);
  font-weight: 500;
}

.upload-hint {
  margin: var(--sp-1) 0 0;
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
}

.upload-area :deep(.el-upload-dragger) {
  border-radius: var(--radius-md);
  border-color: var(--border-default);
  padding: var(--sp-5);
}

.file-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  margin-top: var(--sp-3);
  padding: var(--sp-2) var(--sp-3);
  background: var(--bg-sunken);
  border-radius: var(--radius-md);
}

.file-name {
  color: var(--text-primary);
  font-size: var(--fs-sm);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-status {
  color: var(--text-secondary);
  font-size: var(--fs-sm);
  flex: none;
}

/* ---- 字段映射 ---- */
.mapping-grid {
  display: grid;
  grid-template-columns: 96px 1fr 96px 1fr;
  gap: var(--sp-3);
  align-items: center;
}

.mapping-label {
  color: var(--text-secondary);
  font-size: var(--fs-sm);
  text-align: right;
}

.required-mark {
  color: var(--danger-600);
  margin-right: 2px;
}

/* ---- 预览 ---- */
.summary-bar {
  display: flex;
  align-items: center;
  gap: var(--sp-4);
  margin-bottom: var(--sp-3);
  padding: var(--sp-2) var(--sp-3);
  background: var(--bg-sunken);
  border-radius: var(--radius-md);
  font-size: var(--fs-sm);
  color: var(--text-secondary);
}

.summary-item b {
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.summary-item.ok b {
  color: var(--success-600);
}

.summary-item.bad b {
  color: var(--danger-600);
}

.summary-tip {
  margin-left: auto;
  color: var(--text-tertiary);
}

.preview-table {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
}

.preview-table :deep(.row-invalid td) {
  background: var(--danger-50);
}

.row-errors {
  color: var(--danger-600);
}

.row-ok {
  color: var(--success-600);
}

.empty-text {
  margin: 0;
  color: var(--text-tertiary);
}

/* ---- 结果 ---- */
.result-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--sp-3);
  margin-bottom: var(--sp-4);
}

.result-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-1);
  padding: var(--sp-4) 0;
  background: var(--bg-sunken);
  border-radius: var(--radius-md);
}

.result-num {
  font-size: var(--fs-2xl);
  font-weight: 600;
  color: var(--accent-600);
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}

.result-num.num-bad {
  color: var(--danger-600);
}

.result-label {
  color: var(--text-secondary);
  font-size: var(--fs-sm);
}

.failed-list {
  max-height: 180px;
  overflow: auto;
  padding: var(--sp-2) var(--sp-3);
  background: var(--danger-50);
  border-radius: var(--radius-md);
}

.failed-item {
  margin: 0 0 var(--sp-1);
  color: var(--danger-600);
  font-size: var(--fs-sm);
}

/* ---- 导出 ---- */
.export-form {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.export-row {
  display: grid;
  grid-template-columns: 72px 1fr;
  gap: var(--sp-3);
  align-items: center;
}

.full-control {
  width: 100%;
}

/* ---- 错误态 ---- */
.error-panel {
  margin-top: var(--sp-3);
  padding: var(--sp-3);
  background: var(--danger-50);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
}

.error-text {
  margin: 0;
  color: var(--danger-600);
  font-size: var(--fs-sm);
}
</style>
