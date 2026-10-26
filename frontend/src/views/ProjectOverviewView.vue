<template>
  <section class="page">
    <PageHeader title="项目概览" subtitle="通过率 = 通过 / 已执行，未执行不计入分母">
      <template #actions>
        <el-button :loading="dashboardLoading" @click="loadDashboard">刷新数据</el-button>
      </template>
    </PageHeader>

    <!-- 仪表盘错误态 -->
    <div v-if="dashboardError" class="state-panel">
      <p class="state-text">{{ dashboardError }}</p>
      <el-button size="small" @click="loadDashboard">重新加载</el-button>
    </div>

    <template v-else>
      <!-- 数据概览卡 -->
      <div v-loading="dashboardLoading" class="stat-grid">
        <div v-for="card in statCards" :key="card.label" class="stat-card">
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-value">{{ card.value }}</div>
          <div class="stat-note">{{ card.note }}</div>
        </div>
      </div>

      <div class="panel-grid">
        <!-- 最近操作 -->
        <section class="panel">
          <header class="panel-header">
            <h2 class="panel-title">最近操作</h2>
            <router-link class="panel-link" :to="{ name: 'audit', params: routeParams }">全部日志</router-link>
          </header>

          <div v-if="auditError" class="panel-state">
            <p class="state-text">{{ auditError }}</p>
            <el-button size="small" text type="primary" @click="loadAudit">重试</el-button>
          </div>
          <div v-else v-loading="auditLoading" class="audit-list">
            <div v-for="item in auditItems" :key="item.id" class="audit-row">
              <StatusTag :tone="actionTone(item.action)" :label="actionLabel(item.action)" />
              <span class="audit-ref">{{ objectLabel(item) }}</span>
              <span class="audit-user">{{ item.display_name || item.username || '系统' }}</span>
              <span class="audit-time">{{ formatTime(item.created_at) }}</span>
            </div>
            <div v-if="!auditLoading && auditItems.length === 0" class="panel-state">
              <p class="state-text">暂无操作记录</p>
            </div>
          </div>
        </section>

        <!-- 常用快捷入口 -->
        <section class="panel">
          <header class="panel-header">
            <h2 class="panel-title">快捷入口</h2>
          </header>
          <div class="quick-list">
            <router-link
              v-for="entry in quickEntries"
              :key="entry.name"
              class="quick-row"
              :to="{ name: entry.name, params: routeParams }"
            >
              <span class="quick-text">
                <span class="quick-title">{{ entry.title }}</span>
                <span class="quick-desc">{{ entry.desc }}</span>
              </span>
              <el-icon class="quick-arrow"><ArrowRight /></el-icon>
            </router-link>
          </div>
        </section>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowRight } from '@element-plus/icons-vue'
import { api, notifyError, type PageResult } from '@/api/client'
import PageHeader from '@/components/ui/PageHeader.vue'
import StatusTag from '@/components/ui/StatusTag.vue'

/** GET /projects/{id}/dashboard/（apps/reports/services/dashboard.py） */
interface DashboardData {
  total_cases: number
  cases_by_status: Record<string, number>
  cases_by_priority: Record<string, number>
  execution: {
    executed: number
    not_run: number
    passed: number
    failed: number
    blocked: number
    skipped: number
    execution_rate: number
    pass_rate: number
    failure_rate: number
    block_rate: number
  }
  defects: {
    total: number
    open: number
    in_progress: number
    resolved: number
    closed: number
    by_severity: Record<string, number>
  }
  requirement_coverage: { total: number; covered: number; rate: number }
  recent_plans: { name: string; status: string; updated_at: string }[]
  recent_failures: { case_key: string; title: string; executed_at: string | null }[]
}

/** GET /projects/{id}/audit-logs/（AuditLogSerializer） */
interface AuditItem {
  id: number
  action: string
  object_type: string
  object_id: number | null
  object_ref: string
  display_name: string | null
  username: string | null
  created_at: string
}

interface StatCard {
  label: string
  value: string
  note: string
}

const route = useRoute()

