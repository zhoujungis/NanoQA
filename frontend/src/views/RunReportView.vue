<template>
  <section class="page">
    <PageHeader :title="report?.name || '测试执行报告'" subtitle="通过率 = 通过 / 已执行，未执行不计入分母">
      <template #actions>
        <el-button @click="goBack">返回报告列表</el-button>
        <el-button :loading="reportLoading" @click="loadAll">刷新数据</el-button>
        <el-button plain @click="printReport">打印</el-button>
      </template>
    </PageHeader>

    <!-- 错误态 -->
    <div v-if="reportError" class="state-panel">
      <p class="state-text">{{ reportError }}</p>
      <el-button size="small" @click="loadAll">重新加载</el-button>
    </div>

    <template v-else>
      <!-- 报告头：环境 / 构建 / 时间 / 执行人 -->
      <div v-loading="reportLoading" class="meta-strip">
        <div class="meta-cell">
          <span class="meta-label">状态</span>
          <StatusTag :tone="runStatusOf(report?.status || '').tone" :label="runStatusOf(report?.status || '').label" />
        </div>
        <div class="meta-cell">
          <span class="meta-label">环境</span>
          <span class="meta-value">{{ report?.environment || '—' }}</span>
        </div>
        <div class="meta-cell">
          <span class="meta-label">构建版本</span>
          <span class="meta-value mono">{{ report?.build_version || '—' }}</span>
        </div>
        <div class="meta-cell">
          <span class="meta-label">开始时间</span>
          <span class="meta-value">{{ formatTime(report?.started_at) }}</span>
        </div>
        <div class="meta-cell">
          <span class="meta-label">结束时间</span>
          <span class="meta-value">{{ formatTime(report?.finished_at) }}</span>
        </div>
        <div class="meta-cell">
          <span class="meta-label">执行人</span>
          <span class="meta-value">{{ runDetail?.created_by_name || '—' }}</span>
        </div>
      </div>

      <!-- 总览（§36） -->
      <div v-loading="reportLoading" class="stat-grid">
        <div v-for="card in statCards" :key="card.label" class="stat-card">
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-value">
            {{ card.value }}<span v-if="card.unit" class="stat-unit">{{ card.unit }}</span>
          </div>
          <div class="stat-note">{{ card.note }}</div>
        </div>
      </div>

      <!-- 图表区 -->
      <div class="viz-grid">
        <section class="panel">
          <header class="panel-header">
            <h2 class="panel-title">结果分布</h2>
            <span class="panel-note">本轮全部用例</span>
          </header>
          <div class="donut-wrap">
            <div class="donut-chart">
              <ChartBox
                :option="donutOption"
                :loading="reportLoading"
                height="220px"
                empty-text="暂无执行结果"
              />
              <div v-if="report" class="donut-center">
                <span class="donut-center-label">用例总数</span>
                <span class="donut-center-value">{{ overview.total }}</span>
              </div>
            </div>
            <ul v-if="report" class="legend-list">
              <li v-for="item in resultLegend" :key="item.key" class="legend-row">
                <span class="legend-dot" :style="{ background: item.color }" />
                <span class="legend-name">{{ item.label }}</span>
                <span class="legend-value">{{ item.value }}</span>
                <span class="legend-percent">{{ item.percent }}</span>
              </li>
            </ul>
          </div>
        </section>

        <section class="panel">
          <header class="panel-header">
            <h2 class="panel-title">模块通过率</h2>
            <span class="panel-note">按模块统计已执行用例</span>
          </header>
          <div class="module-chart">
            <ChartBox
              :option="moduleOption"
              :loading="reportLoading"
              height="280px"
              empty-text="暂无模块统计数据"
            />
          </div>
        </section>
      </div>

      <!-- 模块分析 -->
      <section class="panel block">
        <header class="panel-header">
          <h2 class="panel-title">模块分析</h2>
          <span class="panel-note">共 {{ report?.module_analysis.length ?? 0 }} 个模块</span>
        </header>
        <table v-if="report && report.module_analysis.length" class="report-table">
          <thead>
            <tr>
              <th class="col-name">模块</th>
              <th class="col-num">用例数</th>
              <th class="col-num">通过</th>
              <th class="col-rate">通过率</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in report.module_analysis" :key="row.module_name">
              <td class="col-name">{{ row.module_name }}</td>
              <td class="col-num">{{ row.total }}</td>
              <td class="col-num">{{ row.passed }}</td>
              <td class="col-rate">
                <div class="rate-cell">
                  <div class="progress-track">
                    <div class="progress-fill" :style="{ width: percentWidth(row.pass_rate) }" />
                  </div>
                  <span class="rate-text">{{ formatPercent(row.pass_rate) }}</span>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-else-if="!reportLoading" class="panel-state">
          <p class="state-text">暂无模块统计数据</p>
        </div>
      </section>

      <!-- 失败用例清单（§95） -->
      <section class="panel block">
        <header class="panel-header">
          <h2 class="panel-title">失败用例</h2>
          <span class="panel-note">共 {{ report?.failed_cases.length ?? 0 }} 条</span>
        </header>
        <table v-if="report && report.failed_cases.length" class="report-table">
          <thead>
            <tr>
              <th class="col-key">用例 ID</th>
              <th class="col-name">标题</th>
              <th class="col-mod">模块</th>
              <th class="col-user">执行人</th>
              <th class="col-time">最近执行时间</th>
              <th class="col-bug">关联缺陷</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in report.failed_cases" :key="item.result_id">
              <td class="col-key mono">{{ item.case_key }}</td>
              <td class="col-name">{{ item.title }}</td>
              <td class="col-mod">{{ item.module }}</td>
              <td class="col-user">{{ item.executor || '—' }}</td>
              <td class="col-time">{{ formatTime(item.executed_at) }}</td>
              <td class="col-bug">
                <div v-if="item.defects.length" class="bug-list">
                  <StatusTag
                    v-for="bug in item.defects"
                    :key="bug.key"
                    :tone="defectTone(bug.status)"
                  >
                    {{ bug.key }} · {{ DEFECT_STATUS_LABELS[bug.status] || bug.status }}
                  </StatusTag>
                </div>
                <span v-else class="cell-muted">未关联</span>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-else-if="!reportLoading" class="panel-state">
          <p class="state-text">本轮无失败用例</p>
        </div>
      </section>

      <!-- Bug 统计（§95） -->
      <section class="panel block">
        <header class="panel-header">
          <h2 class="panel-title">缺陷统计</h2>
          <span class="panel-note">关联本轮执行结果的缺陷 · 共 {{ defectStats?.total ?? 0 }} 个</span>
        </header>
        <div v-if="report" class="defect-body">
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
            <li v-if="severityRows.length === 0" class="severity-empty">本轮未关联缺陷</li>
          </ul>
        </div>
      </section>
    </template>
  </section>
