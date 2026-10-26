/**
 * 测试用例页面共享定义：接口类型、枚举文案/语义色调、格式化工具。
 * 仅供 TestCaseListView / TestCaseDetailView 及 testcases/ 私有组件使用。
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
export type CaseStatus = 'draft' | 'active' | 'deprecated' | 'archived'

/** GET /projects/{id}/modules/ 树节点 */
export interface ModuleNode {
  id: number
  name: string
  description: string
  parent_id: number | null
  sort_order: number
  children: ModuleNode[]
  case_count: number
  updated_at: string
}

/** GET /projects/{id}/tags/ */
export interface TagBrief {
  id: number
  name: string
  color: string
}

/** 用例关联用户（owner / creator / created_by） */
export interface UserBrief {
  id: number
  username: string
  display_name: string
}

/** steps JSONB 元素 */
export interface StepItem {
  order: number
  action: string
  expected: string
}

/** GET /projects/{id}/testcases/ 列表项 */
export interface TestCaseListItem {
  id: number
  case_key: string
  title: string
  priority: Priority
  case_type: string
  status: CaseStatus
  module_id: number | null
  module_name: string | null
  owner: UserBrief | null
  tags: TagBrief[]
  automation_status: string
  current_version: number
  precondition_summary: string
  created_at: string
  updated_at: string
}

/** GET /testcases/{id}/ 详情 */
export interface TestCaseDetail extends TestCaseListItem {
  description: string
  precondition: string
  module_path: { id: number; name: string }[]
  creator: UserBrief | null
  steps: StepItem[]
  expected_result: string
  change_summary: string
  sort_order: number
  automation_framework: string
  automation_identifier: string
  automation_script: string
}

/** GET /testcases/{id}/versions/ 版本列表项 */
export interface CaseVersionItem {
  id: number
  version: number
  title: string
  change_summary: string
  created_by: UserBrief | null
  created_at: string
}

/** GET /testcase-versions/{id}/ 版本快照 */
export interface CaseVersionDetail extends CaseVersionItem {
  test_case: number
  description: string
  precondition: string
  steps: StepItem[]
  expected_result: string
}

/** GET /testcases/{id}/history/ 操作历史（审计日志） */
export interface AuditLogItem {
  id: number
  action: string
  object_type: string
  object_id: number
  object_ref: string
  old_data: Record<string, unknown> | null
  new_data: Record<string, unknown> | null
  username: string | null
  display_name: string | null
  ip_address: string | null
  request_id: string
  created_at: string
}

/** 批量操作返回：逐条独立，失败不影响其余 */
export interface BatchResult {
  succeeded: number[]
  failed: { id: number; reason: string }[]
}

/** 用例表单草稿模型（创建 / 编辑共用） */
export interface CaseFormModel {
  title: string
  module_id: number | null
  priority: Priority
  case_type: string
  precondition: string
  description: string
  expected_result: string
  steps: StepItem[]
  tag_ids: number[]
  owner_id: number | null
  /** 仅编辑模式展示：变更摘要 */
  change_summary: string
}

/** 空白步骤行 */
export function emptyStep(): StepItem {
  return { order: 1, action: '', expected: '' }
}

/** 新建用例的默认表单模型 */
export function defaultCaseForm(moduleId: number | null = null): CaseFormModel {
  return {
    title: '',
    module_id: moduleId,
    priority: 'P1',
    case_type: 'functional',
    precondition: '',
    description: '',
    expected_result: '',
    steps: [emptyStep()],
    tag_ids: [],
    owner_id: null,
    change_summary: '',
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

export const TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: 'functional', label: '功能' },
  { value: 'regression', label: '回归' },
  { value: 'smoke', label: '冒烟' },
  { value: 'integration', label: '集成' },
  { value: 'api', label: '接口' },
  { value: 'ui', label: 'UI' },
  { value: 'performance', label: '性能' },
  { value: 'security', label: '安全' },
  { value: 'compatibility', label: '兼容' },
  { value: 'exploratory', label: '探索' },
]

export const TYPE_LABELS: Record<string, string> = Object.fromEntries(
  TYPE_OPTIONS.map((item) => [item.value, item.label]),
)

export const STATUS_OPTIONS: { value: CaseStatus; label: string }[] = [
  { value: 'draft', label: '草稿' },
  { value: 'active', label: '激活' },
  { value: 'deprecated', label: '废弃' },
  { value: 'archived', label: '归档' },
]

export const STATUS_LABELS: Record<CaseStatus, string> = {
  draft: '草稿',
  active: '激活',
  deprecated: '废弃',
  archived: '归档',
}

export const STATUS_TONE: Record<CaseStatus, Tone> = {
  draft: 'neutral',
  active: 'pass',
  deprecated: 'warn',
  archived: 'info',
}

/** 合法状态转移（与后端 common/statemachine.py 保持一致） */
export const STATUS_TRANSITIONS: Record<CaseStatus, CaseStatus[]> = {
  draft: ['active', 'archived'],
  active: ['deprecated', 'archived', 'draft'],
  deprecated: ['active', 'archived'],
  archived: ['active'],
}

export const AUTOMATION_OPTIONS: { value: string; label: string }[] = [
  { value: 'manual', label: '手工' },
  { value: 'automated', label: '已自动化' },
  { value: 'partial', label: '部分自动化' },
  { value: 'not_automatable', label: '不可自动化' },
]

export const AUTOMATION_LABELS: Record<string, string> = Object.fromEntries(
  AUTOMATION_OPTIONS.map((item) => [item.value, item.label]),
)

/** 审计动作文案 */
export const AUDIT_ACTION_LABELS: Record<string, string> = {
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

/**
 * 格式化 ISO 时间为本地时区「YYYY-MM-DD HH:mm」。
 * 后端输出带微秒（如 2026-10-26T11:40:00.123456+08:00），
 * 先截断到毫秒再解析，避免浏览器兼容问题。
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

/** 扁平化模块树（el-select 等平铺场景使用） */
export function flattenModules(nodes: ModuleNode[]): ModuleNode[] {
  const result: ModuleNode[] = []
  const walk = (list: ModuleNode[]) => {
    for (const node of list) {
      result.push(node)
      walk(node.children || [])
    }
  }
  walk(nodes)
  return result
}

/** 生成模块全路径文案，如「订单 / 支付」 */
export function modulePathText(
  path: { id: number; name: string }[] | null | undefined,
  fallback: string | null,
): string {
  if (path && path.length) return path.map((item) => item.name).join(' / ')
  return fallback || '未分类'
}
