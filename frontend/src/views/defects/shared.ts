/**
 * 缺陷页面共享定义：接口类型、枚举文案/语义色调、状态机、格式化工具。
 * 仅供 DefectListView / DefectDetailView 及 defects/ 私有组件使用。
 */

/** StatusTag 支持的语义色调 */
export type Tone =
  | 'pass'
  | 'fail'
  | 'block'
  | 'skip'
  | 'warn'
  | 'info'
  | 'neutral'
  | 'accent'

export type Priority = 'P0' | 'P1' | 'P2' | 'P3'
export type Severity = 'Blocker' | 'Critical' | 'Major' | 'Minor' | 'Trivial'
export type DefectStatus =
  | 'Open'
  | 'In Progress'
  | 'Resolved'
  | 'Reopened'
  | 'Closed'
  | 'Rejected'
  | 'Duplicate'

/** 缺陷关联用户（assignee / reporter） */
export interface UserBrief {
  id: number
  username: string
  display_name: string
}

/** 关联用例（GET /defects/{id}/ 的 test_cases 项） */
export interface LinkedTestCase {
  id: number
  case_key: string
  title: string
  priority: Priority
  status: string
}

/** 关联需求（GET /defects/{id}/ 的 requirements 项） */
export interface LinkedRequirement {
  id: number
  key: string
  title: string
  status: string
  priority: Priority
}

/** 关联执行结果（GET /defects/{id}/ 的 test_results 项） */
export interface LinkedTestResult {
  id: number
  test_case: number
  test_case_key: string
  test_case_title: string
  test_run: number
  test_run_name: string
  status: string
  executed_at: string | null
  duration: number | null
  comment: string
}

/** GET /projects/{id}/defects/ 列表项 */
export interface DefectListItem {
  id: number
  key: string
  title: string
  description: string
  severity: Severity
  priority: Priority
  status: DefectStatus | string
  environment: string
  version: string
  assignee: UserBrief | null
  reporter: UserBrief | null
  resolved_at: string | null
  closed_at: string | null
  created_at: string
  updated_at: string
}

/** GET /defects/{id}/ 详情 */
export interface DefectDetail extends DefectListItem {
  test_cases: LinkedTestCase[]
  requirements: LinkedRequirement[]
  test_results: LinkedTestResult[]
}

/** 缺陷表单草稿模型（创建 / 编辑共用） */
export interface DefectFormModel {
  title: string
  description: string
  severity: Severity
  priority: Priority
  environment: string
  version: string
  assignee_id: number | null
}

/** 新建缺陷的默认表单模型 */
export function defaultDefectForm(): DefectFormModel {
  return {
    title: '',
    description: '',
    severity: 'Major',
    priority: 'P1',
    environment: '',
    version: '',
    assignee_id: null,
  }
}

export const PRIORITY_OPTIONS: { value: Priority; label: string }[] = [
  { value: 'P0', label: 'P0' },
  { value: 'P1', label: 'P1' },
  { value: 'P2', label: 'P2' },
  { value: 'P3', label: 'P3' },
]

export const PRIORITY_TONE: Record<Priority, Tone> = {
  P0: 'fail',
  P1: 'warn',
  P2: 'accent',
  P3: 'neutral',
}

/** 优先级语义色调（未知值兜底 neutral，便于表格插槽直接调用） */
export function priorityTone(priority: string): Tone {
  return PRIORITY_TONE[priority as Priority] ?? 'neutral'
}

/** 用例状态文案（关联用例列表展示） */
export const CASE_STATUS_LABELS: Record<string, string> = {
  draft: '草稿',
  active: '激活',
  deprecated: '废弃',
  archived: '归档',
}

export const SEVERITY_OPTIONS: { value: Severity; label: string }[] = [
  { value: 'Blocker', label: '致命' },
  { value: 'Critical', label: '严重' },
  { value: 'Major', label: '一般' },
  { value: 'Minor', label: '次要' },
  { value: 'Trivial', label: '轻微' },
]

const SEVERITY_LABELS: Record<string, string> = Object.fromEntries(
  SEVERITY_OPTIONS.map((item) => [item.value, item.label]),
)

const SEVERITY_TONE: Record<string, Tone> = {
  Blocker: 'fail',
  Critical: 'warn',
  Major: 'accent',
  Minor: 'neutral',
  Trivial: 'skip',
}

/** 严重程度中文文案（未知值兜底原值） */
export function severityLabel(severity: string): string {
  return SEVERITY_LABELS[severity] ?? severity
}

/** 严重程度语义色调（未知值兜底 neutral） */
export function severityTone(severity: string): Tone {
  return SEVERITY_TONE[severity] ?? 'neutral'
}

export const STATUS_OPTIONS: { value: DefectStatus; label: string }[] = [
  { value: 'Open', label: '打开' },
  { value: 'In Progress', label: '处理中' },
  { value: 'Resolved', label: '已修复' },
  { value: 'Reopened', label: '重新打开' },
  { value: 'Closed', label: '已关闭' },
  { value: 'Rejected', label: '已拒绝' },
  { value: 'Duplicate', label: '重复' },
]

const STATUS_LABELS: Record<string, string> = Object.fromEntries(
  STATUS_OPTIONS.map((item) => [item.value, item.label]),
)

const STATUS_TONE: Record<string, Tone> = {
  Open: 'warn',
  'In Progress': 'accent',
  Resolved: 'pass',
  Reopened: 'block',
  Closed: 'info',
  Rejected: 'skip',
  Duplicate: 'neutral',
}

/** 缺陷状态中文文案（未知值兜底原值） */
export function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status
}

/** 缺陷状态语义色调（未知值兜底 neutral） */
export function statusTone(status: string): Tone {
  return STATUS_TONE[status] ?? 'neutral'
}

/** 合法状态转移（与后端 common/statemachine.py 的 DEFECT_TRANSITIONS 一致，含回退） */
export const STATUS_TRANSITIONS: Record<DefectStatus, DefectStatus[]> = {
  Open: ['In Progress', 'Rejected', 'Duplicate', 'Closed'],
  'In Progress': ['Resolved', 'Open', 'Rejected', 'Duplicate'],
  Resolved: ['Closed', 'Reopened', 'In Progress'],
  Reopened: ['In Progress', 'Resolved', 'Open'],
  Closed: ['Reopened'],
  Rejected: ['Open'],
  Duplicate: ['Open'],
}

/** 执行结果状态文案（关联执行结果展示） */
export const RESULT_STATUS_LABELS: Record<string, string> = {
  passed: '通过',
  failed: '失败',
  blocked: '阻塞',
  skipped: '跳过',
  not_run: '未执行',
}

/**
 * 格式化 ISO 时间为本地时区「YYYY-MM-DD HH:mm」。
 * 后端输出带微秒，先截断到毫秒再解析，避免浏览器兼容问题。
 */
export function formatTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const normalized = iso.replace(/(\.\d{3})\d+/, '$1')
  const date = new Date(normalized)
  if (Number.isNaN(date.getTime())) return iso
  const pad = (value: number) => String(value).padStart(2, '0')
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    ` ${pad(date.getHours())}:${pad(date.getMinutes())}`
  )
}

/** 展示用户：display_name 优先，缺失回退 username */
export function userLabel(user: UserBrief | null | undefined): string {
  if (!user) return '—'
  return user.display_name || user.username || '—'
}
