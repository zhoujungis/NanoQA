<template>
  <section class="panel">
    <div class="panel-head">
      <div class="panel-head-main">
        <h2 class="panel-title">AI 任务记录</h2>
        <p class="panel-desc">所有 AI 调用均落任务记录；生成类任务的输出是草案，需人工「入库」才会写入正式用例库，「丢弃」则只留记录</p>
      </div>
      <div class="panel-tools">
        <el-select v-model="taskType" class="tool-select" clearable placeholder="全部类型" @change="onFilterChange">
          <el-option v-for="item in TASK_TYPE_OPTIONS" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-button :loading="loading" @click="refresh">刷新</el-button>
      </div>
    </div>

    <!-- 错误态 -->
    <div v-if="error && !rows.length" class="state-box">
      <p class="state-text">{{ error }}</p>
      <el-button size="small" type="primary" plain @click="refresh">重试</el-button>
    </div>

    <template v-else>
      <el-table v-loading="loading" :data="rows" row-key="id" class="task-table">
        <el-table-column label="任务" width="88">
          <template #default="{ row }">
            <span class="task-id">#{{ row.id }}</span>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="132">
          <template #default="{ row }">
            <span class="cell-text">{{ taskTypeLabel(row.task_type) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="104">
          <template #default="{ row }">
            <StatusTag :tone="taskStatusInfo(row).tone" :label="taskStatusInfo(row).label" />
          </template>
        </el-table-column>
        <el-table-column label="输入摘要" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="cell-text">{{ inputSummary(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="模型 / 耗时" width="128">
          <template #default="{ row }">
            <span class="cell-muted">{{ row.model }} · {{ formatDuration(row.duration) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="触发人" width="110">
          <template #default="{ row }">
            <span class="cell-muted">{{ row.user?.username ?? '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="150">
          <template #default="{ row }">
            <span class="cell-time">{{ formatTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="" width="190" align="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDetail(row)">详情</el-button>
            <el-tooltip v-if="canTaskAccept(row)" :disabled="acceptReason(row) === ''" :content="acceptReason(row)" placement="top">
              <span class="tip-wrap">
                <el-button
                  link
                  type="primary"
                  size="small"
                  :disabled="acceptReason(row) !== ''"
                  @click="acceptTask(row)"
                >
                  入库
                </el-button>
              </span>
            </el-tooltip>
            <el-tooltip v-if="canTaskReject(row)" :disabled="rejectReason(row) === ''" :content="rejectReason(row)" placement="top">
              <span class="tip-wrap">
                <el-button
                  link
                  size="small"
                  :disabled="rejectReason(row) !== ''"
                  @click="rejectTask(row)"
                >
                  丢弃
                </el-button>
              </span>
            </el-tooltip>
          </template>
        </el-table-column>

        <template #empty>
          <div class="empty-state">
            <p class="empty-text">{{ taskType ? '没有符合筛选条件的 AI 任务' : '暂无 AI 任务，去上方生成用例草案试试' }}</p>
          </div>
        </template>
      </el-table>

      <div v-if="total > 0" class="pager">
        <el-pagination
          :current-page="page"
          :page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          background
          @current-change="onPageChange"
          @size-change="onSizeChange"
        />
      </div>
    </template>

    <!-- 任务详情抽屉 -->
    <el-drawer v-model="drawerVisible" :title="drawerTitle" size="560px">
      <div v-if="detail" class="drawer-body">
        <!-- 元信息 -->
        <div class="meta-grid">
          <div class="meta-item">
            <span class="meta-label">任务</span>
            <span class="meta-value mono">#{{ detail.id }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">类型</span>
            <span class="meta-value">{{ taskTypeLabel(detail.task_type) }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">状态</span>
            <span class="meta-value">
              <StatusTag :tone="taskStatusInfo(detail).tone" :label="taskStatusInfo(detail).label" />
            </span>
          </div>
          <div class="meta-item">
            <span class="meta-label">模型</span>
            <span class="meta-value mono">{{ detail.model }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">耗时 / Tokens</span>
            <span class="meta-value mono">{{ formatDuration(detail.duration) }} · {{ detail.tokens }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">触发人</span>
            <span class="meta-value">{{ detail.user?.username ?? '—' }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">创建 / 完成</span>
            <span class="meta-value">{{ formatTime(detail.created_at) }} / {{ formatTime(detail.completed_at) }}</span>
          </div>
        </div>

        <!-- 失败原因 -->
        <div v-if="detail.error" class="error-box">{{ detail.error }}</div>

        <!-- 输出结构 -->
        <div class="output">
          <h3 class="output-title">结构化输出</h3>

          <!-- 用例草案 -->
          <template v-if="outputCases.length">
            <p class="output-hint">
              用例草案 {{ outputCases.length }} 条（{{ detail.output_data?.accepted ? '已审核入库' : '未入库，仅草案' }}）
            </p>
            <div v-for="(item, index) in outputCases" :key="index" class="case-block">
              <div class="case-head">
                <span class="case-index">{{ String(index + 1).padStart(2, '0') }}</span>
                <span class="case-title">{{ item.title }}</span>
                <StatusTag :tone="priorityTone(item.priority)" :label="item.priority" />
                <span class="case-type">{{ caseTypeLabel(item.type) }}</span>
              </div>
              <p v-if="item.precondition" class="case-line">前置：{{ item.precondition }}</p>
              <ol class="case-steps">
                <li v-for="(step, stepIndex) in item.steps" :key="stepIndex">
                  <span class="step-action">{{ step.action }}</span>
                  <span class="step-arrow">→</span>
                  <span class="step-expected">{{ step.expected }}</span>
                </li>
              </ol>
              <p v-if="item.expected_result" class="case-line">预期：{{ item.expected_result }}</p>
            </div>
          </template>

          <!-- 评审结果 -->
          <template v-else-if="detail.output_data?.score !== undefined">
            <div class="score-row">
              <span class="score-value" :class="scoreClass(detail.output_data.score)">{{ detail.output_data.score }}</span>
              <span class="score-label">评审得分</span>
            </div>
            <p class="output-hint">问题（{{ detail.output_data.issues?.length ?? 0 }}）</p>
            <ul class="plain-list">
              <li v-for="(issue, index) in detail.output_data.issues ?? []" :key="index" class="issue-row">
                <StatusTag :tone="levelTone(issue.severity)" :label="levelLabel(issue.severity)" />
                <span>{{ issue.message }}</span>
              </li>
              <li v-if="!(detail.output_data.issues ?? []).length" class="list-empty">未发现问题</li>
            </ul>
            <p class="output-hint">改进建议（{{ detail.output_data.suggestions?.length ?? 0 }}）</p>
            <ul class="plain-list">
              <li v-for="(item, index) in detail.output_data.suggestions ?? []" :key="index">{{ item }}</li>
              <li v-if="!(detail.output_data.suggestions ?? []).length" class="list-empty">暂无建议</li>
            </ul>
          </template>

          <!-- 重复用例对 -->
          <template v-else-if="detail.output_data?.pairs">
            <p class="output-hint">相似用例对 {{ detail.output_data.pairs.length }}（相似度 ≥ 60%，建议人工合并）</p>
            <ul class="plain-list">
              <li v-for="(pair, index) in detail.output_data.pairs" :key="index" class="pair-row">
                <el-button link type="primary" size="small" @click="goCase(pair.case_a)">用例 #{{ pair.case_a }}</el-button>
                <span class="pair-mark">↔</span>
                <el-button link type="primary" size="small" @click="goCase(pair.case_b)">用例 #{{ pair.case_b }}</el-button>
                <span class="pair-similarity">相似度 {{ (pair.similarity * 100).toFixed(0) }}%</span>
                <span class="pair-advice">建议合并</span>
              </li>
              <li v-if="!detail.output_data.pairs.length" class="list-empty">未发现相似用例对</li>
            </ul>
          </template>

          <!-- 需求分析 -->
          <template v-else-if="detail.output_data?.summary">
            <p class="output-hint">分析摘要</p>
            <p class="summary-text">{{ detail.output_data.summary }}</p>
            <p class="output-hint">风险提示（{{ detail.output_data.risks?.length ?? 0 }}）</p>
            <ul class="plain-list">
              <li v-for="(risk, index) in detail.output_data.risks ?? []" :key="index" class="issue-row">
                <StatusTag :tone="levelTone(risk.level)" :label="levelLabel(risk.level)" />
                <span>{{ risk.message }}</span>
              </li>
            </ul>
            <p class="output-hint">建议用例（{{ detail.output_data.suggested_cases?.length ?? 0 }}）</p>
            <ul class="plain-list">
              <li v-for="(item, index) in detail.output_data.suggested_cases ?? []" :key="index">{{ item.title }}</li>
            </ul>
          </template>

          <!-- 缺陷分析 -->
          <template v-else-if="detail.output_data?.possible_causes">
            <p class="output-hint">可能原因</p>
            <ul class="plain-list">
              <li v-for="(item, index) in detail.output_data.possible_causes" :key="index">{{ item }}</li>
            </ul>
            <p class="output-hint">处理建议（{{ detail.output_data.suggestions?.length ?? 0 }}）</p>
            <ul class="plain-list">
              <li v-for="(item, index) in detail.output_data.suggestions ?? []" :key="index">{{ item }}</li>
            </ul>
          </template>

          <!-- 兜底：原始 JSON -->
          <template v-else>
            <pre class="raw-json">{{ rawOutput }}</pre>
          </template>
        </div>

        <!-- 审核操作条（固定在抽屉底部） -->
        <div v-if="canAccept(detail) || canReject(detail)" class="drawer-foot">
          <span class="foot-hint">人工审核后才会写入正式用例库</span>
          <div class="foot-actions">
            <el-button
              v-if="canReject(detail)"
              :disabled="rejectReason(detail) !== ''"
              :loading="rejecting"
              @click="rejectTask(detail)"
            >
              丢弃
            </el-button>
            <el-button
              v-if="canAccept(detail)"
              type="primary"
              :disabled="acceptReason(detail) !== ''"
              :loading="accepting"
              @click="acceptTask(detail)"
            >
              审核入库
            </el-button>
          </div>
        </div>
      </div>
      <div v-else-if="detailError" class="state-box">
        <p class="state-text">{{ detailError }}</p>
        <el-button size="small" type="primary" plain @click="openDetailById">重试</el-button>
      </div>
      <div v-else v-loading="detailLoading" class="state-box" />
    </el-drawer>

    <AcceptedCasesDialog v-model="resultVisible" :cases="resultCases" />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, notifyError, type PageResult } from '@/api/client'
import StatusTag from '@/components/ui/StatusTag.vue'
import AcceptedCasesDialog from './AcceptedCasesDialog.vue'
import {
  TASK_TYPE_OPTIONS,
  canTaskAccept,
  canTaskReject,
  caseTypeLabel,
  formatDuration,
  formatTime,
  inputSummary,
  levelLabel,
  levelTone,
  priorityTone,
  taskStatusInfo,
  taskTypeLabel,
  type AcceptedCase,
  type AiGeneratedCase,
  type AiTaskRecord,
} from './shared'

const props = defineProps<{
  /** 当前项目 id（路由参数） */
  projectId: number
  /** 已在生成面板逐条入库的任务 id（禁止再次入库/丢弃，避免重复） */
  manualAcceptedTaskIds: Set<number>
}>()

const emit = defineEmits<{
  /** 任务入库 / 丢弃后通知父组件 */
  (e: 'changed'): void
}>()

const router = useRouter()

/* ---------------- 任务列表 ---------------- */
const rows = ref<AiTaskRecord[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const error = ref<string | null>(null)
const taskType = ref('')

async function fetchList() {
  loading.value = true
  error.value = null
  try {
    const data = await api.get<PageResult<AiTaskRecord>>('/ai/tasks/', {
      params: {
        project_id: props.projectId,
        page: page.value,
        page_size: pageSize.value,
        task_type: taskType.value || undefined,
      },
    })
    rows.value = data.items
    total.value = data.total
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'AI 任务记录加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

function refresh() {
  fetchList()
  if (drawerVisible.value && currentTaskId.value) fetchDetail(currentTaskId.value)
}

function onFilterChange() {
  page.value = 1
  fetchList()
}

function onPageChange(value: number) {
  page.value = value
  fetchList()
}

function onSizeChange(value: number) {
  pageSize.value = value
  page.value = 1
  fetchList()
}

/* ---------------- 任务详情抽屉 ---------------- */
const drawerVisible = ref(false)
const detail = ref<AiTaskRecord | null>(null)
const detailLoading = ref(false)
const detailError = ref<string | null>(null)
const currentTaskId = ref<number | null>(null)

const drawerTitle = computed(() =>
  detail.value
    ? `AI 任务 #${detail.value.id} · ${taskTypeLabel(detail.value.task_type)}`
    : 'AI 任务详情',
)

const outputCases = computed<AiGeneratedCase[]>(() => detail.value?.output_data?.cases ?? [])

const rawOutput = computed(() => {
  const output = detail.value?.output_data ?? {}
  try {
    return JSON.stringify(output, null, 2)
  } catch {
    return String(output)
  }
})

function scoreClass(score: number): string {
  if (score >= 85) return 'tone-pass'
  if (score >= 60) return 'tone-warn'
  return 'tone-fail'
}

async function fetchDetail(taskId: number) {
  detailLoading.value = true
  detailError.value = null
  try {
    detail.value = await api.get<AiTaskRecord>(`/ai/tasks/${taskId}/`)
  } catch (err) {
    detail.value = null
    detailError.value = err instanceof Error ? err.message : '任务详情加载失败，请稍后重试'
  } finally {
    detailLoading.value = false
  }
}

function openDetail(row: AiTaskRecord) {
  currentTaskId.value = row.id
  drawerVisible.value = true
  fetchDetail(row.id)
}

function openDetailById() {
  if (currentTaskId.value) fetchDetail(currentTaskId.value)
}

/* ---------------- 入库 / 丢弃 ---------------- */
const accepting = ref(false)
const rejecting = ref(false)
const resultVisible = ref(false)
const resultCases = ref<AcceptedCase[]>([])

function acceptReason(row: AiTaskRecord): string {
  if (!canTaskAccept(row)) return row.status === 'succeeded' ? '该任务没有可入库的用例草案' : '仅生成类任务且执行成功后可入库'
  if (props.manualAcceptedTaskIds.has(row.id)) return '该任务的草案已在生成面板逐条入库，请勿重复入库'
  return ''
}

function rejectReason(row: AiTaskRecord): string {
  if (!canTaskReject(row)) return '仅执行成功且未审核的任务可丢弃'
  if (props.manualAcceptedTaskIds.has(row.id)) return '该任务的草案已逐条入库，无法丢弃'
  return ''
}

function canAccept(row: AiTaskRecord) {
  return canTaskAccept(row)
}

function canReject(row: AiTaskRecord) {
  return canTaskReject(row)
}

async function acceptTask(row: AiTaskRecord) {
  if (acceptReason(row) !== '') {
    ElMessage.warning(acceptReason(row))
    return
  }
  try {
    await ElMessageBox.confirm(
      '将把该任务的全部 AI 用例草案写入正式用例库（初始状态为「草稿」），确认继续？',
      '审核入库',
      { type: 'warning', confirmButtonText: '确认入库', cancelButtonText: '再看看' },
    )
  } catch {
    return
  }

  accepting.value = true
  try {
    const data = await api.post<{ task_id: number; cases: AcceptedCase[] }>(`/ai/tasks/${row.id}/accept/`)
    resultCases.value = data.cases
    resultVisible.value = true
    ElMessage.success(`已审核入库 ${data.cases.length} 条正式用例`)
    emit('changed')
    refresh()
  } catch (err) {
    notifyError(err)
  } finally {
    accepting.value = false
  }
}

async function rejectTask(row: AiTaskRecord) {
  if (rejectReason(row) !== '') {
    ElMessage.warning(rejectReason(row))
    return
  }
  try {
    await ElMessageBox.confirm('丢弃后 AI 输出不会写入正式用例库，仅保留任务记录，确认丢弃？', '丢弃任务', {
      type: 'warning',
      confirmButtonText: '确认丢弃',
      cancelButtonText: '再看看',
    })
  } catch {
    return
  }

  rejecting.value = true
  try {
    await api.post(`/ai/tasks/${row.id}/reject/`)
    ElMessage.success('已丢弃，仅保留 AI 任务记录')
    emit('changed')
    refresh()
  } catch (err) {
    notifyError(err)
  } finally {
    rejecting.value = false
  }
}

function goCase(caseId: number) {
  router.push({ name: 'testcase-detail', params: { projectId: props.projectId, caseId } })
}

onMounted(() => {
  fetchList()
})

defineExpose({ refresh })
</script>

<style scoped>
.panel {
  background: var(--bg-surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  margin-bottom: var(--sp-5);
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--sp-4);
  padding: var(--sp-4) var(--sp-5);
  border-bottom: 1px solid var(--border-light);
}

.panel-title {
  margin: 0;
  font-size: var(--fs-lg);
  font-weight: 600;
  line-height: var(--lh-tight);
}

.panel-desc {
  margin: var(--sp-1) 0 0;
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
}

.panel-tools {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex: none;
}

.tool-select {
  width: 148px;
}

.task-table {
  width: 100%;
}

.task-id {
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
  color: var(--text-secondary);
}

.cell-text {
  color: var(--text-primary);
  font-size: var(--fs-base);
}

.cell-muted {
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
}

.cell-time {
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
  font-variant-numeric: tabular-nums;
}

.tip-wrap {
  display: inline-flex;
  margin-left: var(--sp-2);
}

.state-box {
  padding: var(--sp-10) var(--sp-6);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--sp-3);
  min-height: 120px;
}

.state-text {
  margin: 0;
  color: var(--text-tertiary);
}

.empty-state {
  padding: var(--sp-8) 0;
  text-align: center;
}

.empty-text {
  margin: 0;
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
}

.pager {
  display: flex;
  justify-content: flex-end;
  padding: var(--sp-3) var(--sp-4);
  border-top: 1px solid var(--border-light);
}

/* ---------------- 详情抽屉 ---------------- */
.drawer-body {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}

.meta-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--sp-2) var(--sp-4);
  padding: var(--sp-3) var(--sp-4);
  background: var(--bg-sunken);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
}

.meta-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.meta-label {
  color: var(--text-tertiary);
  font-size: var(--fs-xs);
}

.meta-value {
  color: var(--text-primary);
  font-size: var(--fs-sm);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.meta-value.mono {
  font-family: var(--font-mono);
}

.error-box {
  padding: var(--sp-2) var(--sp-3);
  background: var(--danger-50);
  border-left: 3px solid var(--danger-600);
  border-radius: var(--radius-sm);
  color: var(--danger-600);
  font-size: var(--fs-sm);
}

.output {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.output-title {
  margin: 0;
  font-size: var(--fs-md);
  font-weight: 600;
}

.output-hint {
  margin: var(--sp-2) 0 0;
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
  font-weight: 500;
}

.case-block {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  padding: var(--sp-2) var(--sp-3);
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}

.case-head {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.case-index {
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
  color: var(--text-placeholder);
}

.case-title {
  flex: 1;
  min-width: 0;
  font-weight: 500;
  color: var(--text-primary);
  font-size: var(--fs-base);
}

.case-type {
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
}

.case-line {
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--fs-sm);
}

.case-steps {
  margin: 0;
  padding-left: var(--sp-4);
  color: var(--text-secondary);
  font-size: var(--fs-sm);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.step-arrow {
  color: var(--text-placeholder);
  margin: 0 var(--sp-1);
}

.plain-list {
  margin: 0;
  padding-left: var(--sp-4);
  color: var(--text-secondary);
  font-size: var(--fs-sm);
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}

.issue-row {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.pair-row {
  display: flex;
  align-items: center;
  gap: var(--sp-1);
}

.pair-mark {
  color: var(--text-placeholder);
}

.pair-similarity {
  margin-left: var(--sp-2);
  color: var(--accent-600);
  font-variant-numeric: tabular-nums;
}

.pair-advice {
  color: var(--text-tertiary);
}

.list-empty {
  color: var(--text-placeholder);
  list-style: none;
  margin-left: calc(var(--sp-4) * -1);
}

.summary-text {
  margin: 0;
  padding: var(--sp-2) var(--sp-3);
  background: var(--bg-sunken);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: var(--fs-base);
  line-height: var(--lh-base);
}

.score-row {
  display: flex;
  align-items: baseline;
  gap: var(--sp-2);
}

.score-value {
  font-size: var(--fs-2xl);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.score-value.tone-pass {
  color: var(--success-600);
}
.score-value.tone-warn {
  color: var(--warning-600);
}
.score-value.tone-fail {
  color: var(--danger-600);
}

.score-label {
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
}

.raw-json {
  margin: 0;
  padding: var(--sp-3);
  background: var(--bg-sunken);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
  color: var(--text-secondary);
  overflow: auto;
  max-height: 360px;
  white-space: pre-wrap;
  word-break: break-all;
}

.drawer-foot {
  position: sticky;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  margin-top: var(--sp-2);
  padding: var(--sp-3) 0 0;
  border-top: 1px solid var(--border-light);
  background: var(--bg-surface);
}

.foot-hint {
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
}

.foot-actions {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex: none;
}
</style>
