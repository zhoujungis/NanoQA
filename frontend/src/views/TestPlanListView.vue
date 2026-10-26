<template>
  <section class="page">
    <PageHeader title="测试计划" subtitle="组织用例集、分配人员并开启执行轮次">
      <template #actions>
        <el-button type="primary" @click="openCreate">新建计划</el-button>
      </template>
    </PageHeader>

    <div class="panel">
      <!-- 加载失败：错误态 + 重试 -->
      <div v-if="error" class="state-box">
        <p class="state-text">{{ error }}</p>
        <el-button size="small" @click="load">重新加载</el-button>
      </div>

      <template v-else>
        <el-table
          v-loading="loading"
          :data="plans"
          row-key="id"
          class="plan-table"
          @row-click="goDetail"
        >
          <el-table-column label="计划名称" min-width="240">
            <template #default="{ row }">
              <span class="plan-name">{{ row.name }}</span>
            </template>
          </el-table-column>
          <el-table-column label="版本" width="100">
            <template #default="{ row }">
              <span class="mono">{{ row.version || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <StatusTag :tone="planTone(row.status)" :label="planLabel(row.status)" />
            </template>
          </el-table-column>
          <el-table-column label="用例数" width="90" align="center">
            <template #default="{ row }">
              <span class="mono">{{ caseCounts[row.id] ?? '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="负责人" width="120">
            <template #default="{ row }">
              {{ row.owner_name || '—' }}
            </template>
          </el-table-column>
          <el-table-column label="计划时间" min-width="200">
            <template #default="{ row }">
              <span class="muted">{{ fmtTime(row.start_at) }} ~ {{ fmtTime(row.end_at) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="更新时间" width="150">
            <template #default="{ row }">
              <span class="muted">{{ fmtTime(row.updated_at) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="" width="90" align="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click.stop="goDetail(row)">详情</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-empty
          v-if="!loading && plans.length === 0"
          description="暂无测试计划，点击右上角「新建计划」创建"
        />

        <div v-if="total > 0" class="pager">
          <el-pagination
            :current-page="page"
            :page-size="pageSize"
            :total="total"
            layout="total, prev, pager, next"
            @current-change="onPageChange"
          />
        </div>
      </template>
    </div>

    <!-- 新建计划弹窗 -->
    <el-dialog v-model="createVisible" title="新建测试计划" width="540px" :close-on-click-modal="false">
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-width="80px">
        <el-form-item label="计划名称" prop="name">
          <el-input v-model="createForm.name" maxlength="128" placeholder="如：v1.0 回归测试" />
        </el-form-item>
        <el-form-item label="版本">
          <el-input v-model="createForm.version" maxlength="64" placeholder="如：1.0" />
        </el-form-item>
        <el-form-item label="测试范围">
          <el-input
            v-model="createForm.description"
            type="textarea"
            :rows="3"
            placeholder="描述本次测试的范围与目标"
          />
        </el-form-item>
        <el-form-item label="负责人">
          <el-select
            v-model="createForm.owner_id"
            placeholder="选择负责人"
            clearable
            filterable
            style="width: 100%"
          >
            <el-option v-for="u in users" :key="u.id" :label="u.display_name || u.username" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="开始时间">
          <el-date-picker
            v-model="createForm.start_at"
            type="datetime"
            placeholder="选择开始时间"
            value-format="YYYY-MM-DDTHH:mm:ssZ"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="结束时间">
          <el-date-picker
            v-model="createForm.end_at"
            type="datetime"
            placeholder="选择结束时间"
            value-format="YYYY-MM-DDTHH:mm:ssZ"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'
import { api, notifyError, type PageResult } from '@/api/client'
import PageHeader from '@/components/ui/PageHeader.vue'
import StatusTag from '@/components/ui/StatusTag.vue'

/** 测试计划（GET /projects/{id}/testplans/ 列表项） */
interface TestPlan {
  id: number
  name: string
  description: string
  version: string
  status: string
  start_at: string | null
  end_at: string | null
  owner_id: number | null
  owner_name: string | null
  created_at: string
  updated_at: string
}

/** 计划详情（GET /testplans/{id}/，含 cases 数组，仅取长度做用例数） */
interface TestPlanDetail extends TestPlan {
  cases?: { id: number }[]
}

interface UserBrief {
  id: number
  username: string
  display_name: string
}

type Tone = 'pass' | 'fail' | 'block' | 'skip' | 'warn' | 'info' | 'neutral' | 'accent'

/** 计划状态展示（未知值兜底原样展示） */
const PLAN_STATUS: Record<string, { label: string; tone: Tone }> = {
  draft: { label: '草稿', tone: 'neutral' },
  ready: { label: '就绪', tone: 'info' },
  running: { label: '执行中', tone: 'accent' },
  completed: { label: '已完成', tone: 'pass' },
  cancelled: { label: '已取消', tone: 'skip' },
  in_progress: { label: '进行中', tone: 'accent' },
}

function planLabel(status: string): string {
  return PLAN_STATUS[status]?.label ?? status
}

function planTone(status: string): Tone {
  return PLAN_STATUS[status]?.tone ?? 'neutral'
}

/** ISO 时间 → YYYY-MM-DD HH:mm */
function fmtTime(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.projectId)

const plans = ref<TestPlan[]>([])
const caseCounts = ref<Record<number, number>>({})
const loading = ref(false)
const error = ref('')
const page = ref(1)
const pageSize = 20
const total = ref(0)

const users = ref<UserBrief[]>([])
const createVisible = ref(false)
const creating = ref(false)
const createFormRef = ref<FormInstance>()

const createForm = reactive({
  name: '',
  version: '',
  description: '',
  owner_id: null as number | null,
  start_at: '' as string,
  end_at: '' as string,
})

const createRules: FormRules = {
  name: [{ required: true, message: '请输入计划名称', trigger: 'blur' }],
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await api.get<PageResult<TestPlan>>(`/projects/${projectId}/testplans/`, {
      params: { page: page.value, page_size: pageSize },
    })
    plans.value = data.items
    total.value = data.total
    loadCaseCounts()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载测试计划失败'
  } finally {
    loading.value = false
  }
}

/** 用例数需逐个取详情统计（列表接口不返回），失败不阻塞列表 */
async function loadCaseCounts() {
  const ids = plans.value.map((p) => p.id)
  const results = await Promise.allSettled(ids.map((id) => api.get<TestPlanDetail>(`/testplans/${id}/`)))
  const map: Record<number, number> = {}
  results.forEach((result, index) => {
    if (result.status === 'fulfilled') {
      map[ids[index]] = result.value.cases?.length ?? 0
    }
  })
  caseCounts.value = map
}

async function loadUsers() {
  try {
    const data = await api.get<PageResult<UserBrief>>('/users/', { params: { page_size: 100 } })
    users.value = data.items
  } catch (e) {
    notifyError(e)
  }
}

function onPageChange(value: number) {
  page.value = value
  load()
}

function goDetail(row: TestPlan) {
  router.push({ name: 'testplan-detail', params: { projectId, planId: row.id } })
}

function openCreate() {
  createForm.name = ''
  createForm.version = ''
  createForm.description = ''
  createForm.owner_id = null
  createForm.start_at = ''
  createForm.end_at = ''
  createVisible.value = true
  createFormRef.value?.clearValidate()
  if (users.value.length === 0) loadUsers()
}

async function submitCreate() {
  const formEl = createFormRef.value
  if (!formEl) return
  const valid = await formEl.validate().catch(() => false)
  if (!valid) return

  creating.value = true
  try {
    const created = await api.post<TestPlan>(`/projects/${projectId}/testplans/`, {
      name: createForm.name.trim(),
      version: createForm.version.trim(),
      description: createForm.description.trim(),
      owner_id: createForm.owner_id,
      start_at: createForm.start_at || null,
      end_at: createForm.end_at || null,
    })
    createVisible.value = false
    router.push({ name: 'testplan-detail', params: { projectId, planId: created.id } })
  } catch (e) {
    notifyError(e)
  } finally {
    creating.value = false
  }
}

onMounted(load)
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

.plan-table {
  width: 100%;
}

.plan-table :deep(.el-table__row) {
  cursor: pointer;
}

.plan-name {
  font-weight: 500;
  color: var(--text-primary);
}

.mono {
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
}

.muted {
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
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

.pager {
  display: flex;
  justify-content: flex-end;
  padding: var(--sp-3) var(--sp-4);
  border-top: 1px solid var(--border-light);
}
</style>
