<template>
  <section v-loading="loading" class="detail-page">
    <!-- 加载失败且无数据：整页错误态 -->
    <div v-if="error && !detail" class="page-error">
      <p class="page-error-text">{{ error }}</p>
      <el-button type="primary" plain @click="fetchDetail">重试</el-button>
    </div>

    <template v-else-if="detail">
      <PageHeader :title="detail.title">
        <template #subtitle>
          <span class="header-meta">
            <span class="req-key">{{ detail.key }}</span>
            <StatusTag :tone="statusTone(detail.status)" :label="statusLabel(detail.status)" />
            <StatusTag :tone="PRIORITY_TONE[detail.priority]" :label="detail.priority" />
            <span class="header-sub">负责人 {{ userLabel(detail.owner) }}</span>
          </span>
        </template>
        <template #actions>
          <el-button @click="openEdit">编辑</el-button>
          <el-button @click="goList">返回列表</el-button>
        </template>
      </PageHeader>

      <div class="detail-layout">
        <!-- 主栏 -->
        <div class="detail-main">
          <section class="panel">
            <h2 class="panel-title">需求描述</h2>
            <div class="info-text" :class="{ 'is-empty': !detail.description }">
              {{ detail.description || '暂无描述' }}
            </div>
          </section>

          <!-- 需求覆盖面板（§37） -->
          <section class="panel">
            <div class="panel-head">
              <h2 class="panel-title">需求覆盖</h2>
              <div class="panel-head-side">
                <span class="head-label">预期用例数</span>
                <el-input-number
                  v-model="expectedCases"
                  :min="1"
                  :max="9999"
                  size="small"
                  class="expected-input"
                />
                <el-button size="small" :loading="coverageLoading" @click="fetchCoverage(expectedCases)">
                  按预期数计算
                </el-button>
              </div>
            </div>

            <div v-if="coverageError" class="inline-error">
              {{ coverageError }}
              <el-button link type="primary" size="small" @click="fetchCoverage()">重新加载</el-button>
            </div>

            <template v-else-if="coverage">
              <div class="coverage-summary">
                <div class="coverage-rate">
                  <span class="coverage-percent mono">{{ coveragePercent }}%</span>
                  <StatusTag
                    :tone="RISK_META[coverage.risk_level].tone"
                    :label="RISK_META[coverage.risk_level].label"
                  />
                </div>
                <el-progress
                  :percentage="coveragePercent"
                  :stroke-width="8"
                  :show-text="false"
                  :status="coveragePercent >= 100 ? 'success' : coverage.risk_level === 'high' ? 'exception' : ''"
                />
                <div class="coverage-numbers">
                  <div class="cov-item">
                    <span class="cov-value mono">{{ coverage.linked_cases }}</span>
                    <span class="cov-label">已覆盖</span>
                  </div>
                  <div class="cov-item">
                    <span class="cov-value mono">{{ uncoveredCases }}</span>
                    <span class="cov-label">未覆盖</span>
                  </div>
                  <div class="cov-item">
                    <span class="cov-value mono">{{ coverage.expected_cases }}</span>
                    <span class="cov-label">总数</span>
                  </div>
                </div>
              </div>

              <div class="exec-stats">
                <div class="exec-item">
                  <span class="exec-label">已执行</span>
                  <span class="exec-value mono">{{ coverage.executed }}</span>
                </div>
                <div class="exec-item">
                  <span class="exec-label">通过</span>
                  <span class="exec-value mono is-pass">{{ coverage.passed }}</span>
                </div>
                <div class="exec-item">
                  <span class="exec-label">失败</span>
                  <span class="exec-value mono is-fail">{{ coverage.failed }}</span>
                </div>
                <div class="exec-item">
                  <span class="exec-label">阻塞</span>
                  <span class="exec-value mono is-block">{{ coverage.blocked }}</span>
                </div>
                <div class="exec-item">
                  <span class="exec-label">跳过</span>
                  <span class="exec-value mono">{{ coverage.skipped }}</span>
                </div>
                <div class="exec-item">
                  <span class="exec-label">未执行</span>
                  <span class="exec-value mono">{{ coverage.not_run }}</span>
                </div>
              </div>
            </template>

            <div v-else class="empty-text">{{ coverageLoading ? '覆盖数据加载中…' : '暂无覆盖数据' }}</div>
          </section>

          <!-- 关联用例 -->
          <section class="panel">
            <div class="panel-head">
              <h2 class="panel-title">关联用例（{{ detail.test_cases.length }}）</h2>
              <el-button size="small" @click="openLinkDialog">关联用例</el-button>
            </div>
            <el-table :data="detail.test_cases" size="small" class="link-table">
              <el-table-column label="编号" width="150">
                <template #default="{ row }">
                  <span class="req-key">{{ row.case_key }}</span>
                </template>
              </el-table-column>
              <el-table-column label="标题" min-width="220" show-overflow-tooltip>
                <template #default="{ row }">
                  <el-button link type="primary" class="cell-link" @click="goCase(row)">
                    {{ row.title }}
                  </el-button>
                </template>
              </el-table-column>
              <el-table-column label="优先级" width="80" align="center">
                <template #default="{ row }">
                  <StatusTag :tone="priorityTone(row.priority)" :label="row.priority" />
                </template>
              </el-table-column>
              <el-table-column label="状态" width="88">
                <template #default="{ row }">
                  <StatusTag :tone="caseStatusTone(row.status)" :label="CASE_STATUS_LABELS[row.status] || row.status" />
                </template>
              </el-table-column>
              <el-table-column label="" width="96" align="right">
                <template #default="{ row }">
                  <el-button
                    link
                    type="danger"
                    size="small"
                    :loading="unlinkingId === row.id"
                    @click="confirmUnlink(row)"
                  >
                    取消关联
                  </el-button>
                </template>
              </el-table-column>
              <template #empty>
                <div class="empty-text">暂未关联测试用例，点击右上角「关联用例」补充覆盖</div>
              </template>
            </el-table>
          </section>
        </div>

        <!-- 侧栏 -->
        <aside class="detail-side">
          <section class="panel">
            <h2 class="panel-title">属性</h2>
            <dl class="attr-list">
              <div class="attr-row">
                <dt>编号</dt>
                <dd class="req-key">{{ detail.key }}</dd>
              </div>
              <div class="attr-row">
                <dt>状态</dt>
                <dd>
                  <StatusTag :tone="statusTone(detail.status)" :label="statusLabel(detail.status)" />
                </dd>
              </div>
              <div class="attr-row">
                <dt>优先级</dt>
                <dd>
                  <StatusTag :tone="PRIORITY_TONE[detail.priority]" :label="detail.priority" />
                </dd>
              </div>
              <div class="attr-row">
                <dt>负责人</dt>
                <dd>{{ userLabel(detail.owner) }}</dd>
              </div>
              <div class="attr-row">
                <dt>创建人</dt>
                <dd>{{ userLabel(detail.creator) }}</dd>
              </div>
              <div class="attr-row">
                <dt>版本</dt>
                <dd class="mono">v{{ detail.version }}</dd>
              </div>
              <div class="attr-row">
                <dt>创建时间</dt>
                <dd class="cell-time">{{ formatTime(detail.created_at) }}</dd>
              </div>
              <div class="attr-row">
                <dt>更新时间</dt>
                <dd class="cell-time">{{ formatTime(detail.updated_at) }}</dd>
              </div>
            </dl>
          </section>

          <!-- 状态流转（§50，仅展示合法目标状态） -->
          <section class="panel">
            <h2 class="panel-title">状态流转</h2>
            <div class="transition-current">
              当前状态
              <StatusTag :tone="statusTone(detail.status)" :label="statusLabel(detail.status)" />
            </div>
            <div v-if="nextStatuses.length" class="transition-actions">
              <el-button
                v-for="status in nextStatuses"
                :key="status"
                size="small"
                :loading="transitioning === status"
                @click="confirmTransition(status)"
              >
                转为{{ statusLabel(status) }}
              </el-button>
            </div>
            <p v-else class="empty-text">当前状态无可用流转</p>
          </section>
        </aside>
      </div>
    </template>

    <!-- 编辑需求 -->
    <el-dialog v-model="editVisible" title="编辑需求" width="560px" :close-on-click-modal="false">
      <RequirementForm ref="editFormRef" :model="editForm" :users="users" mode="edit" />
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editSubmitting" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 关联用例 -->
    <el-dialog v-model="linkVisible" title="关联测试用例" width="640px" :close-on-click-modal="false">
      <div class="link-dialog-body">
        <el-input
          v-model="linkSearch"
          clearable
          placeholder="搜索用例编号 / 标题"
          @input="onLinkSearchInput"
          @clear="onLinkSearchInput"
        />
        <el-table
          v-loading="linkLoading"
          :data="linkCandidates"
          size="small"
          class="link-table"
          max-height="320"
          @selection-change="onLinkSelectionChange"
        >
          <el-table-column type="selection" width="40" :selectable="isLinkable" />
          <el-table-column label="编号" width="150">
            <template #default="{ row }">
              <span class="req-key">{{ row.case_key }}</span>
            </template>
          </el-table-column>
          <el-table-column label="标题" min-width="220" show-overflow-tooltip prop="title" />
          <el-table-column label="状态" width="88">
            <template #default="{ row }">
              <StatusTag :tone="caseStatusTone(row.status)" :label="CASE_STATUS_LABELS[row.status] || row.status" />
            </template>
          </el-table-column>
          <template #empty>
            <div class="empty-text">{{ linkLoading ? '加载中…' : '没有可关联的用例' }}</div>
          </template>
        </el-table>
      </div>
      <template #footer>
        <el-button @click="linkVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!linkSelection.length" :loading="linkSubmitting" @click="submitLink">
          关联所选（{{ linkSelection.length }}）
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, notifyError, ApiError, type PageResult } from '@/api/client'
import PageHeader from '@/components/ui/PageHeader.vue'
import StatusTag from '@/components/ui/StatusTag.vue'
import RequirementForm from './requirements/RequirementForm.vue'
import {
  CASE_STATUS_LABELS,
  PRIORITY_TONE,
  RISK_META,
  STATUS_TRANSITIONS,
  defaultRequirementForm,
  formatTime,
  priorityTone,
  statusLabel,
  statusTone,
  userLabel,
  type Coverage,
  type LinkedTestCase,
  type ReqStatus,
  type RequirementDetail,
  type RequirementFormModel,
  type UserBrief,
} from './requirements/shared'

