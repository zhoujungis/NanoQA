<template>
  <section class="page">
    <PageHeader title="工作台" :subtitle="greeting">
      <template #actions>
        <el-button :loading="loading" @click="loadAll">刷新</el-button>
        <el-button type="primary" @click="goProjects">创建项目</el-button>
      </template>
    </PageHeader>

    <!-- 错误态 -->
    <div v-if="error" class="state-panel">
      <p class="state-text">{{ error }}</p>
      <el-button size="small" @click="loadAll">重新加载</el-button>
    </div>

    <template v-else>
      <!-- 我的项目 -->
      <div class="section-head">
        <h2 class="section-title">我的项目</h2>
        <router-link class="section-link" to="/projects">全部项目</router-link>
      </div>

      <div v-loading="loading" class="project-grid">
        <article v-for="project in projects" :key="project.id" class="project-card">
          <header class="project-head">
            <span class="project-key">{{ project.key }}</span>
            <StatusTag
              v-if="project.status !== 'active'"
              tone="neutral"
              :label="project.status === 'archived' ? '已归档' : project.status"
            />
            <StatusTag v-else-if="project.role" tone="accent" :label="project.role" />
          </header>

          <router-link
            class="project-name"
            :to="{ name: 'project-overview', params: { projectId: project.id } }"
          >
            {{ project.name }}
          </router-link>
          <p class="project-desc">{{ project.description || '暂无项目简介' }}</p>

          <!-- 概要卡：来自 GET /projects/{id}/dashboard/ -->
          <div v-if="summaries[project.id]" class="project-stats">
            <div class="mini-stat">
              <span class="mini-label">用例</span>
              <span class="mini-value">{{ summaries[project.id]!.total_cases }}</span>
            </div>
            <div class="mini-stat">
              <span class="mini-label">执行进度</span>
              <span class="mini-value">{{ formatPercent(summaries[project.id]!.execution.execution_rate) }}</span>
            </div>
            <div class="mini-stat">
              <span class="mini-label">通过率</span>
              <span class="mini-value">{{ formatPercent(summaries[project.id]!.execution.pass_rate) }}</span>
            </div>
            <div class="mini-stat">
              <span class="mini-label">未闭缺陷</span>
              <span class="mini-value">{{ unclosedDefects(summaries[project.id]!) }}</span>
            </div>
          </div>
          <div v-else-if="summaryLoading" class="project-stats">
            <div v-for="i in 4" :key="i" class="mini-stat">
              <span class="mini-label">加载中</span>
              <span class="mini-value mini-skeleton" />
            </div>
          </div>
          <div v-else class="project-stats-empty">概要数据加载失败</div>

          <footer class="project-foot">
            <router-link
              class="enter-link"
              :to="{ name: 'project-overview', params: { projectId: project.id } }"
            >
              进入项目
              <el-icon><ArrowRight /></el-icon>
            </router-link>
          </footer>
        </article>

        <!-- 空态 -->
        <div v-if="!loading && projects.length === 0" class="empty-card">
          <p class="state-text">暂无可见项目</p>
          <el-button type="primary" size="small" @click="goProjects">创建项目</el-button>
        </div>
      </div>

      <div class="lower-grid">
        <!-- 最近动态 -->
        <section class="panel">
          <header class="panel-header">
            <h2 class="panel-title">最近动态</h2>
            <span class="panel-note">近 {{ activities.length }} 条操作记录</span>
          </header>

          <div v-if="activityError" class="panel-state">
            <p class="state-text">{{ activityError }}</p>
            <el-button size="small" text type="primary" @click="loadActivities">重试</el-button>
          </div>
          <div v-else v-loading="activityLoading" class="activity-list">
            <div v-for="item in activities" :key="item.id" class="activity-row">
              <StatusTag :tone="actionTone(item.action)" :label="actionLabel(item.action)" />
              <span class="activity-ref">{{ item.object_ref || item.object_type }}</span>
              <span class="activity-project">{{ item.project_key }}</span>
              <span class="activity-user">{{ item.display_name || item.username || '系统' }}</span>
              <span class="activity-time">{{ formatTime(item.created_at) }}</span>
            </div>
            <div v-if="!activityLoading && activities.length === 0" class="panel-state">
              <p class="state-text">暂无操作记录</p>
            </div>
          </div>
        </section>

        <!-- 快捷入口 -->
        <section class="panel">
          <header class="panel-header">
            <h2 class="panel-title">快捷入口</h2>
          </header>
          <div class="quick-list">
            <router-link class="quick-row" to="/projects">
              <span class="quick-text">
                <span class="quick-title">项目列表</span>
                <span class="quick-desc">查看全部项目、搜索与筛选</span>
              </span>
              <el-icon class="quick-arrow"><ArrowRight /></el-icon>
            </router-link>
            <router-link class="quick-row" to="/projects">
              <span class="quick-text">
                <span class="quick-title">创建项目</span>
                <span class="quick-desc">新建测试项目并配置成员</span>
              </span>
              <el-icon class="quick-arrow"><ArrowRight /></el-icon>
            </router-link>
            <router-link
              v-for="project in projects.slice(0, 3)"
              :key="`quick-${project.id}`"
              class="quick-row"
              :to="{ name: 'project-overview', params: { projectId: project.id } }"
            >
              <span class="quick-text">
                <span class="quick-title">{{ project.name }}</span>
                <span class="quick-desc">{{ project.key }} · 项目概览</span>
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
/**
 * 个人工作台（全局页）
 * 数据来源（全部为现有接口）：
 * - GET /projects/                  项目列表（分页）
 * - GET /projects/{id}/dashboard/   项目概要（并发取前若干个项目）
 * - GET /projects/{id}/audit-logs/  最近动态（并发取前若干个项目后按时间归并）
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight } from '@element-plus/icons-vue'
import { api, notifyError, type PageResult } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import PageHeader from '@/components/ui/PageHeader.vue'
import StatusTag from '@/components/ui/StatusTag.vue'

/** GET /projects/（ProjectSerializer） */
interface ProjectItem {
  id: number
  name: string
  key: string
  description: string
  status: string
  role: string | null
}

