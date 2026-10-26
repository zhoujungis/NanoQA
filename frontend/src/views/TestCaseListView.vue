<template>
  <section class="case-list-page">
    <PageHeader title="用例管理" :subtitle="subtitleText">
      <template #actions>
        <el-button @click="importVisible = true">导入</el-button>
        <el-button @click="exportVisible = true">导出</el-button>
        <el-button type="primary" @click="openCreate">新建用例</el-button>
      </template>
    </PageHeader>

    <div class="list-layout">
      <ModuleTree
        :nodes="modules"
        :total="total"
        :selected-id="selectedModuleId"
        :include-submodules="includeSubmodules"
        :loading="modulesLoading"
        :error="modulesError"
        @select="onModuleSelect"
        @update:include-submodules="onIncludeChange"
        @drop-case="onDropCase"
        @retry="fetchModules"
      />

      <div class="list-main">
        <!-- 筛选工具条 -->
        <div class="filter-bar">
          <el-input
            v-model="filters.q"
            class="filter-search"
            clearable
            placeholder="搜索标题 / 编号 / 预期结果，支持筛选语法"
            @input="onSearchInput"
            @clear="onSearchInput"
            @keyup.enter="flushSearch"
          />
          <el-select
            v-model="filters.priority"
            class="filter-select"
            clearable
            placeholder="优先级"
            @change="onFilterChange"
          >
            <el-option
              v-for="item in PRIORITY_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
          <el-select
            v-model="filters.status"
            class="filter-select"
            clearable
            placeholder="状态"
            @change="onFilterChange"
          >
            <el-option
              v-for="item in STATUS_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
          <el-select
            v-model="filters.case_type"
            class="filter-select"
            clearable
            placeholder="类型"
            @change="onFilterChange"
          >
            <el-option
              v-for="item in TYPE_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
          <el-select
            v-model="filters.tag"
            class="filter-select"
            clearable
            placeholder="标签"
            @change="onFilterChange"
          >
            <el-option v-for="tag in tags" :key="tag.id" :label="tag.name" :value="tag.name" />
          </el-select>
          <el-button text @click="resetFilters">重置</el-button>
        </div>

        <!-- 批量操作条 -->
        <div v-if="selection.length" class="batch-bar">
          <span class="batch-count">已选 {{ selection.length }} 项</span>
          <div class="batch-actions">
            <el-button size="small" @click="openBatch('priority')">批量改优先级</el-button>
            <el-button size="small" @click="openBatch('status')">批量改状态</el-button>
            <el-button size="small" @click="openBatch('move')">批量移动</el-button>
            <el-button size="small" @click="openBatch('tag')">批量标签</el-button>
            <el-button size="small" type="danger" plain @click="confirmBatchDelete">批量删除</el-button>
            <el-button size="small" text @click="clearSelection">取消选择</el-button>
          </div>
        </div>

        <!-- 表格区 -->
        <div class="table-wrap">
          <!-- 错误态 -->
          <div v-if="error && !rows.length" class="error-panel">
            <p class="error-text">{{ error }}</p>
            <el-button size="small" type="primary" plain @click="fetchCases">重试</el-button>
          </div>

          <el-table
            v-else
            v-loading="loading"
            class="case-table"
            :data="rows"
            height="100%"
            row-key="id"
            element-loading-text="加载中"
            @selection-change="onSelectionChange"
            @row-click="onRowClick"
          >
            <el-table-column type="selection" width="40" reserve-selection />
            <el-table-column label="编号" prop="case_key" width="150">
              <template #default="{ row }">
                <span class="case-key">{{ row.case_key }}</span>
              </template>
            </el-table-column>
            <el-table-column label="标题" prop="title" min-width="240" show-overflow-tooltip>
              <template #default="{ row }">
                <span
                  class="case-title"
                  draggable="true"
                  @dragstart="onDragStart($event, row)"
                  @click.stop="openDetail(row)"
                >
                  {{ row.title }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="优先级" width="76" align="center">
              <template #default="{ row }">
                <StatusTag :tone="PRIORITY_TONE[row.priority as Priority]" :label="row.priority" />
              </template>
            </el-table-column>
            <el-table-column label="类型" width="80" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="cell-muted">{{ TYPE_LABELS[row.case_type] || row.case_type }}</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="86">
              <template #default="{ row }">
                <StatusTag
                  :tone="STATUS_TONE[row.status as CaseStatus]"
                  :label="STATUS_LABELS[row.status as CaseStatus] || row.status"
                />
              </template>
            </el-table-column>
            <el-table-column label="标签" min-width="150">
              <template #default="{ row }">
                <div class="tag-cell">
                  <StatusTag
                    v-for="tag in row.tags"
                    :key="tag.id"
                    tone="info"
                    :label="tag.name"
                  />
                  <span v-if="!row.tags.length" class="cell-muted">—</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="负责人" width="110">
              <template #default="{ row }">
                <span class="cell-muted">{{ userLabel(row.owner) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="更新时间" width="130">
              <template #default="{ row }">
                <span class="cell-time">{{ formatTime(row.updated_at) }}</span>
              </template>
            </el-table-column>

            <template #empty>
              <div class="empty-state">
                <p class="empty-text">{{ emptyText }}</p>
              </div>
            </template>
          </el-table>
        </div>

        <!-- 分页 -->
        <div class="pager">
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
      </div>
    </div>

    <!-- 导入 / 导出（§61） -->
    <ImportExportDialog
      v-model="importVisible"
      mode="import"
      :project-id="projectId"
      :modules="modules"
      @refresh="onImportExportDone"
    />
    <ImportExportDialog
      v-model="exportVisible"
      mode="export"
      :project-id="projectId"
      :modules="modules"
    />

    <!-- 新建用例 -->
    <el-dialog v-model="createVisible" title="新建用例" width="760px" top="6vh" destroy-on-close>
      <CaseForm
        ref="createFormRef"
        :model="createForm"
        :modules="modules"
        :tags="tags"
        :members="members"
        mode="create"
      />
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button :loading="createSubmitting" @click="submitCreate('draft')">保存草稿</el-button>
        <el-button type="primary" :loading="createSubmitting" @click="submitCreate('active')">
          保存并激活
        </el-button>
      </template>
    </el-dialog>

    <!-- 批量改优先级 -->
    <el-dialog v-model="batchDialog.priority" title="批量修改优先级" width="420px">
      <p class="batch-tip">将对已选的 {{ selection.length }} 条用例统一设置优先级：</p>
      <el-select v-model="batchForm.priority" class="full-width">
        <el-option
          v-for="item in PRIORITY_OPTIONS"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
      <template #footer>
        <el-button @click="batchDialog.priority = false">取消</el-button>
        <el-button type="primary" :loading="batchRunning" @click="submitBatch('update', { priority: batchForm.priority })">
          确认执行
        </el-button>
      </template>
    </el-dialog>

    <!-- 批量改状态 -->
    <el-dialog v-model="batchDialog.status" title="批量修改状态" width="420px">
      <p class="batch-tip">将对已选的 {{ selection.length }} 条用例流转状态（非法流转会单独报错）：</p>
      <el-select v-model="batchForm.status" class="full-width">
        <el-option
          v-for="item in STATUS_OPTIONS"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
      <template #footer>
        <el-button @click="batchDialog.status = false">取消</el-button>
        <el-button type="primary" :loading="batchRunning" @click="submitBatch('update', { status: batchForm.status })">
          确认执行
        </el-button>
      </template>
    </el-dialog>

    <!-- 批量移动 -->
    <el-dialog v-model="batchDialog.move" title="批量移动到模块" width="420px">
      <p class="batch-tip">将把已选的 {{ selection.length }} 条用例移动到目标模块：</p>
      <el-tree-select
        v-model="batchForm.module_id"
        class="full-width"
        :data="modules"
        :props="{ value: 'id', label: 'name', children: 'children' }"
        node-key="id"
        check-strictly
        clearable
        :render-after-expand="false"
        placeholder="选择目标模块（留空为未分类）"
      />
      <template #footer>
        <el-button @click="batchDialog.move = false">取消</el-button>
        <el-button type="primary" :loading="batchRunning" @click="submitBatch('move', { module_id: batchForm.module_id })">
          确认执行
        </el-button>
      </template>
    </el-dialog>

    <!-- 批量标签 -->
    <el-dialog v-model="batchDialog.tag" title="批量调整标签" width="460px">
      <p class="batch-tip">为已选的 {{ selection.length }} 条用例添加或移除标签：</p>
      <div class="batch-tag-form">
        <span class="batch-tag-label">添加标签</span>
        <el-select v-model="batchForm.add_tag_ids" multiple clearable placeholder="选择要添加的标签">
          <el-option v-for="tag in tags" :key="tag.id" :label="tag.name" :value="tag.id" />
        </el-select>
        <span class="batch-tag-label">移除标签</span>
        <el-select v-model="batchForm.remove_tag_ids" multiple clearable placeholder="选择要移除的标签">
          <el-option v-for="tag in tags" :key="tag.id" :label="tag.name" :value="tag.id" />
        </el-select>
      </div>
      <template #footer>
        <el-button @click="batchDialog.tag = false">取消</el-button>
        <el-button
          type="primary"
          :loading="batchRunning"
          @click="submitBatch('tag', { add_tag_ids: batchForm.add_tag_ids, remove_tag_ids: batchForm.remove_tag_ids })"
        >
          确认执行
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, notifyError, ApiError, type PageResult } from '@/api/client'
import PageHeader from '@/components/ui/PageHeader.vue'
import StatusTag from '@/components/ui/StatusTag.vue'
import ModuleTree from './testcases/ModuleTree.vue'
import CaseForm from './testcases/CaseForm.vue'
import ImportExportDialog from './testcases/ImportExportDialog.vue'
import {
  PRIORITY_OPTIONS,
  PRIORITY_TONE,
  STATUS_LABELS,
  STATUS_OPTIONS,
  STATUS_TONE,
  TYPE_LABELS,
  TYPE_OPTIONS,
  defaultCaseForm,
  flattenModules,
  formatTime,
  userLabel,
  type BatchResult,
  type CaseFormModel,
  type CaseStatus,
  type ModuleNode,
  type Priority,
  type TagBrief,
  type TestCaseListItem,
  type UserBrief,
} from './testcases/shared'

const route = useRoute()
const router = useRouter()
const projectId = computed(() => Number(route.params.projectId))

/* ---------------- 模块树 / 标签 / 成员 ---------------- */
const modules = ref<ModuleNode[]>([])
const modulesLoading = ref(false)
const modulesError = ref<string | null>(null)
const tags = ref<TagBrief[]>([])
const members = ref<UserBrief[]>([])

async function fetchModules() {
  modulesLoading.value = true
  modulesError.value = null
  try {
    modules.value = await api.get<ModuleNode[]>(`/projects/${projectId.value}/modules/`)
  } catch (error) {
    modulesError.value = error instanceof ApiError ? error.message : '模块加载失败'
  } finally {
    modulesLoading.value = false
  }
}

async function fetchMeta() {
  try {
    const [tagList, memberList] = await Promise.all([
      api.get<TagBrief[]>(`/projects/${projectId.value}/tags/`),
      api.get<{ user: UserBrief }[]>(`/projects/${projectId.value}/members/`),
    ])
    tags.value = tagList
    members.value = memberList.map((item) => item.user)
  } catch {
    // 标签/负责人下拉缺失不影响主流程，静默降级
  }
}

/* ---------------- 列表查询 ---------------- */
const rows = ref<TestCaseListItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const error = ref<string | null>(null)
const selectedModuleId = ref<number | null>(null)
const includeSubmodules = ref(true)

const filters = reactive({
  q: '',
  priority: '' as Priority | '',
  status: '' as CaseStatus | '',
  case_type: '',
  tag: '',
})

const subtitleText = computed(() => {
  const scope = selectedModuleId.value
    ? `模块：${flattenModules(modules.value).find((m) => m.id === selectedModuleId.value)?.name ?? ''}`
    : '全部模块'
  return `${scope} · 共 ${total.value} 条用例`
})

const emptyText = computed(() => {
  if (filters.q || filters.priority || filters.status || filters.case_type || filters.tag) {
    return '没有符合当前筛选条件的用例'
  }
  return selectedModuleId.value ? '该模块下暂无用例' : '暂无用例，点击右上角「新建用例」创建'
})

async function fetchCases() {
  loading.value = true
  error.value = null
  try {
    const params: Record<string, string | number> = {
      page: page.value,
      page_size: pageSize.value,
      ordering: '-updated_at',
    }
    const q = filters.q.trim()
    if (q) params.q = q
    if (filters.priority) params.priority = filters.priority
    if (filters.status) params.status = filters.status
    if (filters.case_type) params.case_type = filters.case_type
    if (filters.tag) params.tag = filters.tag
    if (selectedModuleId.value != null) {
      params.module_id = selectedModuleId.value
      if (includeSubmodules.value) params.include_submodules = '1'
    }
    const data = await api.get<PageResult<TestCaseListItem>>(
      `/projects/${projectId.value}/testcases/`,
      { params },
    )
    rows.value = data.items
    total.value = data.total
  } catch (err) {
    if (rows.value.length) {
      notifyError(err)
    } else {
      error.value = err instanceof ApiError ? err.message : '用例加载失败，请稍后重试'
    }
  } finally {
    loading.value = false
  }
}

/* ---------------- 筛选交互 ---------------- */
let searchTimer: ReturnType<typeof setTimeout> | undefined

function onSearchInput() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    fetchCases()
  }, 300)
}

