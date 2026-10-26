/**
 * 需求页面共享定义：接口类型、枚举文案/语义色调、状态机、格式化工具。
 * 仅供 RequirementListView / RequirementDetailView 及 requirements/ 私有组件使用。
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
export type ReqStatus = 'draft' | 'ready' | 'in_progress' | 'done' | 'cancelled'

/** 需求关联用户（owner / creator） */
export interface UserBrief {
  id: number
  username: string
  display_name: string
}

/** 需求关联用例（GET /requirements/{id}/ 的 test_cases 项） */
export interface LinkedTestCase {
  id: number
  case_key: string
  title: string
  priority: Priority
  status: string
  automation_status: string
}

/** 需求覆盖率（GET /requirements/{id}/coverage/） */
export interface Coverage {
  linked_cases: number
  expected_cases: number
  executed: number
  passed: number
  failed: number
  blocked: number
  skipped: number
  not_run: number
  coverage: number
  risk_level: 'low' | 'medium' | 'high'
}

/** GET /projects/{id}/requirements/ 列表项 */
export interface RequirementListItem {
  id: number
  key: string
  title: string
  description: string
  status: ReqStatus | string
  priority: Priority
  creator: UserBrief | null
  owner: UserBrief | null
  version: number
  created_at: string
  updated_at: string
}

/** GET /requirements/{id}/ 详情 */
export interface RequirementDetail extends RequirementListItem {
  test_cases: LinkedTestCase[]
  coverage: Coverage
}

/** 需求表单草稿模型（创建 / 编辑共用） */
export interface RequirementFormModel {
  title: string
  description: string
  status: ReqStatus | string
  priority: Priority
  owner_id: number | null
}

/** 新建需求的默认表单模型 */
export function defaultRequirementForm(): RequirementFormModel {
  return {
    title: '',
    description: '',
    status: 'draft',
    priority: 'P1',
    owner_id: null,
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

export const STATUS_OPTIONS: { value: ReqStatus; label: string }[] = [
  { value: 'draft', label: '草稿' },
  { value: 'ready', label: '就绪' },
  { value: 'in_progress', label: '进行中' },
  { value: 'done', label: '完成' },
  { value: 'cancelled', label: '取消' },
]

const STATUS_LABELS: Record<string, string> = Object.fromEntries(
  STATUS_OPTIONS.map((item) => [item.value, item.label]),
)

const STATUS_TONE: Record<string, Tone> = {
  draft: 'neutral',
  ready: 'info',
  in_progress: 'accent',
  done: 'pass',
  cancelled: 'skip',
}

/** 状态中文文案（未知状态兜底原值，兼容历史数据） */
export function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status
}

/** 状态语义色调（未知状态兜底 neutral） */
export function statusTone(status: string): Tone {
  return STATUS_TONE[status] ?? 'neutral'
}

/** 合法状态转移（与后端 common/statemachine.py 的 REQUIREMENT_TRANSITIONS 一致） */
export const STATUS_TRANSITIONS: Record<ReqStatus, ReqStatus[]> = {
  draft: ['ready', 'cancelled'],
  ready: ['draft', 'in_progress', 'cancelled'],
  in_progress: ['done', 'ready', 'cancelled'],
  done: ['in_progress'],
  cancelled: ['draft'],
}

/** 风险等级文案与色调（覆盖率面板） */
export const RISK_META: Record<Coverage['risk_level'], { label: string; tone: Tone }> = {
  low: { label: '低风险', tone: 'pass' },
  medium: { label: '中风险', tone: 'warn' },
  high: { label: '高风险', tone: 'fail' },
}

/** 用例状态文案（关联用例列表展示） */
export const CASE_STATUS_LABELS: Record<string, string> = {
  draft: '草稿',
  active: '激活',
  deprecated: '废弃',
  archived: '归档',
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