</template>

<script setup lang="ts">
/**
 * 单次执行报告（§36 / §95 报告验收项）
 * 数据来源（全部为现有接口）：
 * - GET /runs/{id}/report/  报告聚合（总览 / 模块分析 / 失败用例 / 缺陷统计）
 * - GET /runs/{id}/         执行人（created_by_name）
 * 注：run 报告不含需求覆盖率，项目级需求覆盖率见项目报告页。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, notifyError } from '@/api/client'
import PageHeader from '@/components/ui/PageHeader.vue'
import StatusTag from '@/components/ui/StatusTag.vue'
import ChartBox from './reports/ChartBox.vue'
import {
  donutOption as buildDonutOption,
  moduleBarOption,
  resultColor,
  type ChartOption,
  type ModuleRateRow,
} from './reports/chartTheme'
import {
  DEFECT_STATUS_LABELS,
  formatPercent,
  formatTime,
  percentWidth,
  RESULT_LABELS,
  runStatusOf,
  SEVERITY_LABELS,
  type Tone,
} from './reports/reportShared'

/** GET /runs/{id}/report/（apps/reports/services/run_report.py） */
interface RunReport {
  run_id: number
  name: string
  status: string
  overview: {
    total: number
    passed: number
    failed: number
    blocked: number
    skipped: number
    pass_rate: number
  }
  module_analysis: (ModuleRateRow & { module_id: number | null })[]
  failed_cases: {
    result_id: number
    case_key: string
    title: string
    module: string
    executor: string
    executed_at: string | null
    defects: { key: string; title: string; status: string }[]
  }[]
  defect_stats: {
    total: number
    open: number
    in_progress: number
    resolved: number
    closed: number
    by_severity: Record<string, number>
  }
  started_at: string | null
  finished_at: string | null
  environment: string
  build_version: string
}