function flushSearch() {
  clearTimeout(searchTimer)
  page.value = 1
  fetchCases()
}

function onFilterChange() {
  page.value = 1
  fetchCases()
}

function resetFilters() {
  filters.q = ''
  filters.priority = ''
  filters.status = ''
  filters.case_type = ''
  filters.tag = ''
  selectedModuleId.value = null
  page.value = 1
  fetchCases()
}

function onModuleSelect(id: number | null) {
  selectedModuleId.value = id
  page.value = 1
  fetchCases()
}

function onIncludeChange(value: boolean) {
  includeSubmodules.value = value
  if (selectedModuleId.value != null) {
    page.value = 1
    fetchCases()
  }
}

function onPageChange(value: number) {
  page.value = value
  fetchCases()
}

function onSizeChange(value: number) {
  pageSize.value = value
  page.value = 1
  fetchCases()
}

/* ---------------- 行交互 / 拖拽移动 ---------------- */
function openDetail(row: TestCaseListItem) {
  router.push({ name: 'testcase-detail', params: { projectId: projectId.value, caseId: row.id } })
}

function onRowClick(row: TestCaseListItem, column: { type?: string }) {
  if (column && column.type === 'selection') return
  openDetail(row)
}

function onDragStart(event: DragEvent, row: TestCaseListItem) {
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/case-id', String(row.id))
  }
}

