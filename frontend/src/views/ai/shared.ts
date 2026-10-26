/**
 * AI 助手页面共享定义：接口类型、任务/用例枚举文案、语义色调与格式化工具。
 * 仅供 AiWorkspaceView 与 views/ai/ 私有组件使用。
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

/** AI 任务状态（后端 AITask.status） */
export type TaskStatus = 'queued' | 'running' | 'succeeded' | 'failed'

/** AI 任务类型（后端 AITask.TASK_TYPES） */
export type TaskType =
  | 'generate_testcases'
  | 'review_testcase'
  | 'expand_edge_cases'
  | 'detect_duplicate_cases'
  | 'analyze_requirement'
  | 'analyze_defect'
  | 'generate_test_data'
  | 'analyze_test_report'

/** 用例步骤：动作 + 预期 */
export interface AiCaseStep {
  action: string
  expected: string
}

/** AI 生成的单条用例草案（POST /ai/testcases/generate/ 的 cases 项） */
export interface AiGeneratedCase {
  title: string
  priority: string
  type: string
  precondition?: string
  steps: AiCaseStep[]
  expected_result?: string
  description?: string
}

/** AI 任务输出（output_data）：按任务类型取不同字段 */
export interface AiTaskOutput {
  cases?: AiGeneratedCase[]
  accepted?: boolean
  rejected?: boolean
  accepted_case_ids?: number[]
  score?: number
  issues?: { severity: string; message: string }[]
  suggestions?: string[]
  pairs?: DuplicatePair[]
  summary?: string
  suggested_cases?: AiGeneratedCase[]
  risks?: { level: string; message: string }[]
  possible_causes?: string[]
  related_case_ids?: number[]
}

/** 重复用例检测结果项（POST /ai/testcases/detect-duplicates/ 的 pairs 项） */
export interface DuplicatePair {
  case_a: number
  case_b: number
  similarity: number
}

/** AI 任务记录（GET /ai/tasks/、GET /ai/tasks/{id}/） */
export interface AiTaskRecord {
  id: number
  task_type: TaskType
  status: TaskStatus
  model: string
  input_data: Record<string, unknown>
  output_data: AiTaskOutput
  tokens: number
  duration: number
  error: string
  user: { id: number; username: string } | null
  created_at: string
  completed_at: string | null
}

/** 入库成功返回的正式用例（POST /ai/tasks/{id}/accept/ 的 cases 项） */
export interface AcceptedCase {
  id: number
  case_key: string
  title: string
  priority: string
  case_type: string
  status: string
}

/** 需求简项（下拉候选） */
export interface RequirementBrief {
  id: number
  key: string
  title: string
}

/** 用例简项（下拉候选） */
export interface CaseBrief {
  id: number
  case_key: string
  title: string
}

/** 草案卡片模型（父组件持有，子组件双向修改） */
export interface CaseDraft {
  uid: number
  selected: boolean
  title: string
  priority: Priority
  caseType: string
  precondition: string
  steps: AiCaseStep[]
  expectedResult: string
  /** 入库成功后回填的正式用例信息 */
  caseId: number | null
  caseKey: string | null
  /** 校验失败标记（提交入库时回填，用于卡片高亮） */
  invalid: boolean
}

/** 生成面板表单模型 */
export interface GenerateForm {
  titleHint: string
  requirementId: number | null
  count: number
  includeEdgeCases: boolean
  includeSecurity: boolean
  includeCompatibility: boolean
}

/** 任务类型文案 */
export const TASK_TYPE_LABELS: Record<TaskType, string> = {
  generate_testcases: '生成用例',
  review_testcase: '评审用例',
  expand_edge_cases: '补充边界场景',
  detect_duplicate_cases: '重复用例检测',
  analyze_requirement: '需求分析',
  analyze_defect: '缺陷分析',
  generate_test_data: '生成测试数据',
  analyze_test_report: '测试报告分析',
}

export const TASK_TYPE_OPTIONS: { value: TaskType; label: string }[] = (
  Object.keys(TASK_TYPE_LABELS) as TaskType[]
).map((value) => ({ value, label: TASK_TYPE_LABELS[value] }))

/** 任务类型文案（未知值兜底原值） */
export function taskTypeLabel(type: string): string {
  return TASK_TYPE_LABELS[type as TaskType] ?? type
}

/** 会产出用例草案、需要人工审核入库的任务类型 */
export const CASE_GENERATING_TYPES: TaskType[] = ['generate_testcases', 'expand_edge_cases']

export const PRIORITY_OPTIONS: { value: Priority; label: string }[] = [
  { value: 'P0', label: 'P0' },
  { value: 'P1', label: 'P1' },
  { value: 'P2', label: 'P2' },
  { value: 'P3', label: 'P3' },
]

/** 用例类型文案（后端 TestCase.TYPE_CHOICES） */
export const CASE_TYPE_LABELS: Record<string, string> = {
  functional: '功能',
  regression: '回归',
  smoke: '冒烟',
  integration: '集成',
  api: '接口',
  ui: 'UI',
  performance: '性能',
  security: '安全',
  compatibility: '兼容',
  exploratory: '探索',
}