const route = useRoute()
const router = useRouter()
const projectId = computed(() => Number(route.params.projectId))
const reqId = computed(() => Number(route.params.reqId))

/* ---------------- 需求详情 ---------------- */
const detail = ref<RequirementDetail | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

/** 用例状态语义色（关联用例列表展示） */
function caseStatusTone(status: string) {
  if (status === 'active') return 'pass' as const
  if (status === 'deprecated') return 'warn' as const
  if (status === 'archived') return 'skip' as const
  return 'neutral' as const
}

async function fetchDetail() {
  loading.value = true
  error.value = null
  try {
    detail.value = await api.get<RequirementDetail>(`/requirements/${reqId.value}/`)
    fetchCoverage()
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : '需求加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

/* ---------------- 覆盖率面板（§37） ---------------- */
const coverage = ref<Coverage | null>(null)
const coverageLoading = ref(false)
const coverageError = ref<string | null>(null)
const expectedCases = ref<number | null>(null)

const coveragePercent = computed(() => Math.round((coverage.value?.coverage ?? 0) * 100))
const uncoveredCases = computed(() => {
  if (!coverage.value) return 0
  return Math.max(coverage.value.expected_cases - coverage.value.linked_cases, 0)
})

/** 取覆盖率；expected 传入时按预期用例数重新计算未覆盖口径 */
async function fetchCoverage(expected?: number | null) {
  coverageLoading.value = true
  coverageError.value = null
  try {
    coverage.value = await api.get<Coverage>(`/requirements/${reqId.value}/coverage/`, {
      params: expected ? { expected_cases: expected } : undefined,
    })
    if (expectedCases.value === null) {
      expectedCases.value = coverage.value.expected_cases
    }
  } catch (err) {
    coverageError.value = err instanceof ApiError ? err.message : '覆盖数据加载失败'
  } finally {
    coverageLoading.value = false
  }
}

/* ---------------- 状态流转（§50） ---------------- */
const transitioning = ref<string | null>(null)

const nextStatuses = computed<ReqStatus[]>(() => {
  if (!detail.value) return []
  return STATUS_TRANSITIONS[detail.value.status as ReqStatus] ?? []
})

async function confirmTransition(target: ReqStatus) {
  if (!detail.value) return
  try {
    await ElMessageBox.confirm(
      `确认将需求「${detail.value.key}」状态从「${statusLabel(detail.value.status)}」变更为「${statusLabel(target)}」？`,
      '状态流转确认',
      { type: 'warning', confirmButtonText: '确认流转', cancelButtonText: '取消' },
    )
  } catch {
    return
  }

  transitioning.value = target
  try {
    detail.value = await api.patch<RequirementDetail>(`/requirements/${reqId.value}/`, {
      status: target,
      updated_at: detail.value.updated_at,
    })
    ElMessage.success('状态已更新')
    fetchCoverage()
  } catch (err) {
    notifyError(err)
  } finally {
    transitioning.value = null
  }
}

/* ---------------- 编辑（乐观锁） ---------------- */
const editVisible = ref(false)
const editSubmitting = ref(false)
const editFormRef = ref<InstanceType<typeof RequirementForm>>()
const editForm = ref<RequirementFormModel>(defaultRequirementForm())
const editOriginalStatus = ref('')
const users = ref<UserBrief[]>([])

async function fetchUsers() {
  try {
    const data = await api.get<PageResult<UserBrief>>('/users/', { params: { page_size: 100 } })
    users.value = data.items
  } catch {
    // 负责人下拉缺失不影响主流程，静默降级
  }
}

function openEdit() {
  if (!detail.value) return
  editForm.value = {
    title: detail.value.title,
    description: detail.value.description,
    status: detail.value.status,
    priority: detail.value.priority,
    owner_id: detail.value.owner?.id ?? null,
  }
  editOriginalStatus.value = detail.value.status
  editVisible.value = true
  editFormRef.value?.clearValidate()
  if (!users.value.length) fetchUsers()
}

async function submitEdit() {
  const form = editFormRef.value
  if (!form || !detail.value) return
  const valid = await form.validate().catch(() => false)
  if (!valid) return

  editSubmitting.value = true
  try {
    const payload: Record<string, unknown> = {
      title: editForm.value.title.trim(),
      description: editForm.value.description.trim(),
      priority: editForm.value.priority,
      owner_id: editForm.value.owner_id,
      // 乐观锁：updated_at 原样回传，禁止格式化（common/optimistic.py）
      updated_at: detail.value.updated_at,
    }
    // 状态仅在变更时提交，避免触发无意义的状态机校验
    if (editForm.value.status !== editOriginalStatus.value) {
      payload.status = editForm.value.status
    }
    detail.value = await api.patch<RequirementDetail>(`/requirements/${reqId.value}/`, payload)
    editVisible.value = false
    ElMessage.success('需求已保存')
  } catch (err) {
    notifyError(err)
  } finally {
    editSubmitting.value = false
  }
}

/* ---------------- 关联 / 取消关联用例 ---------------- */
const unlinkingId = ref<number | null>(null)

function goCase(row: LinkedTestCase) {
  router.push({ name: 'testcase-detail', params: { projectId: projectId.value, caseId: row.id } })
}

async function confirmUnlink(row: LinkedTestCase) {
  if (!detail.value) return
  try {
    await ElMessageBox.confirm(
      `确认取消需求「${detail.value.key}」与用例「${row.case_key}」的关联？`,
      '取消关联确认',
      { type: 'warning', confirmButtonText: '取消关联', cancelButtonText: '返回' },
    )
  } catch {
    return
  }

  unlinkingId.value = row.id
  try {
    await api.delete(`/requirements/${reqId.value}/testcases/${row.id}/`)
    ElMessage.success('已取消关联')
    fetchDetail()
  } catch (err) {
    notifyError(err)
  } finally {
    unlinkingId.value = null
  }
}

/* 选择用例弹窗 */
const linkVisible = ref(false)
const linkLoading = ref(false)
const linkSubmitting = ref(false)
const linkSearch = ref('')
const linkCandidates = ref<LinkedTestCase[]>([])
const linkSelection = ref<LinkedTestCase[]>([])

function isLinkable(row: LinkedTestCase) {
  return !detail.value?.test_cases.some((item) => item.id === row.id)
}

function openLinkDialog() {
  linkVisible.value = true
  linkSearch.value = ''
  linkSelection.value = []
  fetchLinkCandidates()
}

let linkSearchTimer: ReturnType<typeof setTimeout> | null = null

function onLinkSearchInput() {
  if (linkSearchTimer) clearTimeout(linkSearchTimer)
  linkSearchTimer = setTimeout(fetchLinkCandidates, 300)
}

async function fetchLinkCandidates() {
  linkLoading.value = true
  try {
    const data = await api.get<PageResult<LinkedTestCase>>(`/projects/${projectId.value}/testcases/`, {
      params: { page: 1, page_size: 50, q: linkSearch.value.trim() || undefined },
    })
    linkCandidates.value = data.items
  } catch (err) {
    notifyError(err)
    linkCandidates.value = []
  } finally {
    linkLoading.value = false
  }
}

function onLinkSelectionChange(selection: LinkedTestCase[]) {
  linkSelection.value = selection
}

async function submitLink() {
  if (!linkSelection.value.length) return
  linkSubmitting.value = true
  try {
    await api.post(`/requirements/${reqId.value}/testcases/`, {
      test_case_ids: linkSelection.value.map((item) => item.id),
    })
    linkVisible.value = false
    ElMessage.success(`已关联 ${linkSelection.value.length} 条用例`)
    fetchDetail()
  } catch (err) {
    notifyError(err)
  } finally {
    linkSubmitting.value = false
  }
}

function goList() {
  router.push({ name: 'requirements', params: { projectId: projectId.value } })
}

watch(reqId, () => {
  detail.value = null
  coverage.value = null
  expectedCases.value = null
  fetchDetail()
})

onMounted(fetchDetail)
</script>

<style scoped>
.detail-page {
  padding: var(--sp-6);
}

.page-error {
  padding: var(--sp-12) var(--sp-6);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-3);
}

.page-error-text {
  margin: 0;
  color: var(--text-tertiary);
}

.header-meta {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
}

.header-sub {
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
}

.detail-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: var(--sp-4);
  align-items: start;
}