async function onDropCase(payload: { caseId: number; moduleId: number | null }) {
  const row = rows.value.find((item) => item.id === payload.caseId)
  if (row && row.module_id === payload.moduleId) return
  try {
    await api.post(`/testcases/${payload.caseId}/move/`, { module_id: payload.moduleId })
    const target = flattenModules(modules.value).find((m) => m.id === payload.moduleId)
    ElMessage.success(payload.moduleId == null ? '已移动到「未分类」' : `已移动到「${target?.name ?? ''}」`)
    fetchCases()
    fetchModules()
  } catch (err) {
    notifyError(err)
  }
}

/* ---------------- 批量操作 ---------------- */
const selection = ref<TestCaseListItem[]>([])
const batchRunning = ref(false)
const batchDialog = reactive({ priority: false, status: false, move: false, tag: false })
const batchForm = reactive({
  priority: 'P1' as Priority,
  status: 'active' as CaseStatus,
  module_id: null as number | null,
  add_tag_ids: [] as number[],
  remove_tag_ids: [] as number[],
})

function onSelectionChange(value: TestCaseListItem[]) {
  selection.value = value
}

function clearSelection() {
  selection.value = []
}

function openBatch(type: 'priority' | 'status' | 'move' | 'tag') {
  if (!selection.value.length) return
  if (type === 'tag') {
    batchForm.add_tag_ids = []
    batchForm.remove_tag_ids = []
  }
  batchDialog[type] = true
}

