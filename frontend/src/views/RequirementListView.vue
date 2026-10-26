<template>
  <section class="page">
    <PageHeader title="需求" :subtitle="`共 ${total} 条需求 · 点击行查看覆盖与关联用例`">
      <template #actions>
        <el-button type="primary" @click="openCreate">新建需求</el-button>
      </template>
    </PageHeader>

    <div class="panel">
      <!-- 筛选工具条 -->
      <div class="filter-bar">
        <el-input
          v-model="filters.q"
          class="filter-search"
          clearable
          placeholder="搜索编号 / 标题 / 描述"
          @input="onSearchInput"
          @clear="onSearchInput"
          @keyup.enter="flushSearch"
        />
        <el-select
          v-model="filters.status"
          class="filter-select"
          clearable
          placeholder="状态"
          @change="onFilterChange"
        >
          <el-option v-for="item in STATUS_OPTIONS" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select
          v-model="filters.priority"
          class="filter-select"
          clearable
          placeholder="优先级"
          @change="onFilterChange"
        >
          <el-option v-for="item in PRIORITY_OPTIONS" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select
          v-model="filters.owner_id"
          class="filter-select"
          clearable
          filterable
          placeholder="负责人"
          @change="onFilterChange"
        >
          <el-option
            v-for="user in users"
            :key="user.id"
            :label="user.display_name || user.username"
            :value="user.id"
          />
        </el-select>
        <el-button text @click="resetFilters">重置</el-button>
      </div>

      <!-- 加载失败：错误态 + 重试 -->
      <div v-if="error && !rows.length" class="state-box">
        <p class="state-text">{{ error }}</p>
        <el-button size="small" type="primary" plain @click="fetchList">重试</el-button>
      </div>

      <template v-else>
        <el-table
          v-loading="loading"
          :data="rows"
          row-key="id"
          class="req-table"
          @row-click="goDetail"
        >
          <el-table-column label="编号" width="150">
            <template #default="{ row }">
              <span class="req-key">{{ row.key }}</span>
            </template>
          </el-table-column>
          <el-table-column label="标题" min-width="260" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="req-title">{{ row.title }}</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="96">
            <template #default="{ row }">
              <StatusTag :tone="statusTone(row.status)" :label="statusLabel(row.status)" />
            </template>
          </el-table-column>
          <el-table-column label="优先级" width="80" align="center">
            <template #default="{ row }">
              <StatusTag :tone="priorityTone(row.priority)" :label="row.priority" />
            </template>
          </el-table-column>
          <el-table-column label="负责人" width="120">
            <template #default="{ row }">
              <span class="cell-muted">{{ userLabel(row.owner) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="覆盖率" width="130">
            <template #default="{ row }">
              <div v-if="coverages[row.id]" class="coverage-cell">
                <el-progress
                  :percentage="coveragePercent(coverages[row.id])"
                  :stroke-width="4"
                  :show-text="false"
                  :status="coverageBarStatus(coverages[row.id])"
                />
                <span class="mono">{{ coveragePercent(coverages[row.id]) }}%</span>
              </div>
              <span v-else class="cell-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="更新时间" width="150">
            <template #default="{ row }">
              <span class="cell-time">{{ formatTime(row.updated_at) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="" width="72" align="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click.stop="goDetail(row)">详情</el-button>
            </template>
          </el-table-column>

          <template #empty>
            <div class="empty-state">
              <p class="empty-text">{{ emptyText }}</p>
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
    </div>

    <!-- 新建需求 -->
    <el-dialog v-model="createVisible" title="新建需求" width="560px" :close-on-click-modal="false">
      <RequirementForm ref="createFormRef" :model="createForm" :users="users" mode="create" />
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, notifyError, type PageResult } from '@/api/client'
import PageHeader from '@/components/ui/PageHeader.vue'
import StatusTag from '@/components/ui/StatusTag.vue'
import RequirementForm from './requirements/RequirementForm.vue'
import {
  PRIORITY_OPTIONS,
  STATUS_OPTIONS,
  defaultRequirementForm,
  formatTime,
  priorityTone,
  statusLabel,
  statusTone,
  userLabel,
  type Coverage,
  type RequirementFormModel,
  type RequirementListItem,
  type UserBrief,
} from './requirements/shared'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.projectId)

/* ---------------- 列表查询 ---------------- */
const rows = ref<RequirementListItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const error = ref<string | null>(null)
/** 行内覆盖率（列表接口不返回，逐行取 coverage 接口，失败不影响列表） */
const coverages = ref<Record<number, Coverage>>({})

const filters = reactive({
  q: '',
  status: '',
  priority: '',
  owner_id: null as number | null,
})

const emptyText = computed(() =>
  filters.q || filters.status || filters.priority || filters.owner_id
    ? '没有符合筛选条件的需求，试试调整筛选或清空关键词'
    : '暂无需求，点击右上角「新建需求」创建',
)

async function fetchList() {
  loading.value = true
  error.value = null
  try {
    const data = await api.get<PageResult<RequirementListItem>>(`/projects/${projectId}/requirements/`, {
      params: {
        page: page.value,
        page_size: pageSize.value,
        q: filters.q.trim() || undefined,
        status: filters.status || undefined,
        priority: filters.priority || undefined,
        owner_id: filters.owner_id ?? undefined,
      },
    })
    rows.value = data.items
    total.value = data.total
    fetchCoverages()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '需求加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

/** 逐行取覆盖率；单项失败静默留空 */
async function fetchCoverages() {
  const ids = rows.value.map((row) => row.id)
  const results = await Promise.allSettled(ids.map((id) => api.get<Coverage>(`/requirements/${id}/coverage/`)))
  const map: Record<number, Coverage> = {}
  results.forEach((result, index) => {
    if (result.status === 'fulfilled') {
      map[ids[index]] = result.value
    }
  })
  coverages.value = map
}

/** 覆盖率百分比（0-100 整数） */
function coveragePercent(coverage: Coverage | undefined): number {
  if (!coverage) return 0
  return Math.round((coverage.coverage || 0) * 100)
}

/** 进度条语义色：满覆盖 success，否则按风险给色 */
function coverageBarStatus(coverage: Coverage | undefined): '' | 'success' | 'exception' {
  if (!coverage) return ''
  if (coveragePercent(coverage) >= 100) return 'success'
  return coverage.risk_level === 'high' ? 'exception' : ''
}

/* ---------------- 筛选交互 ---------------- */
let searchTimer: ReturnType<typeof setTimeout> | null = null

function onSearchInput() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    fetchList()
  }, 300)
}

function flushSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  page.value = 1
  fetchList()
}