.detail-main,
.detail-side {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
  min-width: 0;
}

.panel {
  background: var(--bg-surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  padding: var(--sp-4);
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  margin-bottom: var(--sp-3);
}

.panel-head-side {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.panel-title {
  margin: 0 0 var(--sp-3);
  font-size: var(--fs-md);
  font-weight: 600;
  color: var(--text-primary);
}

.panel-head .panel-title {
  margin-bottom: 0;
}

.head-label {
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
}

.expected-input {
  width: 110px;
}

.info-text {
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--fs-base);
  line-height: var(--lh-base);
  white-space: pre-wrap;
}

.info-text.is-empty {
  color: var(--text-placeholder);
}

.req-key {
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
  color: var(--text-secondary);
}

.mono {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}

/* 覆盖面板 */
.coverage-summary {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.coverage-rate {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
}

.coverage-percent {
  font-size: var(--fs-2xl);
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1;
}

.coverage-numbers {
  display: flex;
  gap: var(--sp-8);
}

.cov-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.cov-value {
  font-size: var(--fs-lg);
  font-weight: 600;
  color: var(--text-primary);
}

.cov-label {
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
}

.exec-stats {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2) var(--sp-6);
  margin-top: var(--sp-4);
  padding-top: var(--sp-3);
  border-top: 1px solid var(--border-light);
}

.exec-item {
  display: flex;
  align-items: baseline;
  gap: var(--sp-2);
}

.exec-label {
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
}

.exec-value {
  font-size: var(--fs-md);
  font-weight: 600;
  color: var(--text-primary);
}

.exec-value.is-pass {
  color: var(--status-pass);
}

.exec-value.is-fail {
  color: var(--status-fail);
}

.exec-value.is-block {
  color: var(--status-block);
}

.inline-error {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  color: var(--danger-600);
  font-size: var(--fs-sm);
}

/* 关联用例 */
.link-table {
  width: 100%;
}

.cell-link {
  padding: 0;
  font-weight: 500;
}

.link-dialog-body {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

/* 属性 */
.attr-list {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.attr-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--sp-3);
}

.attr-row dt {
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
  flex: none;
}

.attr-row dd {
  margin: 0;
  color: var(--text-primary);
  font-size: var(--fs-sm);
  text-align: right;
  word-break: break-all;
}

.cell-time {
  color: var(--text-secondary);
  font-size: var(--fs-sm);
  font-variant-numeric: tabular-nums;
}

/* 状态流转 */
.transition-current {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
  margin-bottom: var(--sp-3);
}

.transition-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2);
}

.empty-text {
  margin: 0;
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
}
</style>
