<template>
  <section class="page">
    <PageHeader title="项目报告" subtitle="通过率 = 通过 / 已执行，未执行不计入分母">
      <template #actions>
        <el-button :loading="dashboardLoading || listLoading" @click="refreshAll">刷新数据</el-button>
      </template>
    </PageHeader>

    <!-- 项目统计错误态 -->
    <div v-if="dashboardError" class="state-panel">
      <p class="state-text">{{ dashboardError }}</p>
      <el-button size="small" @click="loadDashboard">重新加载</el-button>
    </div>

    <template v-else>
      <!-- 项目级统计（GET /projects/{id}/dashboard/） -->
      <div v-loading="dashboardLoading" class="stat-grid">
        <div v-for="card in statCards" :key="card.label" class="stat-card">
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-value">
            {{ card.value }}<span v-if="card.unit" class="stat-unit">{{ card.unit }}</span>
          </div>
          <div class="stat-note">{{ card.note }}</div>
        </div>
      </div>

      <div class="viz-grid">
        <!-- 执行结果分布 -->
        <section class="panel">
          <header class="panel-header">
            <h2 class="panel-title">执行结果分布</h2>
            <span class="panel-note">最近一次执行状态统计</span>
          </header>
          <div class="donut-wrap">
            <div class="donut-chart">
              <ChartBox
                :option="donutOption"
                :loading="dashboardLoading"
                height="200px"
                empty-text="暂无用例数据"
              />
              <div v-if="dashboard" class="donut-center">
                <span class="donut-center-label">用例总数</span>
                <span class="donut-center-value">{{ dashboard.total_cases }}</span>
              </div>
            </div>
            <ul v-if="dashboard" class="legend-list">
              <li v-for="item in resultLegend" :key="item.key" class="legend-row">
                <span class="legend-dot" :style="{ background: item.color }" />
                <span class="legend-name">{{ item.label }}</span>
                <span class="legend-value">{{ item.value }}</span>
                <span class="legend-percent">{{ item.percent }}</span>
              </li>
            </ul>
          </div>
        </section>

        <!-- 模块通过率（最近执行） -->
        <section class="panel">
          <header class="panel-header">
            <h2 class="panel-title">模块通过率</h2>
            <span class="panel-note">{{ moduleRunName || '最近一次执行' }}</span>
          </header>
          <div v-if="moduleError" class="panel-state">
            <p class="state-text">{{ moduleError }}</p>
            <el-button size="small" text type="primary" @click="loadModuleAnalysis">重试</el-button>
          </div>
          <div v-else v-loading="moduleLoading" class="module-list">
            <div v-for="row in moduleRows" :key="row.module_name" class="module-row">
              <div class="module-head">
                <span class="module-name">{{ row.module_name }}</span>
                <span class="module-rate">{{ formatPercent(row.pass_rate) }}</span>
              </div>
              <div class="progress-track">
                <div class="progress-fill" :style="{ width: percentWidth(row.pass_rate) }" />
              </div>
              <div class="module-note">通过 {{ row.passed }} / {{ row.total }}</div>
            </div>
            <div v-if="!moduleLoading && moduleRows.length === 0" class="panel-state">
              <p class="state-text">暂无执行数据，完成一轮测试执行后可查看模块统计</p>
            </div>
          </div>
        </section>

        <!-- 缺陷统计与需求覆盖率 -->
        <section class="panel">
          <header class="panel-header">
            <h2 class="panel-title">缺陷统计</h2>
            <span class="panel-note">共 {{ defectStats?.total ?? 0 }} 个</span>
          </header>
          <div v-if="dashboard" class="defect-body">
            <div class="defect-grid">
              <div class="defect-cell">
                <span class="defect-label">打开</span>
                <span class="defect-value">{{ defectStats?.open ?? 0 }}</span>
              </div>
              <div class="defect-cell">
                <span class="defect-label">处理中</span>
                <span class="defect-value">{{ defectStats?.in_progress ?? 0 }}</span>
              </div>
              <div class="defect-cell">
                <span class="defect-label">已修复</span>
                <span class="defect-value">{{ defectStats?.resolved ?? 0 }}</span>
              </div>
              <div class="defect-cell">
                <span class="defect-label">已关闭</span>
                <span class="defect-value">{{ defectStats?.closed ?? 0 }}</span>
              </div>
            </div>

            <ul class="severity-list">
              <li v-for="item in severityRows" :key="item.label" class="severity-row">
                <span class="severity-name">{{ item.label }}</span>
                <div class="progress-track slim">
                  <div class="progress-fill" :style="{ width: item.width }" />
                </div>
                <span class="severity-value">{{ item.value }}</span>
              </li>
              <li v-if="severityRows.length === 0" class="severity-empty">暂无缺陷记录</li>
            </ul>

            <div class="coverage-block">
              <div class="coverage-head">
                <span class="coverage-title">需求覆盖率</span>
                <span class="coverage-rate">{{ formatPercent(dashboard.requirement_coverage.rate) }}</span>
              </div>
              <div class="progress-track">
                <div
                  class="progress-fill"
                  :style="{ width: percentWidth(dashboard.requirement_coverage.rate) }"
                />
              </div>
              <div class="coverage-note">
                已覆盖 {{ dashboard.requirement_coverage.covered }} / {{ dashboard.requirement_coverage.total }} 条需求
              </div>
            </div>
          </div>
        </section>
      </div>

      <!-- 报告历史 -->
      <section class="panel history">
        <header class="panel-header">
          <h2 class="panel-title">报告历史</h2>
          <span class="panel-note">共 {{ listTotal }} 次测试执行</span>
        </header>

        <div v-if="listError" class="panel-state">
          <p class="state-text">{{ listError }}</p>
          <el-button size="small" text type="primary" @click="loadHistory">重试</el-button>
        </div>
        <div v-else v-loading="listLoading" class="history-list">
          <div
            v-for="row in historyRows"
            :key="row.run_id"
            class="history-row"
            role="button"
            @click="openReport(row.run_id)"
          >
            <div class="history-main">
              <div class="history-name">{{ row.name }}</div>
              <div class="history-meta">
                <StatusTag :tone="runStatusOf(row.status).tone" :label="runStatusOf(row.status).label" />
                <span class="meta-item">环境 {{ row.environment || '—' }}</span>
                <span class="meta-item">构建 {{ row.build_version || '—' }}</span>
                <span class="meta-item">开始 {{ formatTime(row.started_at) }}</span>
                <span class="meta-item">结束 {{ formatTime(row.finished_at) }}</span>
              </div>
            </div>

            <div class="history-stats">
              <div class="stacked-bar">
                <div class="stacked-seg seg-pass" :style="{ width: segWidth(row.passed, row.total) }" />
                <div class="stacked-seg seg-fail" :style="{ width: segWidth(row.failed, row.total) }" />
                <div class="stacked-seg seg-other" :style="{ width: segWidth(otherCount(row), row.total) }" />
                <div class="stacked-seg seg-notrun" :style="{ width: segWidth(row.not_run, row.total) }" />
              </div>
              <div class="history-counts">
                共 {{ row.total }} · 通过 {{ row.passed }} · 失败 {{ row.failed }} · 未执行 {{ row.not_run }}
              </div>
            </div>

            <div class="history-rate">
              <div class="rate-value">
                {{ percentNumber(row.pass_rate) }}<span class="rate-unit">%</span>
              </div>
              <div class="rate-label">通过率</div>
            </div>
          </div>

          <div v-if="!listLoading && historyRows.length === 0" class="panel-state">
            <p class="state-text">暂无执行报告，完成一轮测试执行后即可查看</p>
          </div>
        </div>

        <footer v-if="listTotal > pageSize" class="history-footer">
          <el-pagination
            background
            layout="total, prev, pager, next"
            :total="listTotal"
            :page-size="pageSize"
            :current-page="page"
            @current-change="onPageChange"
          />
        </footer>
      </section>
    </template>
  </section>