/** GET /projects/{id}/dashboard/（apps/reports/services/dashboard.py）子集 */
interface DashboardSummary {
  total_cases: number
  execution: {
    executed: number
    not_run: number
    passed: number
    failed: number
    execution_rate: number
    pass_rate: number
  }
  defects: { total: number; closed: number }
}

/** GET /projects/{id}/audit-logs/（AuditLogSerializer） */
interface AuditItem {
  id: number
  action: string
  object_type: string
  object_ref: string
  display_name: string | null
  username: string | null
  created_at: string
}

interface ActivityRow extends AuditItem {
  project_key: string
}

/** 概要卡并发取前 6 个项目，动态归并前 3 个项目 */
const SUMMARY_LIMIT = 6
const ACTIVITY_LIMIT = 3

const router = useRouter()
const auth = useAuthStore()

const projects = ref<ProjectItem[]>([])
const summaries = ref<Record<number, DashboardSummary>>({})
const activities = ref<ActivityRow[]>([])
const loading = ref(false)
const summaryLoading = ref(false)
const activityLoading = ref(false)
const activityError = ref('')
const error = ref('')

const greeting = computed(() => {
  const name = auth.user?.display_name || auth.user?.username || '你好'
  return `${name}，欢迎回来 · 这里是你的项目概览与最近动态`
})

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

function actionLabel(action: string): string {
  return ACTION_LABELS[action] || action
}

function actionTone(action: string): 'pass' | 'fail' | 'warn' | 'accent' | 'neutral' {
  return ACTION_TONES[action] || 'neutral'
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

function unclosedDefects(summary: DashboardSummary): number {
  return summary.defects.total - summary.defects.closed
}

function goProjects() {
  router.push('/projects')
}

/** 项目列表 */
async function loadProjects() {
  loading.value = true
  error.value = ''
  try {
    const data = await api.get<PageResult<ProjectItem>>('/projects/', { params: { page_size: 20 } })
    projects.value = data.items
    loadSummaries()
    loadActivities()
  } catch (e) {
    projects.value = []
    error.value = e instanceof Error ? e.message : '加载项目列表失败，请稍后重试'
    notifyError(e)
  } finally {
    loading.value = false
  }
}

/** 概要卡：并发取前若干个项目的 dashboard */
async function loadSummaries() {
  const targets = projects.value.slice(0, SUMMARY_LIMIT)
  if (targets.length === 0) {
    summaries.value = {}
    return
  }
  summaryLoading.value = true
  try {
    const results = await Promise.allSettled(
      targets.map((project) => api.get<DashboardSummary>(`/projects/${project.id}/dashboard/`)),
    )
    const map: Record<number, DashboardSummary> = {}
    results.forEach((result, index) => {
      if (result.status === 'fulfilled') map[targets[index].id] = result.value
    })
    summaries.value = map
  } finally {
    summaryLoading.value = false
  }
}

/** 最近动态：并发取前若干个项目的审计日志后按时间倒序归并 */
async function loadActivities() {
  const targets = projects.value.slice(0, ACTIVITY_LIMIT)
  if (targets.length === 0) {
    activities.value = []
    return
  }
  activityLoading.value = true
  activityError.value = ''
  try {
    const results = await Promise.allSettled(
      targets.map((project) =>
        api
          .get<PageResult<AuditItem>>(`/projects/${project.id}/audit-logs/`, { params: { page_size: 5 } })
          .then((data) => data.items.map((item) => ({ ...item, project_key: project.key }))),
      ),
    )
    const merged: ActivityRow[] = []
    for (const result of results) {
      if (result.status === 'fulfilled') merged.push(...result.value)
    }
    merged.sort((a, b) => (a.created_at < b.created_at ? 1 : -1))
    activities.value = merged.slice(0, 6)
  } catch (e) {
    activities.value = []
    activityError.value = e instanceof Error ? e.message : '加载操作记录失败，请稍后重试'
  } finally {
    activityLoading.value = false
  }
}

function loadAll() {
  loadProjects()
}

onMounted(loadAll)
</script>

<style scoped>
.page {
  padding: var(--sp-6);
}

/* ---------- 区块标题 ---------- */
.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: var(--sp-3);
}