const dashboard = ref<DashboardData | null>(null)
const dashboardLoading = ref(false)
const dashboardError = ref('')
const auditItems = ref<AuditItem[]>([])
const auditLoading = ref(false)
const auditError = ref('')

const routeParams = computed(() => ({ projectId: route.params.projectId }))

const quickEntries = [
  { name: 'testcases', title: '测试用例', desc: '编写与维护用例、组织模块树' },
  { name: 'runs', title: '测试执行', desc: '按计划执行用例、记录结果' },
  { name: 'defects', title: '缺陷', desc: '跟踪失败用例关联的问题' },
  { name: 'reports', title: '测试报告', desc: '查看执行报告与质量趋势' },
]

const ACTION_LABELS: Record<string, string> = {
  create: '创建',
  update: '更新',
  delete: '删除',
  transition: '状态流转',
  execute: '执行',
  import: '导入',
  export: '导出',
  link: '关联',
  unlink: '取消关联',
}

const ACTION_TONES: Record<string, 'pass' | 'fail' | 'warn' | 'accent' | 'neutral'> = {
  create: 'pass',
  update: 'accent',
  delete: 'fail',
  transition: 'warn',
  execute: 'accent',
}

const OBJECT_LABELS: Record<string, string> = {
  project: '项目',
  module: '模块',
  tag: '标签',
  projectmember: '项目成员',
  organization: '组织',
  organizationmember: '组织成员',
  user: '用户',
  role: '角色',
  requirement: '需求',
  requirementtestcase: '需求-用例关联',
  requirementdefect: '需求-缺陷关联',
  testcase: '测试用例',
  testcaseversion: '用例版本',
  testcasetag: '用例标签',
  testplan: '测试计划',
  testplancase: '计划用例',
  testrun: '测试执行',
  testresult: '执行结果',
  defect: '缺陷',
  testcasedefect: '用例-缺陷关联',
  testresultdefect: '结果-缺陷关联',
  aitask: 'AI 任务',
  attachment: '附件',
  auditlog: '操作日志',
}

function actionLabel(action: string): string {
  return ACTION_LABELS[action] || action
}

function actionTone(action: string): 'pass' | 'fail' | 'warn' | 'accent' | 'neutral' {
  return ACTION_TONES[action] || 'neutral'
}

function objectLabel(item: AuditItem): string {
  const type = OBJECT_LABELS[item.object_type] || item.object_type
  return item.object_ref ? `${type} · ${item.object_ref}` : type
}

function formatTime(value: string): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

/** 概览卡：用例总数 / 执行进度 / 通过率 / 失败用例 / 未闭缺陷 / 需求覆盖率 */
const statCards = computed<StatCard[]>(() => {
  const data = dashboard.value
  if (!data) return []
  const exec = data.execution
  const defects = data.defects
  const unclosed = defects.total - defects.closed
  return [
    {
      label: '用例总数',
      value: String(data.total_cases),
      note: `活跃 ${data.cases_by_status['active'] || 0} · 草稿 ${data.cases_by_status['draft'] || 0}`,
    },
    {
      label: '执行进度',
      value: formatPercent(exec.execution_rate),
      note: `已执行 ${exec.executed} / ${data.total_cases} · 未执行 ${exec.not_run}`,
    },
    {
      label: '通过率',
      value: formatPercent(exec.pass_rate),
      note: `通过 ${exec.passed} / 已执行 ${exec.executed}`,
    },
    {
      label: '失败用例',
      value: String(exec.failed),
      note: `失败率 ${formatPercent(exec.failure_rate)} · 阻塞 ${exec.blocked}`,
    },
    {
      label: '未闭缺陷',
      value: String(unclosed),
      note: `待处理 ${defects.open} · 处理中 ${defects.in_progress}`,
    },
    {
      label: '需求覆盖率',
      value: formatPercent(data.requirement_coverage.rate),
      note: `已覆盖 ${data.requirement_coverage.covered} / ${data.requirement_coverage.total} 条需求`,
    },
  ]
})