</template>

<script setup lang="ts">
/**
 * 项目报告中心（§36）
 * - 项目级统计：GET /projects/{id}/dashboard/（总体通过率 / 缺陷统计 / 需求覆盖率，口径以 dashboard 服务为准）
 * - 模块统计：取最近一次执行的 GET /runs/{id}/report/ 模块分析
 * - 报告历史：GET /projects/{id}/reports/（分页 run 摘要）
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, notifyError, type PageResult } from '@/api/client'
import PageHeader from '@/components/ui/PageHeader.vue'
import StatusTag from '@/components/ui/StatusTag.vue'
import ChartBox from './reports/ChartBox.vue'
import { donutOption as buildDonutOption, resultColor, type ChartOption, type ModuleRateRow } from './reports/chartTheme'
import {
  formatPercent,
  formatTime,
  percentWidth,
  runStatusOf,
  SEVERITY_LABELS,
} from './reports/reportShared'

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
}

/** GET /projects/{id}/reports/（RunReportSummarySerializer） */
interface RunSummary {
  run_id: number
  name: string
  status: string
  environment: string
  build_version: string
  started_at: string | null
  finished_at: string | null
  total: number
  passed: number
  failed: number
  not_run: number
  pass_rate: number
}

/** GET /runs/{id}/report/（build_run_report）子集 */
interface RunReportModulePart {
  name: string
  module_analysis: ModuleRateRow[]
}