.section-title {
  margin: 0;
  font-size: var(--fs-lg);
  font-weight: 600;
  color: var(--text-primary);
}

.section-link {
  font-size: var(--fs-sm);
  color: var(--accent-600);
  text-decoration: none;
}

.section-link:hover {
  color: var(--accent-700);
}

/* ---------- 项目卡 ---------- */
.project-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--sp-3);
  min-height: 180px;
  margin-bottom: var(--sp-6);
}

.project-card {
  display: flex;
  flex-direction: column;
  background: var(--bg-surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  padding: var(--sp-4);
  transition: box-shadow var(--dur-fast) var(--ease-out), border-color var(--dur-fast) var(--ease-out);
}

.project-card:hover {
  border-color: var(--border-default);
  box-shadow: var(--shadow-md);
}

.project-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
}

.project-key {
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
  letter-spacing: 0.06em;
  color: var(--accent-600);
  background: var(--accent-50);
  border-radius: var(--radius-sm);
  padding: 1px 6px;
}

.project-name {
  margin-top: var(--sp-2);
  font-size: var(--fs-md);
  font-weight: 600;
  color: var(--text-primary);
  text-decoration: none;
}

.project-name:hover {
  color: var(--accent-600);
}

.project-desc {
  margin: var(--sp-1) 0 var(--sp-3);
  font-size: var(--fs-sm);
  color: var(--text-tertiary);
  min-height: 32px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.project-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--sp-2);
  padding: var(--sp-3) 0;
  border-top: 1px solid var(--border-light);
}

.mini-stat {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.mini-label {
  font-size: var(--fs-xs);
  color: var(--text-tertiary);
}

.mini-value {
  font-size: var(--fs-lg);
  font-weight: 600;
  line-height: var(--lh-tight);
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.mini-skeleton {
  display: inline-block;
  width: 36px;
  height: 18px;
  border-radius: var(--radius-sm);
  background: var(--bg-sunken);
}

.project-stats-empty {
  padding: var(--sp-3) 0;
  border-top: 1px solid var(--border-light);
  font-size: var(--fs-sm);
  color: var(--text-tertiary);
}

.project-foot {
  margin-top: auto;
  padding-top: var(--sp-3);
  border-top: 1px solid var(--border-light);
}

.enter-link {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-1);
  font-size: var(--fs-sm);
  font-weight: 500;
  color: var(--accent-600);
  text-decoration: none;
}

.enter-link:hover {
  color: var(--accent-700);
}

.empty-card {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-10) var(--sp-6);
  background: var(--bg-surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
}

/* ---------- 下部双栏 ---------- */
.lower-grid {
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

.panel-note {
  font-size: var(--fs-xs);
  color: var(--text-tertiary);
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

/* ---------- 最近动态 ---------- */
.activity-list {
  min-height: 120px;
}

.activity-row {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-2) var(--sp-4);
  border-bottom: 1px solid var(--border-light);
}

.activity-row:last-child {
  border-bottom: none;
}

.activity-ref {
  flex: 1;
  min-width: 0;
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.activity-project {
  flex: none;
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
  color: var(--text-tertiary);
  background: var(--bg-sunken);
  border-radius: var(--radius-sm);
  padding: 0 6px;
}

.activity-user {
  flex: none;
  font-size: var(--fs-sm);
  color: var(--text-secondary);
}

.activity-time {
  flex: none;
  font-size: var(--fs-xs);
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
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
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