/** GET /runs/{id}/（TestRunSerializer）子集 */
interface RunDetail {
  project: number
  created_by_name: string | null
}

const route = useRoute()
const router = useRouter()

const report = ref<RunReport | null>(null)
const runDetail = ref<RunDetail | null>(null)
const reportLoading = ref(false)
const reportError = ref('')

const overview = computed(() => report.value?.overview ?? {
  total: 0,
  passed: 0,
  failed: 0,
  blocked: 0,
  skipped: 0,
  pass_rate: 0,
})

const defectStats = computed(() => report.value?.defect_stats ?? null)

/** 未执行 = 总数 - 有结果的用例（与后端 not_run 口径一致，本地推导） */
const notRun = computed(() => {
  const o = overview.value
  return Math.max(0, o.total - o.passed - o.failed - o.blocked - o.skipped)
})

/** 总览卡（§36） */
const statCards = computed(() => {
  const o = overview.value
  const executed = o.total - notRun.value
  return [
    { label: '用例总数', value: String(o.total), unit: '', note: `已执行 ${executed} · 未执行 ${notRun.value}` },
    { label: '通过', value: String(o.passed), unit: '', note: `占已执行 ${formatPercent(executed ? o.passed / executed : 0)}` },
    { label: '失败', value: String(o.failed), unit: '', note: '详见下方失败用例清单' },
    { label: '阻塞', value: String(o.blocked), unit: '', note: '受阻未完成的用例' },
    { label: '跳过', value: String(o.skipped), unit: '', note: '本轮主动跳过' },
    { label: '总体通过率', value: (o.pass_rate * 100).toFixed(1), unit: '%', note: '通过 / 已执行，未执行不计入' },
  ]
})

/** 结果分布图例（与环形图同一套语义色） */
const resultLegend = computed(() => {
  const o = overview.value
  const total = o.total || 1
  const rows: { key: string; label: string; value: number }[] = [
    { key: 'passed', label: RESULT_LABELS.passed, value: o.passed },
    { key: 'failed', label: RESULT_LABELS.failed, value: o.failed },
    { key: 'blocked', label: RESULT_LABELS.blocked, value: o.blocked },
    { key: 'skipped', label: RESULT_LABELS.skipped, value: o.skipped },
    { key: 'not_run', label: RESULT_LABELS.not_run, value: notRun.value },
  ]
  return rows.map((row) => ({
    ...row,
    color: resultColor(row.key),
    percent: `${((row.value / total) * 100).toFixed(1)}%`,
  }))
})

const donutOption = computed<ChartOption | null>(() => {
  const legend = resultLegend.value
  if (!report.value || legend.length === 0) return null
  return buildDonutOption(
    legend.map((item) => ({ name: item.label, value: item.value, color: item.color })),
  )
})

const moduleOption = computed<ChartOption | null>(() => {
  const rows = report.value?.module_analysis ?? []
  if (rows.length === 0) return null
  return moduleBarOption(rows)
})

/** 缺陷严重程度分布 */
const severityRows = computed(() => {
  const entries = Object.entries(defectStats.value?.by_severity ?? {}).filter(([, value]) => value > 0)
  const max = Math.max(1, ...entries.map(([, value]) => value))
  return entries.map(([key, value]) => ({
    label: SEVERITY_LABELS[key] || key,
    value,
    width: `${((value / max) * 100).toFixed(1)}%`,
  }))
})

const DEFECT_TONES: Record<string, Tone> = {
  Open: 'warn',
  'In Progress': 'accent',
  Resolved: 'pass',
  Reopened: 'fail',
  Closed: 'neutral',
  Rejected: 'skip',
  Duplicate: 'skip',
}