const route = useRoute()
const router = useRouter()
const pageSize = 10

const dashboard = ref<DashboardData | null>(null)
const dashboardLoading = ref(false)
const dashboardError = ref('')

const historyRows = ref<RunSummary[]>([])
const listLoading = ref(false)
const listError = ref('')
const listTotal = ref(0)
const page = ref(1)

const moduleRows = ref<ModuleRateRow[]>([])
const moduleRunName = ref('')
const moduleLoading = ref(false)
const moduleError = ref('')

const defectStats = computed(() => dashboard.value?.defects ?? null)

/** 数据概览卡：总体通过率 / 执行进度 / 用例总数 / 未闭缺陷 / 需求覆盖率 */
const statCards = computed(() => {
  const data = dashboard.value
  if (!data) return []
  const exec = data.execution
  const unclosed = data.defects.total - data.defects.closed
  return [
    {
      label: '总体通过率',
      value: (exec.pass_rate * 100).toFixed(1),
      unit: '%',
      note: `通过 ${exec.passed} / 已执行 ${exec.executed}`,
    },
    {
      label: '执行进度',
      value: (exec.execution_rate * 100).toFixed(1),
      unit: '%',
      note: `已执行 ${exec.executed} / ${data.total_cases} · 未执行 ${exec.not_run}`,
    },
    {
      label: '用例总数',
      value: String(data.total_cases),
      unit: '',
      note: `失败 ${exec.failed} · 阻塞 ${exec.blocked} · 跳过 ${exec.skipped}`,
    },
    {
      label: '未闭缺陷',
      value: String(unclosed),
      unit: '',
      note: `打开 ${data.defects.open} · 处理中 ${data.defects.in_progress}`,
    },
    {
      label: '需求覆盖率',
      value: (data.requirement_coverage.rate * 100).toFixed(1),
      unit: '%',
      note: `已覆盖 ${data.requirement_coverage.covered} / ${data.requirement_coverage.total} 条需求`,
    },
  ]
})

/** 结果分布图例（与环形图同一套语义色） */
const resultLegend = computed(() => {
  const data = dashboard.value
  if (!data) return []
  const exec = data.execution
  const total = data.total_cases || 1
  const rows = [
    { key: 'passed', label: '通过', value: exec.passed },
    { key: 'failed', label: '失败', value: exec.failed },
    { key: 'blocked', label: '阻塞', value: exec.blocked },
    { key: 'skipped', label: '跳过', value: exec.skipped },
    { key: 'not_run', label: '未执行', value: exec.not_run },
  ]
  return rows.map((row) => ({
    ...row,
    color: resultColor(row.key),
    percent: `${((row.value / total) * 100).toFixed(1)}%`,
  }))
})

const donutOption = computed<ChartOption | null>(() => {
  const legend = resultLegend.value
  if (!dashboard.value || legend.length === 0) return null
  return buildDonutOption(
    legend.map((item) => ({ name: item.label, value: item.value, color: item.color })),
  )
})

/** 缺陷严重程度分布（宽度按占比） */
const severityRows = computed(() => {
  const bySeverity = defectStats.value?.by_severity ?? {}
  const entries = Object.entries(bySeverity).filter(([, value]) => value > 0)
  const max = Math.max(1, ...entries.map(([, value]) => value))
  return entries.map(([key, value]) => ({
    label: SEVERITY_LABELS[key] || key,
    value,
    width: `${((value / max) * 100).toFixed(1)}%`,
  }))
})

function percentNumber(value: number): string {
  return (value * 100).toFixed(1)
}