function onFilterChange() {
  page.value = 1
  fetchList()
}

function resetFilters() {
  filters.q = ''
  filters.status = ''
  filters.priority = ''
  filters.owner_id = null
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

function goDetail(row: RequirementListItem) {
  router.push({ name: 'requirement-detail', params: { projectId, reqId: row.id } })
}

/* ---------------- 负责人候选 ---------------- */
const users = ref<UserBrief[]>([])

async function fetchUsers() {
  try {
    const data = await api.get<PageResult<UserBrief>>('/users/', { params: { page_size: 100 } })
    users.value = data.items
  } catch {
    // 负责人下拉缺失不影响主流程，静默降级
  }
}

/* ---------------- 新建需求 ---------------- */
const createVisible = ref(false)
const creating = ref(false)
const createFormRef = ref<InstanceType<typeof RequirementForm>>()
const createForm = ref<RequirementFormModel>(defaultRequirementForm())

function openCreate() {
  createForm.value = defaultRequirementForm()
  createVisible.value = true
  createFormRef.value?.clearValidate()
  if (!users.value.length) fetchUsers()
}

async function submitCreate() {
  const form = createFormRef.value
  if (!form) return
  const valid = await form.validate().catch(() => false)
  if (!valid) return

  creating.value = true
  try {
    const created = await api.post<RequirementListItem>(`/projects/${projectId}/requirements/`, {
      title: createForm.value.title.trim(),
      description: createForm.value.description.trim(),
      status: createForm.value.status,
      priority: createForm.value.priority,
      owner_id: createForm.value.owner_id,
    })
    createVisible.value = false
    router.push({ name: 'requirement-detail', params: { projectId, reqId: created.id } })
  } catch (err) {
    notifyError(err)
  } finally {
    creating.value = false
  }
}

onMounted(() => {
  fetchList()
  fetchUsers()
})
</script>

<style scoped>
.page {
  padding: var(--sp-6);
}

.panel {
  background: var(--bg-surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
}

.filter-bar {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-3) var(--sp-4);
  border-bottom: 1px solid var(--border-light);
}

.filter-search {
  width: 280px;
}

.filter-select {
  width: 132px;
}

.req-table {
  width: 100%;
}

.req-table :deep(.el-table__row) {
  cursor: pointer;
}

.req-key {
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
  color: var(--text-secondary);
}

.req-title {
  font-weight: 500;
  color: var(--text-primary);
}

.coverage-cell {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.coverage-cell .el-progress {
  width: 64px;
}

.mono {
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
  color: var(--text-secondary);
  min-width: 34px;
  text-align: right;
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

.state-box {
  padding: var(--sp-10) var(--sp-6);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-3);
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
</style>
