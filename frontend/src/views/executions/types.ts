/**
 * 测试执行页私有类型定义
 * 字段口径以 backend/apps/executions/serializers.py 与 testcases 序列化器为准。
 */

/** 结果状态（POST 提交仅允许前四种，not_run 表示未执行） */
export type ResultStatus = 'not_run' | 'passed' | 'failed' | 'blocked' | 'skipped'

/** 执行结果（GET /runs/{id}/results/ 列表项） */
export interface RunResult {
  id: number
  test_run: number
  test_case: number
  case_key: string
  title: string
  module: string | null
  /** 绑定的用例版本快照 id（坑 4：结果固定绑执行时版本） */
  test_case_version: number
  case_version: number
  status: ResultStatus
  actual_result: string
  comment: string
  executed_by: number | null
  executed_by_name: string | null
  executed_at: string | null
  duration: number
}

/** 用例版本快照步骤（GET /testcase-versions/{id}/ steps 项） */
export interface CaseStep {
  order: number
  action: string
  expected: string
}

/** 用例版本快照（GET /testcase-versions/{id}/） */
export interface VersionSnapshot {
  id: number
  test_case: number
  version: number
  title: string
  description: string
  precondition: string
  steps: CaseStep[]
  expected_result: string
  change_summary: string
}

/** Run 详情（GET /runs/{id}/，含结果统计 stats） */
export interface RunDetail {
  id: number
  project: number
  test_plan: number
  name: string
  environment: string
  build_version: string
  status: string
  started_at: string | null
  finished_at: string | null
  stats: {
    total: number
    not_run: number
    passed: number
    failed: number
    blocked: number
    skipped: number
  }
}

/** 缺陷简要（POST /results/{id}/defects/ 响应 defect 字段） */
export interface DefectBrief {
  id: number
  key: string
  title: string
  status: string
}

/** 缺陷创建入参（DefectFromResultSerializer 可写字段） */
export interface DefectForm {
  title: string
  description: string
  severity: string
  priority: string
  comment: string
}