async function submitBatch(op: 'update' | 'move' | 'tag' | 'delete', params: Record<string, unknown>) {
  if (!selection.value.length) return
  batchRunning.value = true
  try {
    const result = await api.post<BatchResult>(`/projects/${projectId.value}/testcases/batch/`, {
      op,
      test_case_ids: selection.value.map((row) => row.id),
      params,
    })
    batchDialog.priority = false
    batchDialog.status = false
    batchDialog.move = false
    batchDialog.tag = false
    if (result.failed.length) {
      const detail = result.failed.map((item) => `#${item.id}：${item.reason}`).join('\n')
      await ElMessageBox.alert(
        detail,
        `成功 ${result.succeeded.length} 条，失败 ${result.failed.length} 条`,
        { type: 'warning', customClass: 'nano-batch-result' },
      ).catch(() => undefined)
    } else {
      ElMessage.success(`已更新 ${result.succeeded.length} 条用例`)
    }
    clearSelection()
    fetchCases()
    fetchModules()
  } catch (err) {
    notifyError(err)
  } finally {
    batchRunning.value = false
  }
}

function confirmBatchDelete() {
  if (!selection.value.length) return
  ElMessageBox.confirm(
    `确认删除已选的 ${selection.value.length} 条用例？删除后进入软删状态，可在审计中追溯。`,
    '批量删除确认',
    { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' },
  )
    .then(() => submitBatch('delete', {}))
    .catch(() => undefined)
}

/* ---------------- 新建用例 ---------------- */
const createVisible = ref(false)
const importVisible = ref(false)
const exportVisible = ref(false)

function onImportExportDone() {
  importVisible.value = false
  exportVisible.value = false
  fetchCases()
}
const createSubmitting = ref(false)
const createFormRef = ref<InstanceType<typeof CaseForm> | null>(null)
const createForm = ref<CaseFormModel>(defaultCaseForm())

function openCreate() {
  createForm.value = defaultCaseForm(selectedModuleId.value)
  createVisible.value = true
}

async function submitCreate(status: 'draft' | 'active') {
  const form = createFormRef.value
  if (form && !(await form.validate())) return
  createSubmitting.value = true
  try {
    const model = createForm.value
    await api.post(`/projects/${projectId.value}/testcases/`, {
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
      status,
    })
    ElMessage.success(status === 'draft' ? '用例已保存为草稿' : '用例已创建并激活')
    createVisible.value = false
    page.value = 1
    fetchCases()
    fetchModules()
  } catch (err) {
    notifyError(err)
  } finally {
    createSubmitting.value = false
  }
}

watch(
  () => route.params.projectId,
  () => {
    selectedModuleId.value = null
    page.value = 1
    fetchModules()
    fetchMeta()
    fetchCases()
  },
)

onMounted(() => {
  fetchModules()
  fetchMeta()
  fetchCases()
})
</script>

<style scoped>
.case-list-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: var(--sp-5) var(--sp-6) var(--sp-4);
}

