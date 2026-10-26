<template>
  <section class="page">
    <PageHeader :title="plan?.name || '测试计划'" :subtitle="subtitle">
      <template #actions>
        <el-button @click="router.push({ name: 'testplans', params: { projectId } })">返回列表</el-button>
        <el-button :disabled="!plan" @click="openEdit">编辑</el-button>
        <el-button type="primary" :disabled="!plan" @click="openStart">开始执行</el-button>
      </template>
    </PageHeader>

    <!-- 加载失败：错误态 + 重试 -->
    <div v-if="error" class="panel state-box">
      <p class="state-text">{{ error }}</p>
      <el-button size="small" @click="load">重新加载</el-button>
    </div>

    <template v-else>
      <!-- 计划信息 -->
      <div v-loading="loading" class="panel info-panel">
        <div class="panel-title">计划信息</div>
        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">状态</span>
            <StatusTag :tone="planTone(plan?.status)" :label="planLabel(plan?.status)" />
          </div>
          <div class="info-item">
            <span class="info-label">版本</span>
            <span class="mono">{{ plan?.version || '—' }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">负责人</span>
            <span>{{ plan?.owner_name || '—' }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">创建人</span>
            <span>{{ plan?.created_by_name || '—' }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">开始时间</span>
            <span>{{ fmtTime(plan?.start_at ?? null) }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">结束时间</span>
            <span>{{ fmtTime(plan?.end_at ?? null) }}</span>
          </div>
          <div class="info-item info-item-wide">
            <span class="info-label">测试范围</span>
            <span class="info-desc">{{ plan?.description || '—' }}</span>
          </div>
        </div>
      </div>

      <!-- 计划用例集 -->
      <div class="panel">
        <div class="panel-head">
          <div class="panel-title">计划用例<span class="count">共 {{ planCases.length }} 条</span></div>
          <el-button size="small" type="primary" plain @click="openAddCases">添加用例</el-button>
        </div>
        <el-table v-loading="loading" :data="planCases" row-key="test_case">
          <el-table-column label="用例 Key" width="150">
            <template #default="{ row }">
              <span class="mono accent">{{ row.case_key }}</span>
            </template>
          </el-table-column>
          <el-table-column label="标题" min-width="260" show-overflow-tooltip>
            <template #default="{ row }">{{ row.title }}</template>
          </el-table-column>
          <el-table-column label="模块" width="110">
            <template #default="{ row }">
              <span class="muted">{{ row.module_name || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="优先级" width="90">
            <template #default="{ row }">
              <span class="mono">{{ row.priority || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="分配人" width="170">
            <template #default="{ row }">
              <el-select
                :model-value="row.assigned_to"
                size="small"
                placeholder="未分配"
                clearable
                filterable
                :loading="usersLoading"
                @change="assignCase(row, $event)"
              >
                <el-option v-for="u in users" :key="u.id" :label="u.display_name || u.username" :value="u.id" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="执行状态" width="110">
            <template #default="{ row }">
              <StatusTag :tone="resultTone(row.execution_status)" :label="resultLabel(row.execution_status)" />
            </template>
          </el-table-column>
          <el-table-column label="" width="80" align="right">
            <template #default="{ row }">
              <el-button link type="danger" size="small" @click="removeCase(row)">移除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!loading && planCases.length === 0" description="尚未添加用例，点击「添加用例」开始组织计划" />
      </div>

      <!-- 历史执行轮次 -->
      <div class="panel">
        <div class="panel-head">
          <div class="panel-title">执行轮次<span class="count">共 {{ runs.length }} 轮</span></div>
        </div>
        <el-table v-loading="runsLoading" :data="runs" row-key="id">
          <el-table-column label="名称" min-width="220">
            <template #default="{ row }">
              <span class="run-name" @click="goRun(row)">{{ row.name }}</span>
            </template>
          </el-table-column>
          <el-table-column label="环境" width="110">
            <template #default="{ row }">{{ row.environment || '—' }}</template>
          </el-table-column>
          <el-table-column label="构建版本" width="110">
            <template #default="{ row }">
              <span class="mono">{{ row.build_version || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <StatusTag :tone="runTone(row.status)" :label="runLabel(row.status)" />
            </template>
          </el-table-column>
          <el-table-column label="通过率" width="140">
            <template #default="{ row }">
              <div v-if="reportMap[row.id]" class="rate-cell">
                <el-progress
                  :percentage="Math.round((reportMap[row.id]?.pass_rate ?? 0) * 100)"
                  :stroke-width="4"
                  :show-text="false"
                  class="rate-bar"
                />
                <span class="mono rate-text">{{ Math.round((reportMap[row.id]?.pass_rate ?? 0) * 100) }}%</span>
              </div>
              <span v-else class="muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="开始时间" width="150">
            <template #default="{ row }">
              <span class="muted">{{ fmtTime(row.started_at) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="" width="130" align="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="goRun(row)">执行</el-button>
              <el-button link size="small" @click="goReport(row)">报告</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!runsLoading && runs.length === 0" description="暂无执行轮次，点击上方「开始执行」开启第一轮" />
      </div>
    </template>

    <!-- 编辑计划弹窗 -->
    <el-dialog v-model="editVisible" title="编辑测试计划" width="540px" :close-on-click-modal="false">
      <el-form ref="editFormRef" :model="editForm" :rules="editRules" label-width="80px">
        <el-form-item label="计划名称" prop="name">
          <el-input v-model="editForm.name" maxlength="128" />
        </el-form-item>
        <el-form-item label="版本">
          <el-input v-model="editForm.version" maxlength="64" />
        </el-form-item>
        <el-form-item label="测试范围">
          <el-input v-model="editForm.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="editForm.status" style="width: 100%">
            <el-option v-for="option in statusOptions" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="负责人">
          <el-select v-model="editForm.owner_id" clearable filterable placeholder="选择负责人" style="width: 100%">
            <el-option v-for="u in users" :key="u.id" :label="u.display_name || u.username" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="开始时间">
          <el-date-picker
            v-model="editForm.start_at"
            type="datetime"
            value-format="YYYY-MM-DDTHH:mm:ssZ"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="结束时间">
          <el-date-picker
            v-model="editForm.end_at"
            type="datetime"
            value-format="YYYY-MM-DDTHH:mm:ssZ"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 添加用例弹窗 -->
    <el-dialog v-model="addVisible" title="添加用例到计划" width="680px" :close-on-click-modal="false">
      <div class="add-toolbar">
        <el-input
          v-model="addKeyword"
          placeholder="按 Key / 标题筛选"
          clearable
          size="small"
          class="add-search"
        />
        <span class="muted">已选 {{ selectedCaseIds.length }} 条</span>
      </div>
      <el-table
        ref="addTableRef"
        v-loading="addLoading"
        :data="filteredCases"
        row-key="id"
        max-height="380"
        @selection-change="onSelectionChange"
      >
        <el-table-column type="selection" width="46" :selectable="canSelect" />
        <el-table-column label="用例 Key" width="150">
          <template #default="{ row }">
            <span class="mono">{{ row.case_key }}</span>
          </template>
        </el-table-column>
        <el-table-column label="标题" min-width="240" show-overflow-tooltip>
          <template #default="{ row }">{{ row.title }}</template>
        </el-table-column>
        <el-table-column label="优先级" width="80">
          <template #default="{ row }">
            <span class="mono">{{ row.priority }}</span>
          </template>
        </el-table-column>
        <el-table-column label="模块" width="100">
          <template #default="{ row }">
            <span class="muted">{{ row.module_name || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <span class="muted">{{ row.status === 'active' ? '生效' : row.status }}</span>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!addLoading && filteredCases.length === 0" description="没有可添加的用例" />
      <template #footer>
        <el-button @click="addVisible = false">取消</el-button>
        <el-button type="primary" :loading="adding" :disabled="selectedCaseIds.length === 0" @click="submitAddCases">
          加入计划
        </el-button>
      </template>
    </el-dialog>

    <!-- 开始执行弹窗 -->
    <el-dialog v-model="startVisible" title="开始执行" width="480px" :close-on-click-modal="false">
      <el-form label-width="90px">
        <el-form-item label="轮次名称">
          <el-input v-model="startForm.name" maxlength="128" placeholder="留空自动按计划名与时间生成" />
        </el-form-item>
        <el-form-item label="测试环境">
          <el-input v-model="startForm.environment" maxlength="64" placeholder="如：Staging" />
        </el-form-item>
        <el-form-item label="构建版本">
          <el-input v-model="startForm.build_version" maxlength="64" placeholder="如：1.0.0" />
        </el-form-item>
      </el-form>
      <p class="dialog-note">将为计划内 {{ planCases.length }} 条用例预建执行结果，并按当前用例版本生成快照。</p>
      <template #footer>
        <el-button @click="startVisible = false">取消</el-button>
        <el-button type="primary" :loading="starting" @click="submitStart">开始执行</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { api, notifyError, type PageResult } from '@/api/client'
import PageHeader from '@/components/ui/PageHeader.vue'
import StatusTag from '@/components/ui/StatusTag.vue'

/** 计划用例（GET /testplans/{id}/ cases 项） */
interface PlanCase {
  id: number
  test_case: number
  case_key: string
  title: string
  module_name: string | null
  priority: string
  assigned_to: number | null
  assigned_to_name: string | null
  execution_status: string
}

interface TestPlanDetail {
  id: number
  name: string
  description: string
  version: string
  status: string
  start_at: string | null
  end_at: string | null
  owner_id: number | null
  owner_name: string | null
  created_by_name: string | null
  created_at: string
  updated_at: string
  cases: PlanCase[]
}

/** 执行轮次（GET /testplans/{id}/runs/ 列表项） */
interface TestRun {
  id: number
  name: string
  environment: string
  build_version: string
  status: string
  started_at: string | null
  finished_at: string | null
  created_at: string
}

/** run 摘要（GET /projects/{id}/reports/），仅取通过率 */
interface RunReportSummary {
  run_id: number
  pass_rate: number
  total: number
  passed: number
  failed: number
  not_run: number
}

interface UserBrief {
  id: number
  username: string
  display_name: string
}

/** 项目用例（GET /projects/{id}/testcases/ 列表项，选入计划用） */
interface ProjectCase {
  id: number
  case_key: string
  title: string
  priority: string
  module_name: string | null
  status: string
}

type Tone = 'pass' | 'fail' | 'block' | 'skip' | 'warn' | 'info' | 'neutral' | 'accent'

const PLAN_STATUS: Record<string, { label: string; tone: Tone }> = {
  draft: { label: '草稿', tone: 'neutral' },
  ready: { label: '就绪', tone: 'info' },
  running: { label: '执行中', tone: 'accent' },
  completed: { label: '已完成', tone: 'pass' },
  cancelled: { label: '已取消', tone: 'skip' },
  in_progress: { label: '进行中', tone: 'accent' },
}

const RESULT_STATUS: Record<string, { label: string; tone: Tone }> = {
  not_run: { label: '未执行', tone: 'neutral' },
  passed: { label: '通过', tone: 'pass' },
  failed: { label: '失败', tone: 'fail' },
  blocked: { label: '阻塞', tone: 'block' },
  skipped: { label: '跳过', tone: 'skip' },
}

const RUN_STATUS: Record<string, { label: string; tone: Tone }> = {
  created: { label: '已创建', tone: 'info' },
  running: { label: '执行中', tone: 'accent' },
  finished: { label: '已完成', tone: 'pass' },
  cancelled: { label: '已取消', tone: 'skip' },
}

function planLabel(status?: string): string {
  return (status && PLAN_STATUS[status]?.label) || status || '—'
}
function planTone(status?: string): Tone {
  return (status && PLAN_STATUS[status]?.tone) || 'neutral'
}
function resultLabel(status: string): string {
  return RESULT_STATUS[status]?.label ?? status
}
function resultTone(status: string): Tone {
  return RESULT_STATUS[status]?.tone ?? 'neutral'
}
function runLabel(status: string): string {
  return RUN_STATUS[status]?.label ?? status
}
function runTone(status: string): Tone {
  return RUN_STATUS[status]?.tone ?? 'neutral'
}

function fmtTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

/** ISO 时间 → 日期选择器 value-format（去掉微秒） */
function toPickerValue(iso: string | null): string {
  return iso ? iso.replace(/\.\d+/, '') : ''
}

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.projectId)
const planId = Number(route.params.planId)

const plan = ref<TestPlanDetail | null>(null)
const loading = ref(false)
const error = ref('')
const runs = ref<TestRun[]>([])
const runsLoading = ref(false)
const reportMap = ref<Record<number, RunReportSummary>>({})
const users = ref<UserBrief[]>([])
const usersLoading = ref(false)

const planCases = computed(() => plan.value?.cases ?? [])

const subtitle = computed(() => {
  if (!plan.value) return ''
  return `版本 ${plan.value.version || '—'} · 创建人 ${plan.value.created_by_name || '—'} · 更新于 ${fmtTime(plan.value.updated_at)}`
})

/** 状态下拉：保留未知的当前状态，避免编辑时被吞掉 */
const statusOptions = computed(() => {
  const base = [
    { value: 'draft', label: '草稿' },
    { value: 'ready', label: '就绪' },
    { value: 'running', label: '执行中' },
    { value: 'completed', label: '已完成' },
    { value: 'cancelled', label: '已取消' },
  ]
  const current = plan.value?.status
  if (current && !base.some((item) => item.value === current)) {
    return [{ value: current, label: planLabel(current) }, ...base]
  }
  return base
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    plan.value = await api.get<TestPlanDetail>(`/testplans/${planId}/`)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载测试计划失败'
  } finally {
    loading.value = false
  }
}

async function loadRuns() {
  runsLoading.value = true
  try {
    const data = await api.get<PageResult<TestRun>>(`/testplans/${planId}/runs/`, {
      params: { page_size: 100 },
    })
    runs.value = data.items
    loadReportRates()
  } catch (e) {
    notifyError(e)
  } finally {
    runsLoading.value = false
  }
}

/** 通过率来自报告摘要接口，一次拉全项目 run 摘要做映射 */
async function loadReportRates() {
  try {
    const data = await api.get<PageResult<RunReportSummary>>(`/projects/${projectId}/reports/`, {
      params: { page_size: 100 },
    })
    const map: Record<number, RunReportSummary> = {}
    data.items.forEach((item) => {
      map[item.run_id] = item
    })
    reportMap.value = map
  } catch {
    // 通过率是辅助信息，失败不打扰
  }
}

async function loadUsers() {
  if (usersLoading.value || users.value.length > 0) return
  usersLoading.value = true
  try {
    const data = await api.get<PageResult<UserBrief>>('/users/', { params: { page_size: 100 } })
    users.value = data.items
  } catch (e) {
    notifyError(e)
  } finally {
    usersLoading.value = false
  }
}

function goRun(row: TestRun) {
  router.push({ name: 'run-execution', params: { projectId, runId: row.id } })
}

function goReport(row: TestRun) {
  router.push({ name: 'run-report', params: { projectId, runId: row.id } })
}

/* ---------- 编辑计划（乐观锁 updated_at） ---------- */
const editVisible = ref(false)
const saving = ref(false)
const editFormRef = ref<FormInstance>()

const editForm = reactive({
  name: '',
  version: '',
  description: '',
  status: 'draft',
  owner_id: null as number | null,
  start_at: '',
  end_at: '',
})

const editRules: FormRules = {
  name: [{ required: true, message: '请输入计划名称', trigger: 'blur' }],
}

function openEdit() {
  if (!plan.value) return
  editForm.name = plan.value.name
  editForm.version = plan.value.version
  editForm.description = plan.value.description
  editForm.status = plan.value.status
  editForm.owner_id = plan.value.owner_id
  editForm.start_at = toPickerValue(plan.value.start_at)
  editForm.end_at = toPickerValue(plan.value.end_at)
  editVisible.value = true
  editFormRef.value?.clearValidate()
  loadUsers()
}

async function submitEdit() {
  const formEl = editFormRef.value
  if (!formEl || !plan.value) return
  const valid = await formEl.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    plan.value = await api.patch<TestPlanDetail>(`/testplans/${planId}/`, {
      name: editForm.name.trim(),
      version: editForm.version.trim(),
      description: editForm.description.trim(),
      status: editForm.status,
      owner_id: editForm.owner_id,
      start_at: editForm.start_at || null,
      end_at: editForm.end_at || null,
      // 乐观锁：原样回传 updated_at，冲突时 client 层弹统一提示
      updated_at: plan.value.updated_at,
    })
    editVisible.value = false
    ElMessage.success('计划已更新')
  } catch (e) {
    notifyError(e)
  } finally {
    saving.value = false
  }
}

/* ---------- 计划用例：分配 / 移除 / 添加 ---------- */
async function assignCase(row: PlanCase, value: number | null) {
  try {
    await api.patch(`/testplans/${planId}/cases/${row.test_case}/`, { assigned_to: value })
    row.assigned_to = value
    row.assigned_to_name = users.value.find((u) => u.id === value)?.display_name ?? null
    ElMessage.success('分配人已更新')
  } catch (e) {
    notifyError(e)
    load()
  }
}

async function removeCase(row: PlanCase) {
  try {
    await ElMessageBox.confirm(`确认将「${row.case_key}」移出该计划？`, '移除用例', {
      type: 'warning',
      confirmButtonText: '移除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await api.delete(`/testplans/${planId}/cases/${row.test_case}/`)
    ElMessage.success('已移出计划')
    load()
  } catch (e) {
    notifyError(e)
  }
}

const addVisible = ref(false)
const addLoading = ref(false)
const adding = ref(false)
const addKeyword = ref('')
const allCases = ref<ProjectCase[]>([])
const selectedCaseIds = ref<number[]>([])

const filteredCases = computed(() => {
  const keyword = addKeyword.value.trim().toLowerCase()
  if (!keyword) return allCases.value
  return allCases.value.filter(
    (item) =>
      item.case_key.toLowerCase().includes(keyword) || item.title.toLowerCase().includes(keyword),
  )
})

const existingCaseIds = computed(() => new Set(planCases.value.map((item) => item.test_case)))

function canSelect(row: ProjectCase): boolean {
  return !existingCaseIds.value.has(row.id)
}

function onSelectionChange(rows: ProjectCase[]) {
  selectedCaseIds.value = rows.map((row) => row.id)
}

async function openAddCases() {
  addVisible.value = true
  addKeyword.value = ''
  selectedCaseIds.value = []
  addLoading.value = true
  try {
    const data = await api.get<PageResult<ProjectCase>>(`/projects/${projectId}/testcases/`, {
      params: { page_size: 100 },
    })
    allCases.value = data.items
  } catch (e) {
    notifyError(e)
  } finally {
    addLoading.value = false
  }
}

async function submitAddCases() {
  if (selectedCaseIds.value.length === 0) return
  adding.value = true
  try {
    const result = await api.post<{ added: number[]; skipped: number[] }>(
      `/testplans/${planId}/cases/`,
      { test_case_ids: selectedCaseIds.value },
    )
    addVisible.value = false
    ElMessage.success(`已加入 ${result.added.length} 条用例${result.skipped.length ? `，跳过 ${result.skipped.length} 条已存在用例` : ''}`)
    load()
  } catch (e) {
    notifyError(e)
  } finally {
    adding.value = false
  }
}

/* ---------- 开始执行 ---------- */
const startVisible = ref(false)
const starting = ref(false)

const startForm = reactive({
  name: '',
  environment: '',
  build_version: '',
})

function openStart() {
  startForm.name = ''
  startForm.environment = ''
  startForm.build_version = ''
  startVisible.value = true
}

async function submitStart() {
  starting.value = true
  try {
    const run = await api.post<TestRun>(`/testplans/${planId}/start/`, {
      name: startForm.name.trim(),
      environment: startForm.environment.trim(),
      build_version: startForm.build_version.trim(),
    })
    startVisible.value = false
    ElMessage.success('执行轮次已创建')
    router.push({ name: 'run-execution', params: { projectId, runId: run.id } })
  } catch (e) {
    notifyError(e)
  } finally {
    starting.value = false
  }
}

onMounted(() => {
  load()
  loadRuns()
  loadUsers()
})
</script>

<style scoped>
.page {
  padding: var(--sp-6);
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}

.panel {
  background: var(--bg-surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  padding: var(--sp-3) var(--sp-4);
  border-bottom: 1px solid var(--border-light);
}

.panel-title {
  padding: var(--sp-3) var(--sp-4);
  font-size: var(--fs-md);
  font-weight: 600;
  color: var(--text-primary);
}

.panel-head .panel-title {
  padding: 0;
}

.count {
  margin-left: var(--sp-2);
  font-size: var(--fs-sm);
  font-weight: 400;
  color: var(--text-tertiary);
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--sp-3) var(--sp-6);
  padding: 0 var(--sp-4) var(--sp-4);
}

.info-item {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  font-size: var(--fs-base);
  color: var(--text-primary);
}

.info-item-wide {
  grid-column: 1 / -1;
  align-items: flex-start;
}

.info-label {
  flex: none;
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
}

.info-desc {
  white-space: pre-wrap;
  color: var(--text-secondary);
  line-height: var(--lh-base);
}

.mono {
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
}

.accent {
  color: var(--accent-600);
}

.muted {
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
}

.run-name {
  cursor: pointer;
  font-weight: 500;
  color: var(--text-primary);
}

.run-name:hover {
  color: var(--accent-600);
}

.rate-cell {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.rate-bar {
  flex: 1;
  min-width: 60px;
}

.rate-text {
  width: 38px;
  text-align: right;
  color: var(--text-secondary);
}

.state-box {
  padding: var(--sp-10);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-3);
}

.state-text {
  margin: 0;
  color: var(--text-tertiary);
}

.add-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  margin-bottom: var(--sp-3);
}

.add-search {
  width: 240px;
}

.dialog-note {
  margin: 0;
  font-size: var(--fs-sm);
  color: var(--text-tertiary);
}
</style>