function defectTone(status: string): Tone {
  return DEFECT_TONES[status] ?? 'neutral'
}

function goBack() {
  router.push({ name: 'reports', params: { projectId: route.params.projectId } })
}

function printReport() {
  window.print()
}

async function loadAll() {
  reportLoading.value = true
  reportError.value = ''
  try {
    const [reportData, runData] = await Promise.all([
      api.get<RunReport>(`/runs/${route.params.runId}/report/`),
      api.get<RunDetail>(`/runs/${route.params.runId}/`).catch(() => null),
    ])
    // URL 中的 projectId 与 Run 实际归属不一致时（手工输入错误 URL），拒绝渲染
    if (runData && runData.project !== Number(route.params.projectId)) {
      reportError.value = '该执行轮次不属于当前项目'
      return
    }
    report.value = reportData
    runDetail.value = runData
  } catch (e) {
    report.value = null
    runDetail.value = null
    reportError.value = e instanceof Error ? e.message : '加载执行报告失败，请稍后重试'
    notifyError(e)
  } finally {
    reportLoading.value = false
  }
}

onMounted(loadAll)

// 切换执行后重新拉取
watch(
  () => route.params.runId,
  (value, oldValue) => {
    if (value && value !== oldValue) loadAll()
  },
)
</script>

<style scoped>
.page {
  padding: var(--sp-6);
}

/* ---------- 报告头 ---------- */
.meta-strip {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--sp-8);
  background: var(--bg-surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  padding: var(--sp-4) var(--sp-5);
  margin-bottom: var(--sp-4);
  min-height: 64px;
}

.meta-cell {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}

.meta-label {
  font-size: var(--fs-xs);
  color: var(--text-tertiary);
}

.meta-value {
  font-size: var(--fs-base);
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.mono {
  font-family: var(--font-mono);
}

/* ---------- 总览卡 ---------- */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
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

/* ---------- 图表区 ---------- */
.viz-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--sp-3);
  margin-bottom: var(--sp-4);
}

.panel {
  background: var(--bg-surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}

.panel.block {
  margin-bottom: var(--sp-4);
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

/* ---------- 结果分布 ---------- */
.donut-wrap {
  display: flex;
  align-items: center;
  gap: var(--sp-5);
  padding: var(--sp-5);
}

.donut-chart {
  position: relative;
  flex: none;
  width: 220px;
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

.module-chart {
  padding: var(--sp-4);
}

/* ---------- 表格 ---------- */
.report-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--fs-base);
}

.report-table th {
  text-align: left;
  padding: var(--sp-2) var(--sp-4);
  font-size: var(--fs-xs);
  font-weight: 500;
  color: var(--text-tertiary);
  border-bottom: 1px solid var(--border-light);
  background: var(--bg-sunken);
}

.report-table td {
  padding: var(--sp-3) var(--sp-4);
  border-bottom: 1px solid var(--border-light);
  color: var(--text-primary);
  vertical-align: middle;
}

.report-table tbody tr:last-child td {
  border-bottom: none;
}

.report-table tbody tr:hover {
  background: var(--bg-hover);
}

.col-key {
  width: 140px;
}

.col-num {
  width: 90px;
  font-variant-numeric: tabular-nums;
}

.col-mod {
  width: 110px;
  color: var(--text-secondary);
}

.col-user {
  width: 110px;
  color: var(--text-secondary);
}

.col-time {
  width: 150px;
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
  font-variant-numeric: tabular-nums;
}

.col-bug {
  width: 280px;
}

.col-rate {
  width: 220px;
}

.rate-cell {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
}

.rate-text {
  flex: none;
  width: 56px;
  text-align: right;
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.bug-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-1);
}

.cell-muted {
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
}

/* ---------- 进度条 ---------- */
.progress-track {
  height: 6px;
  flex: 1;
  min-width: 60px;
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
  padding: var(--sp-4) var(--sp-5);
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
  max-width: 320px;
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

/* ---------- 打印友好 ---------- */
@media print {
  .page {
    padding: 0;
  }

  .panel,
  .stat-card,
  .meta-strip {
    box-shadow: none;
    break-inside: avoid;
  }
}
</style>