async function loadDashboard() {
  dashboardLoading.value = true
  dashboardError.value = ''
  try {
    dashboard.value = await api.get<DashboardData>(`/projects/${route.params.projectId}/dashboard/`)
  } catch (e) {
    dashboard.value = null
    dashboardError.value = e instanceof Error ? e.message : '加载概览数据失败，请稍后重试'
    notifyError(e)
  } finally {
    dashboardLoading.value = false
  }
}

async function loadAudit() {
  auditLoading.value = true
  auditError.value = ''
  try {
    const data = await api.get<PageResult<AuditItem>>(`/projects/${route.params.projectId}/audit-logs/`, {
      params: { page_size: 10 },
    })
    auditItems.value = data.items
  } catch (e) {
    auditItems.value = []
    auditError.value = e instanceof Error ? e.message : '加载操作记录失败，请稍后重试'
  } finally {
    auditLoading.value = false
  }
}

function loadAll() {
  loadDashboard()
  loadAudit()
}

onMounted(loadAll)
// 项目切换后重新拉取当前项目数据
watch(
  () => route.params.projectId,
  (value, oldValue) => {
    if (value && value !== oldValue) loadAll()
  },
)
</script>

<style scoped>
.page {
  padding: var(--sp-6);
}

/* ---------- 概览卡 ---------- */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: var(--sp-3);
  margin-bottom: var(--sp-5);
}

.stat-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  padding: var(--sp-4) var(--sp-4) var(--sp-3);
  min-height: 96px;
}

.stat-label {
  font-size: var(--fs-sm);
  color: var(--text-tertiary);
}

.stat-value {
  margin-top: var(--sp-1);
  font-size: var(--fs-2xl);
  font-weight: 600;
  line-height: var(--lh-tight);
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.stat-note {
  margin-top: var(--sp-2);
  font-size: var(--fs-xs);
  color: var(--text-tertiary);
}

/* ---------- 面板区 ---------- */
.panel-grid {
  display: grid;
  grid-template-columns: 3fr 2fr;
  gap: var(--sp-3);
  align-items: start;
}

.panel {
  background: var(--bg-surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--sp-3) var(--sp-4);
  border-bottom: 1px solid var(--border-light);
}

.panel-title {
  margin: 0;
  font-size: var(--fs-md);
  font-weight: 600;
  color: var(--text-primary);
}

.panel-link {
  font-size: var(--fs-sm);
  color: var(--accent-600);
  text-decoration: none;
}

.panel-link:hover {
  color: var(--accent-700);
}

/* ---------- 最近操作 ---------- */
.audit-list {
  min-height: 120px;
}

.audit-row {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-2) var(--sp-4);
  border-bottom: 1px solid var(--border-light);
}

.audit-row:last-child {
  border-bottom: none;
}

.audit-ref {
  flex: 1;
  min-width: 0;
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.audit-user {
  flex: none;
  font-size: var(--fs-sm);
  color: var(--text-secondary);
}

.audit-time {
  flex: none;
  font-size: var(--fs-xs);
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}

.panel-state {
  padding: var(--sp-8) var(--sp-4);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-2);
}

.state-panel {
  padding: var(--sp-10) var(--sp-6);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-3);
  background: var(--bg-surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
}

.state-text {
  margin: 0;
  color: var(--text-tertiary);
  font-size: var(--fs-base);
}

/* ---------- 快捷入口 ---------- */
.quick-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  padding: var(--sp-3) var(--sp-4);
  border-bottom: 1px solid var(--border-light);
  text-decoration: none;
  transition: background-color var(--dur-fast) var(--ease-out);
}

.quick-row:last-child {
  border-bottom: none;
}

.quick-row:hover {
  background: var(--bg-hover);
}

.quick-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.quick-title {
  font-size: var(--fs-base);
  font-weight: 500;
  color: var(--text-primary);
}

.quick-desc {
  font-size: var(--fs-xs);
  color: var(--text-tertiary);
}

.quick-arrow {
  flex: none;
  color: var(--text-placeholder);
}

.quick-row:hover .quick-arrow {
  color: var(--accent-600);
}
</style>
