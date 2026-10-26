<template>
  <section v-loading="loading" class="case-detail-page">
    <!-- 加载失败且无数据：整页错误态 -->
    <div v-if="error && !detail" class="page-error">
      <p class="page-error-text">{{ error }}</p>
      <el-button type="primary" plain @click="loadAll">重试</el-button>
    </div>

    <template v-else-if="detail">
      <PageHeader :title="detail.title">
        <template #subtitle>
          <span class="header-meta">
            <span class="case-key">{{ detail.case_key }}</span>
            <StatusTag
              :tone="STATUS_TONE[detail.status]"
              :label="STATUS_LABELS[detail.status] || detail.status"
            />
            <StatusTag :tone="PRIORITY_TONE[detail.priority]" :label="detail.priority" />
            <span class="header-version">当前版本 v{{ detail.current_version }}</span>
          </span>
        </template>
        <template #actions>
          <el-button @click="openEdit">编辑</el-button>
          <el-button @click="confirmDuplicate">复制</el-button>
          <el-button @click="openMove">移动</el-button>
          <el-dropdown trigger="click" @command="onStatusCommand">
            <el-button>
              状态流转
              <el-icon class="el-icon--right"><ArrowDown /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item
                  v-for="status in nextStatuses"
                  :key="status"
                  :command="status"
                >
                  转为{{ STATUS_LABELS[status] }}
                </el-dropdown-item>
                <el-dropdown-item v-if="!nextStatuses.length" disabled>
                  当前状态无可用流转
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-button type="danger" plain @click="confirmDelete">删除</el-button>
        </template>
      </PageHeader>

      <div class="detail-layout">
        <!-- 主栏 -->
        <div class="detail-main">
          <section class="panel">
            <h2 class="panel-title">基本信息</h2>
            <div v-if="detail.description" class="info-block">
              <div class="info-label">描述</div>
              <div class="info-text">{{ detail.description }}</div>
            </div>
            <div class="info-block">
              <div class="info-label">前置条件</div>
              <div class="info-text" :class="{ 'is-empty': !detail.precondition }">
                {{ detail.precondition || '无前置条件' }}
              </div>
            </div>
          </section>

          <section class="panel">
            <h2 class="panel-title">测试步骤</h2>
            <el-table class="step-table" :data="detail.steps" size="small">
              <el-table-column label="序号" prop="order" width="64" align="center" />
              <el-table-column label="操作" prop="action" min-width="260" />
              <el-table-column label="预期结果" prop="expected" min-width="260" />
              <template #empty>
                <div class="empty-text">暂无测试步骤</div>
              </template>
            </el-table>
            <div v-if="detail.expected_result" class="info-block expected-block">
              <div class="info-label">整体预期结果</div>
              <div class="info-text">{{ detail.expected_result }}</div>
            </div>
          </section>

          <section class="panel">
            <h2 class="panel-title">版本历史</h2>
            <el-table
              v-loading="versionsLoading"
              class="version-table"
              :data="versions"
              size="small"
            >
              <el-table-column label="版本" width="86">
                <template #default="{ row }">
                  <span class="version-no">v{{ row.version }}</span>
                  <StatusTag
                    v-if="row.version === detail.current_version"
                    tone="accent"
                    label="当前"
                  />
                </template>
              </el-table-column>
              <el-table-column label="标题" prop="title" min-width="180" show-overflow-tooltip />
              <el-table-column label="变更摘要" min-width="180" show-overflow-tooltip>
                <template #default="{ row }">
                  <span class="cell-muted">{{ row.change_summary || '—' }}</span>
                </template>
              </el-table-column>
              <el-table-column label="创建人" width="110">
                <template #default="{ row }">
                  <span class="cell-muted">{{ userLabel(row.created_by) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="时间" width="130">
                <template #default="{ row }">
                  <span class="cell-time">{{ formatTime(row.created_at) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="72">
                <template #default="{ row }">
                  <el-button text type="primary" size="small" @click="openSnapshot(row.id)">
                    查看
                  </el-button>
                </template>
              </el-table-column>
              <template #empty>
                <div class="empty-text">{{ versionsLoading ? '加载中' : '暂无历史版本' }}</div>
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
                <dd class="case-key">{{ detail.case_key }}</dd>
              </div>
              <div class="attr-row">
                <dt>状态</dt>
                <dd>
                  <StatusTag
                    :tone="STATUS_TONE[detail.status]"
                    :label="STATUS_LABELS[detail.status] || detail.status"
                  />
                </dd>
              </div>
              <div class="attr-row">
                <dt>优先级</dt>
                <dd>
                  <StatusTag :tone="PRIORITY_TONE[detail.priority]" :label="detail.priority" />
                </dd>
              </div>
              <div class="attr-row">
                <dt>类型</dt>
                <dd>{{ TYPE_LABELS[detail.case_type] || detail.case_type }}</dd>
              </div>
              <div class="attr-row">
                <dt>自动化</dt>
                <dd>{{ AUTOMATION_LABELS[detail.automation_status] || detail.automation_status }}</dd>
              </div>
              <div class="attr-row">
                <dt>模块</dt>
                <dd>{{ modulePathText(detail.module_path, detail.module_name) }}</dd>
              </div>
              <div class="attr-row">
                <dt>标签</dt>
                <dd class="attr-tags">
                  <StatusTag v-for="tag in detail.tags" :key="tag.id" tone="info" :label="tag.name" />
                  <span v-if="!detail.tags.length" class="cell-muted">—</span>
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
                <dt>创建时间</dt>
                <dd class="cell-time">{{ formatTime(detail.created_at) }}</dd>
              </div>
              <div class="attr-row">
                <dt>更新时间</dt>
                <dd class="cell-time">{{ formatTime(detail.updated_at) }}</dd>
              </div>
            </dl>
          </section>

          <section class="panel">
            <h2 class="panel-title">操作历史</h2>
            <div v-loading="historyLoading" class="history-list">
              <div v-for="item in history" :key="item.id" class="history-item">
                <div class="history-line">
                  <span class="history-action">{{ AUDIT_ACTION_LABELS[item.action] || item.action }}</span>
                  <span class="history-user">{{ item.display_name || item.username || '系统' }}</span>
                  <span class="cell-time">{{ formatTime(item.created_at) }}</span>
                </div>
                <div v-if="changedFields(item)" class="history-detail">
                  变更字段：{{ changedFields(item) }}
                </div>
              </div>
              <div v-if="!history.length && !historyLoading" class="empty-text">暂无操作记录</div>
            </div>
          </section>
        </aside>
      </div>
    </template>

    <!-- 编辑用例 -->
    <el-dialog v-model="editVisible" title="编辑用例" width="760px" top="6vh" destroy-on-close>
      <CaseForm
        ref="editFormRef"
        :model="editForm"
        :modules="modules"
        :tags="tags"
        :members="members"
        mode="edit"
      />
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editSubmitting" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 移动模块 -->
    <el-dialog v-model="moveVisible" title="移动到模块" width="420px">
      <p class="dialog-tip">选择目标模块（留空为未分类）：</p>
      <el-tree-select
        v-model="moveModuleId"
        class="full-width"
        :data="modules"
        :props="{ value: 'id', label: 'name', children: 'children' }"
        node-key="id"
        check-strictly
        clearable
        :render-after-expand="false"
        placeholder="选择目标模块"
      />
      <template #footer>
        <el-button @click="moveVisible = false">取消</el-button>
        <el-button type="primary" :loading="moveSubmitting" @click="submitMove">确认移动</el-button>
      </template>
    </el-dialog>

    <!-- 版本快照 -->
    <el-dialog v-model="snapshotVisible" :title="snapshotTitle" width="720px" top="6vh">
      <div v-if="snapshot" class="snapshot-body">
        <div class="info-block">
          <div class="info-label">前置条件</div>
          <div class="info-text" :class="{ 'is-empty': !snapshot.precondition }">
            {{ snapshot.precondition || '无前置条件' }}
          </div>
        </div>
        <el-table class="step-table" :data="snapshot.steps" size="small">
          <el-table-column label="序号" prop="order" width="64" align="center" />
          <el-table-column label="操作" prop="action" min-width="240" />
          <el-table-column label="预期结果" prop="expected" min-width="240" />
          <template #empty>
            <div class="empty-text">该版本无步骤快照</div>
          </template>
        </el-table>
        <div v-if="snapshot.expected_result" class="info-block expected-block">
          <div class="info-label">整体预期结果</div>
          <div class="info-text">{{ snapshot.expected_result }}</div>
        </div>
      </div>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { api, notifyError, ApiError } from '@/api/client'
import PageHeader from '@/components/ui/PageHeader.vue'
import StatusTag from '@/components/ui/StatusTag.vue'
import CaseForm from './testcases/CaseForm.vue'
import {
  AUDIT_ACTION_LABELS,
  AUTOMATION_LABELS,
  PRIORITY_TONE,
  STATUS_LABELS,
  STATUS_TONE,
  STATUS_TRANSITIONS,
  TYPE_LABELS,
  flattenModules,
  formatTime,
  modulePathText,
  userLabel,
  type AuditLogItem,
  type CaseFormModel,
  type CaseStatus,
  type CaseVersionDetail,
  type CaseVersionItem,
  type ModuleNode,
  type TagBrief,
  type TestCaseDetail,
  type UserBrief,
} from './testcases/shared'

const route = useRoute()
const router = useRouter()
const projectId = computed(() => Number(route.params.projectId))
const caseId = computed(() => Number(route.params.caseId))

/* ---------------- 用例数据 ---------------- */
const detail = ref<TestCaseDetail | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

const modules = ref<ModuleNode[]>([])
const tags = ref<TagBrief[]>([])
const members = ref<UserBrief[]>([])
const versions = ref<CaseVersionItem[]>([])
const versionsLoading = ref(false)
const history = ref<AuditLogItem[]>([])
const historyLoading = ref(false)

const nextStatuses = computed<CaseStatus[]>(() => {
  if (!detail.value) return []
  return STATUS_TRANSITIONS[detail.value.status] ?? []
})

async function fetchDetail() {
  loading.value = true
  error.value = null
  try {
    detail.value = await api.get<TestCaseDetail>(`/testcases/${caseId.value}/`)
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : '用例加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

async function fetchVersions() {
  versionsLoading.value = true
  try {
    const data = await api.get<{ items: CaseVersionItem[] }>(`/testcases/${caseId.value}/versions/`, {
      params: { page: 1, page_size: 50 },
    })
    versions.value = data.items
  } catch {
    versions.value = []
  } finally {
    versionsLoading.value = false
  }
}

async function fetchHistory() {
  historyLoading.value = true
  try {
    const data = await api.get<{ items: AuditLogItem[] }>(`/testcases/${caseId.value}/history/`, {
      params: { page: 1, page_size: 50 },
    })
    history.value = data.items
  } catch {
    history.value = []
  } finally {
    historyLoading.value = false
  }
}

async function fetchMeta() {
  try {
    const [moduleList, tagList, memberList] = await Promise.all([
      api.get<ModuleNode[]>(`/projects/${projectId.value}/modules/`),
      api.get<TagBrief[]>(`/projects/${projectId.value}/tags/`),
      api.get<{ user: UserBrief }[]>(`/projects/${projectId.value}/members/`),
    ])
    modules.value = moduleList
    tags.value = tagList
    members.value = memberList.map((item) => item.user)
  } catch {
    // 元数据缺失只影响表单下拉，静默降级
  }
}

function loadAll() {
  fetchDetail()
  fetchVersions()
  fetchHistory()
  fetchMeta()
}

/** 操作历史摘要：旧/新数据合并后的字段名列表 */
function changedFields(item: AuditLogItem): string {
  const keys = new Set([...Object.keys(item.old_data ?? {}), ...Object.keys(item.new_data ?? {})])
  return [...keys].join('、')
}

/* ---------------- 版本快照 ---------------- */
const snapshotVisible = ref(false)
const snapshot = ref<CaseVersionDetail | null>(null)

const snapshotTitle = computed(
  () => (snapshot.value ? `版本 v${snapshot.value.version} 快照` : '版本快照'),
)

async function openSnapshot(versionId: number) {
  try {
    snapshot.value = await api.get<CaseVersionDetail>(`/testcase-versions/${versionId}/`)
    snapshotVisible.value = true
  } catch (err) {
    notifyError(err)
  }
}

/* ---------------- 编辑 ---------------- */
const editVisible = ref(false)
const editSubmitting = ref(false)
const editFormRef = ref<InstanceType<typeof CaseForm> | null>(null)
const editForm = ref<CaseFormModel>({
  title: '',
  module_id: null,
  priority: 'P1',
  case_type: 'functional',
  precondition: '',
  description: '',
  expected_result: '',
  steps: [],
  tag_ids: [],
  owner_id: null,
  change_summary: '',
})

function openEdit() {
  if (!detail.value) return
  const data = detail.value
  editForm.value = {
    title: data.title,
    module_id: data.module_id,
    priority: data.priority,
    case_type: data.case_type,
    precondition: data.precondition,
    description: data.description,
    expected_result: data.expected_result,
    steps: data.steps.map((step, index) => ({
      order: index + 1,
      action: step.action,
      expected: step.expected,
    })),
    tag_ids: data.tags.map((tag) => tag.id),
    owner_id: data.owner?.id ?? null,
    change_summary: '',
  }
  editVisible.value = true
}

async function submitEdit() {
  const form = editFormRef.value
  if (form && !(await form.validate())) return
  if (!detail.value) return
  editSubmitting.value = true
  try {
    const model = editForm.value
    await api.patch(`/testcases/${caseId.value}/`, {
      // 乐观锁：原样回传读取到的 updated_at（§52）
      updated_at: detail.value.updated_at,
      title: model.title,
      module_id: model.module_id,
      priority: model.priority,
      case_type: model.case_type,
      precondition: model.precondition,
      steps: model.steps.map((step, index) => ({
        order: index + 1,
        action: step.action,
        expected: step.expected,
      })),
      expected_result: model.expected_result,
      description: model.description,
      tag_ids: model.tag_ids,
      owner_id: model.owner_id,
      change_summary: model.change_summary,
    })
    ElMessage.success('用例已更新')
    editVisible.value = false
    loadAll()
  } catch (err) {
    notifyError(err)
  } finally {
    editSubmitting.value = false
  }
}

/* ---------------- 状态流转 ---------------- */
function onStatusCommand(status: CaseStatus) {
  if (!detail.value) return
  ElMessageBox.confirm(
    `确认将用例「${detail.value.case_key}」状态从${STATUS_LABELS[detail.value.status]}转为${STATUS_LABELS[status]}？`,
    '状态流转确认',
    { type: 'warning', confirmButtonText: '确认流转', cancelButtonText: '取消' },
  )
    .then(async () => {
      try {
        await api.patch(`/testcases/${caseId.value}/`, {
          updated_at: detail.value!.updated_at,
          status,
        })
        ElMessage.success(`状态已转为${STATUS_LABELS[status]}`)
        loadAll()
      } catch (err) {
        notifyError(err)
      }
    })
    .catch(() => undefined)
}

/* ---------------- 复制 / 移动 / 删除 ---------------- */
function confirmDuplicate() {
  if (!detail.value) return
  ElMessageBox.confirm(
    `确认复制用例「${detail.value.case_key}」？将生成一条新的用例（标题加「副本」）。`,
    '复制用例确认',
    { type: 'warning', confirmButtonText: '确认复制', cancelButtonText: '取消' },
  )
    .then(async () => {
      try {
        const created = await api.post<TestCaseDetail>(`/testcases/${caseId.value}/duplicate/`)
        ElMessage.success(`已复制为 ${created.case_key}`)
        router.replace({ name: 'testcase-detail', params: { projectId: projectId.value, caseId: created.id } })
      } catch (err) {
        notifyError(err)
      }
    })
    .catch(() => undefined)
}

const moveVisible = ref(false)
const moveSubmitting = ref(false)
const moveModuleId = ref<number | null>(null)

function openMove() {
  moveModuleId.value = detail.value?.module_id ?? null
  moveVisible.value = true
}

async function submitMove() {
  moveSubmitting.value = true
  try {
    await api.post(`/testcases/${caseId.value}/move/`, { module_id: moveModuleId.value })
    const target = flattenModules(modules.value).find((m) => m.id === moveModuleId.value)
    ElMessage.success(moveModuleId.value == null ? '已移动到「未分类」' : `已移动到「${target?.name ?? ''}」`)
    moveVisible.value = false
    loadAll()
  } catch (err) {
    notifyError(err)
  } finally {
    moveSubmitting.value = false
  }
}

function confirmDelete() {
  if (!detail.value) return
  ElMessageBox.confirm(
    `确认删除用例「${detail.value.case_key}」？删除后进入软删状态，可在审计中追溯。`,
    '删除用例确认',
    { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' },
  )
    .then(async () => {
      try {
        await api.delete(`/testcases/${caseId.value}/`)
        ElMessage.success('用例已删除')
        router.push({ name: 'testcases', params: { projectId: projectId.value } })
      } catch (err) {
        notifyError(err)
      }
    })
    .catch(() => undefined)
}

watch(
  () => route.params.caseId,
  () => {
    if (route.name === 'testcase-detail') loadAll()
  },
)

onMounted(loadAll)
</script>

<style scoped>
.case-detail-page {
  min-height: 100%;
  padding: var(--sp-5) var(--sp-6) var(--sp-6);
}

.page-error {
  min-height: 320px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--sp-3);
}

.page-error-text {
  margin: 0;
  color: var(--danger-600);
}

.header-meta {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
}

.case-key {
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

.header-version {
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
}

/* ---- 布局 ---- */
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

.panel-title {
  margin: 0 0 var(--sp-3);
  font-size: var(--fs-md);
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: 0.02em;
}

/* ---- 基本信息 ---- */
.info-block + .info-block {
  margin-top: var(--sp-3);
}

.info-label {
  margin-bottom: var(--sp-1);
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--text-tertiary);
}

.info-text {
  color: var(--text-primary);
  line-height: var(--lh-base);
  white-space: pre-wrap;
  word-break: break-word;
}

.info-text.is-empty {
  color: var(--text-placeholder);
}

.expected-block {
  padding-top: var(--sp-3);
  border-top: 1px dashed var(--border-light);
}

/* ---- 表格 ---- */
.step-table :deep(.el-table__cell) {
  padding: 5px 0;
}

.version-table :deep(.el-table__cell) {
  padding: 4px 0;
}

.version-no {
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
  color: var(--text-secondary);
  margin-right: var(--sp-1);
}

.cell-muted {
  color: var(--text-secondary);
}

.cell-time {
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}

.empty-text {
  padding: var(--sp-4) 0;
  color: var(--text-tertiary);
  text-align: center;
}

/* ---- 属性 ---- */
.attr-list {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.attr-row {
  display: grid;
  grid-template-columns: 62px minmax(0, 1fr);
  gap: var(--sp-2);
  align-items: start;
  font-size: var(--fs-base);
}

.attr-row dt {
  color: var(--text-tertiary);
}

.attr-row dd {
  margin: 0;
  color: var(--text-primary);
  word-break: break-word;
}

.attr-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

/* ---- 操作历史 ---- */
.history-list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  max-height: 360px;
  overflow: auto;
}

.history-item {
  padding-left: var(--sp-3);
  border-left: 2px solid var(--border-light);
}

.history-line {
  display: flex;
  align-items: baseline;
  gap: var(--sp-2);
  flex-wrap: wrap;
}

.history-action {
  font-weight: 600;
  color: var(--text-primary);
  font-size: var(--fs-sm);
}

.history-user {
  color: var(--text-secondary);
  font-size: var(--fs-sm);
}

.history-detail {
  margin-top: 2px;
  color: var(--text-tertiary);
  font-size: var(--fs-xs);
  word-break: break-all;
}

/* ---- 弹窗 ---- */
.full-width {
  width: 100%;
}

.dialog-tip {
  margin: 0 0 var(--sp-3);
  color: var(--text-secondary);
  font-size: var(--fs-sm);
}

.snapshot-body .step-table {
  margin-top: var(--sp-3);
}

@media (max-width: 1080px) {
  .detail-layout {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