/** 堆叠条宽度：以本轮用例总数为分母 */
function segWidth(value: number, total: number): string {
  return `${((value / (total || 1)) * 100).toFixed(2)}%`
}

function otherCount(row: RunSummary): number {
  return row.total - row.passed - row.failed - row.not_run
}

function openReport(runId: number) {
  router.push({ name: 'run-report', params: { projectId: route.params.projectId, runId } })
}

async function loadDashboard() {
  dashboardLoading.value = true
  dashboardError.value = ''
  try {
    dashboard.value = await api.get<DashboardData>(`/projects/${route.params.projectId}/dashboard/`)
  } catch (e) {
    dashboard.value = null
    dashboardError.value = e instanceof Error ? e.message : '加载项目统计数据失败，请稍后重试'
    notifyError(e)
  } finally {
    dashboardLoading.value = false
  }
}

async function loadHistory() {
  listLoading.value = true
  listError.value = ''
  try {
    const data = await api.get<PageResult<RunSummary>>(`/projects/${route.params.projectId}/reports/`, {
      params: { page: page.value, page_size: pageSize },
    })
    historyRows.value = data.items
    listTotal.value = data.total
  } catch (e) {
    historyRows.value = []
    listTotal.value = 0
    listError.value = e instanceof Error ? e.message : '加载报告历史失败，请稍后重试'
  } finally {
    listLoading.value = false
  }
}

/** 模块统计：最近一次执行的模块分析 */
async function loadModuleAnalysis() {
  moduleLoading.value = true
  moduleError.value = ''
  try {
    const data = await api.get<PageResult<RunSummary>>(`/projects/${route.params.projectId}/reports/`, {
      params: { page: 1, page_size: 1 },
    })
    const latest = data.items[0]
    if (!latest) {
      moduleRows.value = []
      moduleRunName.value = ''
      return
    }
    const report = await api.get<RunReportModulePart>(`/runs/${latest.run_id}/report/`)
    moduleRows.value = report.module_analysis
    moduleRunName.value = `最近执行 · ${report.name}`
  } catch (e) {
    moduleRows.value = []
    moduleError.value = e instanceof Error ? e.message : '加载模块统计数据失败，请稍后重试'
  } finally {
    moduleLoading.value = false
  }
}

function onPageChange(value: number) {
  page.value = value
  loadHistory()
}

function refreshAll() {
  loadDashboard()
  loadHistory()
  loadModuleAnalysis()
}

onMounted(refreshAll)

// 项目切换后重新拉取
watch(
  () => route.params.projectId,
  (value, oldValue) => {
    if (value && value !== oldValue) {
      page.value = 1
      refreshAll()
    }
  },
)
</script>

<style scoped>
.page {
  padding: var(--sp-6);
}

/* ---------- 数据概览卡 ---------- */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: var(--sp-3);
  margin-bottom: var(--sp-4);
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

.stat-unit {
  margin-left: 2px;
  font-size: var(--fs-md);
  font-weight: 500;
  color: var(--text-tertiary);
}

.stat-note {
  margin-top: var(--sp-2);
  font-size: var(--fs-xs);
  color: var(--text-tertiary);
}

/* ---------- 可视化三栏 ---------- */
.viz-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--sp-3);
  margin-bottom: var(--sp-4);
  align-items: stretch;
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
  gap: var(--sp-2);
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
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  margin-bottom: var(--sp-4);
}

.state-text {
  margin: 0;
  color: var(--text-tertiary);
  font-size: var(--fs-base);
  text-align: center;
}

/* ---------- 结果分布环形图 ---------- */
.donut-wrap {
  display: flex;
  align-items: center;
  gap: var(--sp-4);
  padding: var(--sp-4);
}

.donut-chart {
  position: relative;
  flex: none;
  width: 200px;
}

.donut-center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  gap: 2px;
}

.donut-center-label {
  font-size: var(--fs-xs);
  color: var(--text-tertiary);
}

.donut-center-value {
  font-size: var(--fs-xl);
  font-weight: 600;
  color: var(--text-primary);
  line-height: var(--lh-tight);
  font-variant-numeric: tabular-nums;
}

.legend-list {
  flex: 1;
  margin: 0;
  padding: 0;
  list-style: none;
  min-width: 0;
}

.legend-row {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-1) 0;
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 2px;
  flex: none;
}

