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
            <span class="defect-key">{{ detail.key }}</span>
            <StatusTag :tone="statusTone(detail.status)" :label="statusLabel(detail.status)" />
            <StatusTag :tone="severityTone(detail.severity)" :label="severityLabel(detail.severity)" />
            <StatusTag :tone="PRIORITY_TONE[detail.priority]" :label="detail.priority" />
            <span class="header-sub">经办人 {{ userLabel(detail.assignee) }}</span>
          </span>
        </template>
        <template #actions>
          <el-button @click="openEdit">编辑</el-button>
          <el-button v-if="auth.isSystemAdmin" type="danger" plain @click="confirmArchive">
            归档
          </el-button>
          <el-button @click="goList">返回列表</el-button>
        </template>
      </PageHeader>

      <div class="detail-layout">
        <!-- 主栏 -->
        <div class="detail-main">
          <section class="panel">
            <h2 class="panel-title">缺陷描述</h2>
            <div class="info-text" :class="{ 'is-empty': !detail.description }">
              {{ detail.description || '暂无描述' }}
            </div>
          </section>

          <!-- 状态流转区（§50：仅展示合法目标状态，流转前二次确认） -->
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
            <div class="transition-times">
              <div class="time-item">
                <span class="time-label">修复时间</span>
                <span class="cell-time">{{ formatTime(detail.resolved_at) }}</span>
              </div>
              <div class="time-item">
                <span class="time-label">关闭时间</span>
                <span class="cell-time">{{ formatTime(detail.closed_at) }}</span>
              </div>
            </div>
          </section>

          <!-- 关联用例 -->
          <section class="panel">
            <div class="panel-head">
              <h2 class="panel-title">关联用例（{{ detail.test_cases.length }}）</h2>
            </div>
            <el-table :data="detail.test_cases" size="small" class="link-table">
              <el-table-column label="编号" width="150">
                <template #default="{ row }">
                  <span class="defect-key">{{ row.case_key }}</span>
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
                  <span class="cell-muted">{{ CASE_STATUS_LABELS[row.status] || row.status }}</span>
                </template>
              </el-table-column>
              <template #empty>
                <div class="empty-text">暂无关联用例</div>
              </template>
            </el-table>
          </section>

          <!-- 关联执行结果 -->
          <section class="panel">
            <div class="panel-head">
              <h2 class="panel-title">关联执行结果（{{ detail.test_results.length }}）</h2>
            </div>
            <el-table :data="detail.test_results" size="small" class="link-table">
              <el-table-column label="用例" min-width="200" show-overflow-tooltip>
                <template #default="{ row }">
                  <span class="defect-key">{{ row.test_case_key }}</span>
                  <el-button link type="primary" class="cell-link" @click="goResultCase(row)">
                    {{ row.test_case_title }}
                  </el-button>
                </template>
              </el-table-column>
              <el-table-column label="所属执行" min-width="160" show-overflow-tooltip>
                <template #default="{ row }">
                  <el-button link type="primary" class="cell-link" @click="goRun(row)">
                    {{ row.test_run_name || `执行 #${row.test_run}` }}
                  </el-button>
                </template>
              </el-table-column>
              <el-table-column label="结果" width="88">
                <template #default="{ row }">
                  <StatusTag :tone="resultTone(row.status)" :label="RESULT_STATUS_LABELS[row.status] || row.status" />
                </template>
              </el-table-column>
              <el-table-column label="执行时间" width="140">
                <template #default="{ row }">
                  <span class="cell-time">{{ formatTime(row.executed_at) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="耗时" width="80" align="right">
                <template #default="{ row }">
                  <span class="mono">{{ row.duration != null ? `${row.duration}s` : '—' }}</span>
                </template>
              </el-table-column>
              <template #empty>
                <div class="empty-text">暂无关联执行结果</div>
              </template>
            </el-table>
          </section>

          <!-- 关联需求 -->
          <section class="panel">
            <div class="panel-head">
              <h2 class="panel-title">关联需求（{{ detail.requirements.length }}）</h2>
            </div>
            <el-table :data="detail.requirements" size="small" class="link-table">
              <el-table-column label="编号" width="160">
                <template #default="{ row }">
                  <span class="defect-key">{{ row.key }}</span>
                </template>
              </el-table-column>
              <el-table-column label="标题" min-width="220" show-overflow-tooltip>
                <template #default="{ row }">
                  <el-button link type="primary" class="cell-link" @click="goRequirement(row)">
                    {{ row.title }}
                  </el-button>
                </template>
              </el-table-column>
              <el-table-column label="状态" width="96">
                <template #default="{ row }">
                  <span class="cell-muted">{{ row.status }}</span>
                </template>
              </el-table-column>
              <el-table-column label="优先级" width="80" align="center">
                <template #default="{ row }">
                  <StatusTag :tone="priorityTone(row.priority)" :label="row.priority" />
                </template>
              </el-table-column>
              <template #empty>
                <div class="empty-text">暂无关联需求</div>
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
                <dd class="defect-key">{{ detail.key }}</dd>
              </div>
              <div class="attr-row">
                <dt>状态</dt>
                <dd>
                  <StatusTag :tone="statusTone(detail.status)" :label="statusLabel(detail.status)" />
                </dd>
              </div>
              <div class="attr-row">
                <dt>严重程度</dt>
                <dd>
                  <StatusTag :tone="severityTone(detail.severity)" :label="severityLabel(detail.severity)" />
                </dd>
              </div>
              <div class="attr-row">
                <dt>优先级</dt>
                <dd>
                  <StatusTag :tone="PRIORITY_TONE[detail.priority]" :label="detail.priority" />
                </dd>
              </div>
              <div class="attr-row">
                <dt>环境</dt>
                <dd>{{ detail.environment || '—' }}</dd>
              </div>
              <div class="attr-row">
                <dt>影响版本</dt>
                <dd class="mono">{{ detail.version || '—' }}</dd>
              </div>
              <div class="attr-row">
                <dt>报告人</dt>
                <dd>{{ userLabel(detail.reporter) }}</dd>
              </div>
              <div class="attr-row">
                <dt>经办人</dt>
                <dd>{{ userLabel(detail.assignee) }}</dd>
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
        </aside>
      </div>
    </template>

    <!-- 编辑缺陷（含指派经办人，乐观锁） -->
    <el-dialog v-model="editVisible" title="编辑缺陷" width="580px" :close-on-click-modal="false">
      <DefectForm ref="editFormRef" :model="editForm" :users="users" />
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editSubmitting" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, notifyError, ApiError, type PageResult } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import PageHeader from '@/components/ui/PageHeader.vue'
import StatusTag from '@/components/ui/StatusTag.vue'
import DefectForm from './defects/DefectForm.vue'
import {
  CASE_STATUS_LABELS,
  PRIORITY_TONE,
  RESULT_STATUS_LABELS,
  STATUS_TRANSITIONS,
  defaultDefectForm,
  formatTime,
  priorityTone,
  severityLabel,
  severityTone,
  statusLabel,
  statusTone,
  userLabel,
  type DefectDetail,
  type DefectFormModel,
  type DefectStatus,
  type LinkedRequirement,
  type LinkedTestCase,
  type LinkedTestResult,
  type UserBrief,
} from './defects/shared'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const projectId = computed(() => Number(route.params.projectId))
const defectId = computed(() => Number(route.params.defectId))

/* ---------------- 缺陷详情 ---------------- */
const detail = ref<DefectDetail | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

async function fetchDetail() {
  loading.value = true
  error.value = null
  try {
    detail.value = await api.get<DefectDetail>(`/defects/${defectId.value}/`)
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : '缺陷加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

/** 执行结果语义色 */
function resultTone(status: string) {
  if (status === 'passed') return 'pass' as const
  if (status === 'failed') return 'fail' as const
  if (status === 'blocked') return 'block' as const
  return 'skip' as const
}

/* ---------------- 状态流转区（§50） ---------------- */
const transitioning = ref<string | null>(null)

/** 合法目标状态（与后端 DEFECT_TRANSITIONS 一致；未知状态不展示任何流转） */
const nextStatuses = computed<DefectStatus[]>(() => {
  if (!detail.value) return []
  return STATUS_TRANSITIONS[detail.value.status as DefectStatus] ?? []
})

async function confirmTransition(target: DefectStatus) {
  if (!detail.value) return
  try {
    await ElMessageBox.confirm(
      `确认将缺陷「${detail.value.key}」状态从「${statusLabel(detail.value.status)}」变更为「${statusLabel(target)}」？`,
      '状态流转确认',
      { type: 'warning', confirmButtonText: '确认流转', cancelButtonText: '取消' },
    )
  } catch {
    return
  }

  transitioning.value = target
  try {
    // 后端会按状态自动维护 resolved_at / closed_at（services/defects.py）
    detail.value = await api.patch<DefectDetail>(`/defects/${defectId.value}/`, {
      status: target,
      updated_at: detail.value.updated_at,
    })
    ElMessage.success('状态已更新')
  } catch (err) {
    notifyError(err)
  } finally {
    transitioning.value = null
  }
}

/* ---------------- 归档（仅系统管理员） ---------------- */
async function confirmArchive() {
  if (!detail.value) return
  try {
    await ElMessageBox.confirm(
      `归档后缺陷「${detail.value.key}」将置为已关闭，确认归档？`,
      '归档确认',
      { type: 'warning', confirmButtonText: '确认归档', cancelButtonText: '取消' },
    )
  } catch {
    return
  }

  try {
    await api.delete(`/defects/${defectId.value}/`)
    ElMessage.success('缺陷已归档')
    fetchDetail()
  } catch (err) {
    notifyError(err)
  }
}

/* ---------------- 编辑（乐观锁，含指派） ---------------- */
const editVisible = ref(false)
const editSubmitting = ref(false)
const editFormRef = ref<InstanceType<typeof DefectForm>>()
const editForm = ref<DefectFormModel>(defaultDefectForm())
const users = ref<UserBrief[]>([])

async function fetchUsers() {
  try {
    const data = await api.get<PageResult<UserBrief>>('/users/', { params: { page_size: 100 } })
    users.value = data.items
  } catch {
    // 经办人下拉缺失不影响主流程，静默降级
  }
}

function openEdit() {
  if (!detail.value) return
  editForm.value = {
    title: detail.value.title,
    description: detail.value.description,
    severity: detail.value.severity,
    priority: detail.value.priority,
    environment: detail.value.environment,
    version: detail.value.version,
    assignee_id: detail.value.assignee?.id ?? null,
  }
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
    detail.value = await api.patch<DefectDetail>(`/defects/${defectId.value}/`, {
      title: editForm.value.title.trim(),
      description: editForm.value.description.trim(),
      severity: editForm.value.severity,
      priority: editForm.value.priority,
      environment: editForm.value.environment.trim(),
      version: editForm.value.version.trim(),
      assignee_id: editForm.value.assignee_id,
      // 乐观锁：updated_at 原样回传，禁止格式化（common/optimistic.py）
      updated_at: detail.value.updated_at,
    })
    editVisible.value = false
    ElMessage.success('缺陷已保存')
  } catch (err) {
    notifyError(err)
  } finally {
    editSubmitting.value = false
  }
}

/* ---------------- 关联区跳转 ---------------- */
function goCase(row: LinkedTestCase) {
  router.push({ name: 'testcase-detail', params: { projectId: projectId.value, caseId: row.id } })
}

function goResultCase(row: LinkedTestResult) {
  router.push({ name: 'testcase-detail', params: { projectId: projectId.value, caseId: row.test_case } })
}

function goRun(row: LinkedTestResult) {
  router.push({ name: 'run-execution', params: { projectId: projectId.value, runId: row.test_run } })
}

function goRequirement(row: LinkedRequirement) {
  router.push({ name: 'requirement-detail', params: { projectId: projectId.value, reqId: row.id } })
}

function goList() {
  router.push({ name: 'defects', params: { projectId: projectId.value } })
}

watch(defectId, () => {
  detail.value = null
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

.panel-title {
  margin: 0 0 var(--sp-3);
  font-size: var(--fs-md);
  font-weight: 600;
  color: var(--text-primary);
}

.panel-head .panel-title {
  margin-bottom: 0;
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

.defect-key {
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
  color: var(--text-secondary);
}

.mono {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  font-size: var(--fs-sm);
}

/* 状态流转区 */
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

.transition-times {
  display: flex;
  gap: var(--sp-8);
  margin-top: var(--sp-4);
  padding-top: var(--sp-3);
  border-top: 1px solid var(--border-light);
}

.time-item {
  display: flex;
  align-items: baseline;
  gap: var(--sp-2);
}

.time-label {
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
}

/* 关联区 */
.link-table {
  width: 100%;
}

.cell-link {
  padding: 0;
  font-weight: 500;
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

.cell-muted {
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
}

.cell-time {
  color: var(--text-secondary);
  font-size: var(--fs-sm);
  font-variant-numeric: tabular-nums;
}

.empty-text {
  margin: 0;
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
}
</style>
