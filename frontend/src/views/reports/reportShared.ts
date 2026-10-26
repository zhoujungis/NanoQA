/**
 * 报告页共享的展示辅助（ReportsView / RunReportView 私有）
 * 状态文案与后端 choices 保持一致（executions / defects 模型）。
 */

export type Tone = 'pass' | 'fail' | 'block' | 'skip' | 'warn' | 'info' | 'neutral' | 'accent'

/** TestRun.status → 文案与色调 */
export const RUN_STATUS: Record<string, { label: string; tone: Tone }> = {
  created: { label: '已创建', tone: 'info' },
  running: { label: '执行中', tone: 'accent' },
  finished: { label: '已完成', tone: 'pass' },
  cancelled: { label: '已取消', tone: 'skip' },
}

export function runStatusOf(status: string): { label: string; tone: Tone } {
  return RUN_STATUS[status] ?? { label: status, tone: 'neutral' }
}

/** 执行结果状态 → 文案与色调（结果分布图 / 统计口径一致） */
export const RESULT_LABELS: Record<string, string> = {
  passed: '通过',
  failed: '失败',
  blocked: '阻塞',
  skipped: '跳过',
  not_run: '未执行',
}

/** 缺陷状态（dashboard / run report 的 by_status 键为后端原始值） */
export const DEFECT_STATUS_LABELS: Record<string, string> = {
  Open: '打开',
  'In Progress': '处理中',
  Resolved: '已修复',
  Reopened: '重新打开',
  Closed: '已关闭',
  Rejected: '已拒绝',
  Duplicate: '重复',
}

/** 缺陷严重程度（Defect.SEVERERITY_CHOICES） */
export const SEVERITY_LABELS: Record<string, string> = {
  Blocker: '致命',
  Critical: '严重',
  Major: '一般',
  Minor: '次要',
  Trivial: '轻微',
}

/** 2026-10-26 12:30 */
export function formatTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

/** 0.902 → 90.2% */
export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${(value * 100).toFixed(1)}%`
}

/** 比率 → 0~100 的整数（进度条宽度用） */
export function percentWidth(value: number | null | undefined): string {
  const ratio = Math.min(1, Math.max(0, value ?? 0))
  return `${(ratio * 100).toFixed(1)}%`
}