.legend-name {
  flex: 1;
  font-size: var(--fs-sm);
  color: var(--text-secondary);
}

.legend-value {
  font-size: var(--fs-base);
  font-weight: 600;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.legend-percent {
  width: 52px;
  text-align: right;
  font-size: var(--fs-sm);
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}

/* ---------- 模块通过率 ---------- */
.module-list {
  padding: var(--sp-4);
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
  min-height: 120px;
}

.module-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--sp-2);
  margin-bottom: var(--sp-1);
}

.module-name {
  font-size: var(--fs-sm);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.module-rate {
  font-size: var(--fs-base);
  font-weight: 600;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.module-note {
  margin-top: var(--sp-1);
  font-size: var(--fs-xs);
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}

/* ---------- 进度条 ---------- */
.progress-track {
  height: 6px;
  border-radius: var(--radius-pill);
  background: var(--bg-sunken);
  overflow: hidden;
}

.progress-track.slim {
  height: 4px;
}

.progress-fill {
  height: 100%;
  border-radius: var(--radius-pill);
  background: var(--accent-600);
  transition: width var(--dur-base) var(--ease-out);
}

/* ---------- 缺陷统计 ---------- */
.defect-body {
  padding: var(--sp-4);
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}

.defect-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--sp-2);
}

.defect-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.defect-label {
  font-size: var(--fs-xs);
  color: var(--text-tertiary);
}

.defect-value {
  font-size: var(--fs-xl);
  font-weight: 600;
  line-height: var(--lh-tight);
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.severity-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.severity-row {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.severity-name {
  flex: none;
  width: 40px;
  font-size: var(--fs-sm);
  color: var(--text-secondary);
}

.severity-row .progress-track {
  flex: 1;
}

.severity-value {
  flex: none;
  width: 24px;
  text-align: right;
  font-size: var(--fs-sm);
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.severity-empty {
  font-size: var(--fs-sm);
  color: var(--text-tertiary);
}

.coverage-block {
  border-top: 1px solid var(--border-light);
  padding-top: var(--sp-3);
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.coverage-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

.coverage-title {
  font-size: var(--fs-sm);
  color: var(--text-secondary);
}

.coverage-rate {
  font-size: var(--fs-lg);
  font-weight: 600;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.coverage-note {
  font-size: var(--fs-xs);
  color: var(--text-tertiary);
}

/* ---------- 报告历史 ---------- */
.history-list {
  min-height: 120px;
}

.history-row {
  display: flex;
  align-items: center;
  gap: var(--sp-6);
  padding: var(--sp-4);
  border-bottom: 1px solid var(--border-light);
  cursor: pointer;
  transition: background-color var(--dur-fast) var(--ease-out);
}

.history-row:last-child {
  border-bottom: none;
}

.history-row:hover {
  background: var(--bg-hover);
}

.history-main {
  flex: 1;
  min-width: 0;
}

.history-name {
  font-size: var(--fs-md);
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--sp-3);
  margin-top: var(--sp-2);
}

.meta-item {
  font-size: var(--fs-xs);
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}

.history-stats {
  flex: none;
  width: 260px;
}

.stacked-bar {
  display: flex;
  height: 6px;
  border-radius: var(--radius-pill);
  overflow: hidden;
  background: var(--bg-sunken);
}

.stacked-seg {
  height: 100%;
}

.seg-pass {
  background: var(--status-pass);
}

.seg-fail {
  background: var(--status-fail);
}

.seg-other {
  background: var(--status-block);
}

.seg-notrun {
  background: var(--ink-200);
}

.history-counts {
  margin-top: var(--sp-2);
  font-size: var(--fs-xs);
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}

.history-rate {
  flex: none;
  width: 88px;
  text-align: right;
}

.rate-value {
  font-size: var(--fs-xl);
  font-weight: 600;
  line-height: var(--lh-tight);
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.rate-unit {
  font-size: var(--fs-sm);
  font-weight: 500;
  color: var(--text-tertiary);
  margin-left: 1px;
}

.rate-label {
  margin-top: 2px;
  font-size: var(--fs-xs);
  color: var(--text-tertiary);
}

.history-footer {
  display: flex;
  justify-content: flex-end;
  padding: var(--sp-3) var(--sp-4);
  border-top: 1px solid var(--border-light);
}
</style>