export const CASE_TYPE_OPTIONS: { value: string; label: string }[] = Object.entries(CASE_TYPE_LABELS).map(
  ([value, label]) => ({ value, label }),
)

/** 优先级语义色调 */
export function priorityTone(priority: string): Tone {
  const map: Record<string, Tone> = { P0: 'fail', P1: 'warn', P2: 'accent', P3: 'neutral' }
  return map[priority] ?? 'neutral'
}

/** 用例类型文案（未知值兜底原值） */
export function caseTypeLabel(type: string): string {
  return CASE_TYPE_LABELS[type] ?? type
}

/** 问题/风险等级语义色调（high/medium/low 共用） */
export function levelTone(level: string): Tone {
  const map: Record<string, Tone> = { high: 'fail', medium: 'warn', low: 'info' }
  return map[level] ?? 'neutral'
}

/** 问题/风险等级文案 */
export function levelLabel(level: string): string {
  const map: Record<string, string> = { high: '高', medium: '中', low: '低' }
  return map[level] ?? level
}

/** 任务状态展示：已审核（accepted/rejected）优先于原始状态，成功态区分「待审核」 */
export function taskStatusInfo(task: AiTaskRecord): { label: string; tone: Tone } {
  if (task.output_data?.accepted) return { label: '已入库', tone: 'pass' }
  if (task.output_data?.rejected) return { label: '已丢弃', tone: 'neutral' }
  switch (task.status) {
    case 'queued':
      return { label: '排队中', tone: 'info' }
    case 'running':
      return { label: '执行中', tone: 'accent' }
    case 'succeeded':
      return CASE_GENERATING_TYPES.includes(task.task_type)
        ? { label: '待审核', tone: 'warn' }
        : { label: '成功', tone: 'pass' }
    default:
      return { label: '失败', tone: 'fail' }
  }
}

/** 任务是否已审核（入库或丢弃） */
export function isTaskReviewed(task: AiTaskRecord): boolean {
  return Boolean(task.output_data?.accepted || task.output_data?.rejected)
}

/** 任务是否可以入库（产用例草案 + 成功 + 未审核） */
export function canTaskAccept(task: AiTaskRecord): boolean {
  return (
    CASE_GENERATING_TYPES.includes(task.task_type) &&
    task.status === 'succeeded' &&
    !isTaskReviewed(task)
  )
}

/** 任务是否可以丢弃（成功且未审核） */
export function canTaskReject(task: AiTaskRecord): boolean {
  return task.status === 'succeeded' && !isTaskReviewed(task)
}

/** 任务输入摘要（列表「输入摘要」列） */
export function inputSummary(task: AiTaskRecord): string {
  const input = task.input_data ?? {}
  const titleHint = typeof input.title_hint === 'string' ? input.title_hint.trim() : ''
  if (titleHint) return titleHint
  if (input.requirement_id) return `需求 #${input.requirement_id}`
  if (input.test_case_id) return `用例 #${input.test_case_id}`
  if (input.defect_id) return `缺陷 #${input.defect_id}`
  if (task.task_type === 'detect_duplicate_cases') return '项目内全量用例'
  return '—'
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

/** 耗时展示（后端 duration 单位为毫秒） */
export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return '—'
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`
}

/** 由 AI 生成结果构建可编辑草案卡片 */
export function toDrafts(cases: AiGeneratedCase[]): CaseDraft[] {
  return cases.map((item, index) => ({
    uid: index + 1,
    selected: true,
    title: item.title ?? '',
    priority: (item.priority as Priority) ?? 'P1',
    caseType: item.type ?? 'functional',
    precondition: item.precondition ?? '',
    steps: (item.steps ?? []).map((step) => ({ action: step.action ?? '', expected: step.expected ?? '' })),
    expectedResult: item.expected_result ?? '',
    caseId: null,
    caseKey: null,
    invalid: false,
  }))
}

/** 草案校验：返回第一条错误文案，通过则返回 null */
export function validateDraft(draft: CaseDraft): string | null {
  const title = draft.title.trim()
  if (!title) return '标题不能为空'
  if (title.length > 255) return '标题不能超过 255 个字符'
  if (!draft.steps.length) return '至少保留一个步骤'
  for (let index = 0; index < draft.steps.length; index += 1) {
    const step = draft.steps[index]
    if (!step.action.trim()) return `第 ${index + 1} 步的操作动作不能为空`
    if (!step.expected.trim()) return `第 ${index + 1} 步的预期结果不能为空`
  }
  return null
}

/** 草案 → 创建正式用例请求体（POST /projects/{id}/testcases/） */
export function toCasePayload(draft: CaseDraft) {
  return {
    title: draft.title.trim(),
    priority: draft.priority,
    case_type: draft.caseType,
    precondition: draft.precondition.trim(),
    steps: draft.steps.map((step, index) => ({
      order: index + 1,
      action: step.action.trim(),
      expected: step.expected.trim(),
    })),
    expected_result: draft.expectedResult.trim(),
    status: 'draft',
  }
}