.list-layout {
  flex: 1;
  min-height: 0;
  display: flex;
  gap: var(--sp-4);
}

.list-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

/* ---- 工具条 ---- */
.filter-bar {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
}

.filter-search {
  width: 380px;
  max-width: 100%;
}

.filter-select {
  width: 116px;
}

/* ---- 批量条 ---- */
.batch-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  padding: var(--sp-2) var(--sp-3);
  background: var(--accent-50);
  border: 1px solid var(--accent-100);
  border-radius: var(--radius-md);
}

.batch-count {
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--accent-700);
}

.batch-actions {
  display: flex;
  align-items: center;
  gap: var(--sp-1);
  flex-wrap: wrap;
}

/* ---- 表格 ---- */
.table-wrap {
  flex: 1;
  min-height: 0;
  background: var(--bg-surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.case-table {
  height: 100%;
}

.case-table :deep(.el-table__cell) {
  padding: 5px 0;
}

.case-table :deep(th.el-table__cell) {
  padding: 7px 0;
}

.case-key {
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

.case-title {
  color: var(--accent-600);
  font-weight: 500;
  cursor: pointer;
}

.case-title:hover {
  text-decoration: underline;
  text-underline-offset: 3px;
}

.cell-muted {
  color: var(--text-secondary);
}

.cell-time {
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}

.tag-cell {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.empty-state {
  padding: var(--sp-8) 0;
}

.empty-text {
  margin: 0;
  color: var(--text-tertiary);
}

.error-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--sp-3);
}

.error-text {
  margin: 0;
  color: var(--danger-600);
}

/* ---- 分页 ---- */
.pager {
  display: flex;
  justify-content: flex-end;
}

/* ---- 弹窗 ---- */
.full-width {
  width: 100%;
}

.batch-tip {
  margin: 0 0 var(--sp-3);
  color: var(--text-secondary);
  font-size: var(--fs-sm);
}

.batch-tag-form {
  display: grid;
  grid-template-columns: 72px 1fr;
  gap: var(--sp-2) var(--sp-3);
  align-items: center;
}

.batch-tag-label {
  color: var(--text-secondary);
  font-size: var(--fs-sm);
}
</style>
