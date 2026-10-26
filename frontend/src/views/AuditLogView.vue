<template>
  <section class="page">
    <PageHeader title="操作日志" subtitle="记录项目内的关键操作，展开行可查看字段级变更前后对比">
      <template #actions>
        <el-button :disabled="loading" @click="loadAll">刷新</el-button>
      </template>
    </PageHeader>

    <!-- 筛选栏（后端未提供查询参数，为前端过滤） -->
    <div class="filter-bar">
      <el-select v-model="filterAction" placeholder="动作类型" clearable class="filter-select">
        <el-option v-for="(label, value) in ACTION_LABELS" :key="value" :label="label" :value="value" />
      </el-select>
      <el-select v-model="filterObjectType" placeholder="对象类型" clearable class="filter-select">
        <el-option v-for="item in objectTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <el-select v-model="filterUser" placeholder="操作人" clearable filterable class="filter-select">
        <el-option v-for="user in userOptions" :key="user.value" :label="user.label" :value="user.value" />
      </el-select>
      <el-date-picker
        v-model="filterRange"
        type="datetimerange"
        range-separator="至"
        start-placeholder="开始时间"
        end-placeholder="结束时间"
        class="filter-range"
      />
      <el-button v-if="hasFilter" link type="primary" @click="resetFilters">清空筛选</el-button>
      <span v-if="truncated" class="filter-note">仅展示最近 {{ rows.length }} 条记录</span>
    </div>

    <!-- 错误态 -->
    <div v-if="error" class="state-panel">
      <p class="state-text">{{ error }}</p>
      <el-button size="small" @click="loadAll">重新加载</el-button>
    </div>

    <!-- 日志表格 -->
    <div v-else v-loading="loading" class="table-panel">
      <el-table :data="pagedRows" row-key="id">
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="diff-wrap">
              <div class="diff-meta">
                <span><span class="diff-meta-label">请求 ID</span>{{ row.request_id || '—' }}</span>
                <span><span class="diff-meta-label">IP 地址</span>{{ row.ip_address || '—' }}</span>
              </div>
              <table v-if="diffRows(row).length" class="diff-table">
                <thead>
                  <tr>
                    <th class="diff-col-field">字段</th>
                    <th class="diff-col-value">变更前</th>
                    <th class="diff-col-value">变更后</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in diffRows(row)" :key="item.field" :class="`is-${item.state}`">
                    <td class="diff-col-field">{{ item.field }}</td>
                    <td class="diff-col-value">
                      <span class="diff-value">{{ item.before }}</span>
                    </td>
                    <td class="diff-col-value">
                      <span class="diff-value">{{ item.after }}</span>
                    </td>
                  </tr>
                </tbody>
              </table>
              <p v-else class="diff-empty">该操作未记录字段级变更</p>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="155">
          <template #default="{ row }">
            <span class="time-cell">{{ formatTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作人" width="150">
          <template #default="{ row }">
            <span class="user-cell">{{ row.display_name || row.username || '系统' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="动作" width="110">
          <template #default="{ row }">
            <StatusTag :tone="actionTone(row.action)">{{ actionLabel(row.action) }}</StatusTag>
          </template>
        </el-table-column>
        <el-table-column label="对象类型" width="120">
          <template #default="{ row }">
            <span class="type-cell">{{ objectTypeLabel(row.object_type) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="对象标识" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="ref-cell">{{ row.object_ref || `#${row.object_id}` || '—' }}</span>
          </template>
        </el-table-column>

        <template #empty>
          <div class="empty-state">
            <p class="state-text">
              {{ hasFilter ? '没有符合筛选条件的操作记录' : '暂无操作记录' }}
            </p>
            <el-button v-if="hasFilter" size="small" text type="primary" @click="resetFilters">
              清空筛选
            </el-button>
          </div>
        </template>
      </el-table>

      <div v-if="filteredRows.length > pageSize" class="pager">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="filteredRows.length"
          layout="prev, pager, next"
          small
        />
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api, notifyError, type PageResult } from '@/api/client'
import PageHeader from '@/components/ui/PageHeader.vue'
import StatusTag from '@/components/ui/StatusTag.vue'

/** GET /projects/{id}/audit-logs/ 列表项（AuditLogSerializer） */
interface AuditLogItem {
  id: number
  action: string
  object_type: string
  object_id: number | null
  object_ref: string
  old_data: Record<string, unknown> | null
  new_data: Record<string, unknown> | null
  username: string | null
  display_name: string | null
  ip_address: string | null
  request_id: string
  created_at: string
}

/** 展开行中的一条字段级差异 */
interface DiffRow {
  field: string
  before: string
  after: string
  state: 'added' | 'removed' | 'changed' | 'same'
}

/** 动作类型（AuditLog.ACTION_CHOICES） */
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

/** 对象类型（模型名小写）→ 中文（与后端模型全集对齐） */
const OBJECT_TYPE_LABELS: Record<string, string> = {
  project: '项目',
  projectmember: '项目成员',
  module: '模块',
  tag: '标签',
  organization: '组织',
  organizationmember: '组织成员',
  user: '用户',
  role: '角色',
  permission: '权限',
  rolepermission: '角色权限',
  requirement: '需求',
  requirementtestcase: '需求-用例关联',
  requirementdefect: '需求-缺陷关联',
  testcase: '测试用例',
  testcaseversion: '用例版本',
  testcasetag: '用例标签',
  testplan: '测试计划',
  testplancase: '计划用例',
  testrun: '测试执行',
  testresult: '测试结果',
  defect: '缺陷',
  testcasedefect: '用例-缺陷关联',
  testresultdefect: '结果-缺陷关联',
  aitask: 'AI 任务',
  attachment: '附件',
  auditlog: '操作日志',
  numbersequence: '编号序列',
}

/** 一次最多加载 500 条（5 页 × 100），前端过滤 */
const LOAD_CAP = 500
const PAGE_FETCH_SIZE = 100
const pageSize = 15

const route = useRoute()
const projectId = computed(() => String(route.params.projectId || ''))

const rows = ref<AuditLogItem[]>([])
const loading = ref(false)
const error = ref('')

const filterAction = ref('')
const filterObjectType = ref('')
const filterUser = ref('')
const filterRange = ref<Date[] | null>(null)
const currentPage = ref(1)

const truncated = computed(() => rows.value.length >= LOAD_CAP)

const hasFilter = computed(
  () => Boolean(filterAction.value || filterObjectType.value || filterUser.value || filterRange.value),
)

/** 对象类型下拉：取日志中出现过的类型 */
const objectTypeOptions = computed(() => {
  const seen = new Set(rows.value.map((r) => r.object_type))
  return [...seen].sort().map((value) => ({ value, label: objectTypeLabel(value) }))
})

/** 操作人下拉：取日志中出现过的用户 */
const userOptions = computed(() => {
  const map = new Map<string, string>()
  for (const row of rows.value) {
    const value = row.username || ''
    if (value && !map.has(value)) map.set(value, row.display_name || row.username || value)
  }
  return [...map.entries()].map(([value, label]) => ({ value, label }))
})

/** 前端过滤（后端 audit 接口不支持查询参数） */
const filteredRows = computed(() => {
  const start = filterRange.value?.[0]?.getTime()
  const end = filterRange.value?.[1]?.getTime()
  return rows.value.filter((row) => {
    if (filterAction.value && row.action !== filterAction.value) return false
    if (filterObjectType.value && row.object_type !== filterObjectType.value) return false
    if (filterUser.value && (row.username || '') !== filterUser.value) return false
    if (start !== undefined || end !== undefined) {
      const t = new Date(row.created_at).getTime()
      if (Number.isNaN(t)) return false
      if (start !== undefined && t < start) return false
      if (end !== undefined && t > end) return false
    }
    return true
  })
})

const pagedRows = computed(() => {
  const from = (currentPage.value - 1) * pageSize
  return filteredRows.value.slice(from, from + pageSize)
})

function actionLabel(action: string): string {
  return ACTION_LABELS[action] || action
}

function actionTone(action: string): 'accent' | 'info' | 'fail' | 'warn' | 'pass' | 'neutral' {
  const tones: Record<string, 'accent' | 'info' | 'fail' | 'warn' | 'pass' | 'neutral'> = {
    create: 'accent',
    update: 'info',
    delete: 'fail',
    transition: 'warn',
    execute: 'pass',
  }
  return tones[action] || 'neutral'
}

function objectTypeLabel(type: string): string {
  return OBJECT_TYPE_LABELS[type] || type
}

function formatTime(value: string): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'string') return value || '（空）'
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

/** 计算 old_data / new_data 的字段级差异 */
function diffRows(row: AuditLogItem): DiffRow[] {
  const oldData = row.old_data
  const newData = row.new_data
  if (!oldData && !newData) return []
  const keys = [...new Set([...Object.keys(oldData ?? {}), ...Object.keys(newData ?? {})])].sort()
  return keys.map((field) => {
    const before = oldData ? oldData[field] : undefined
    const after = newData ? newData[field] : undefined
    const beforeText = oldData ? formatValue(before) : '—'
    const afterText = newData ? formatValue(after) : '—'
    let state: DiffRow['state'] = 'same'
    if (!oldData || (before === undefined && after !== undefined)) state = 'added'
    else if (!newData || (after === undefined && before !== undefined)) state = 'removed'
    else if (JSON.stringify(before) !== JSON.stringify(after)) state = 'changed'
    return { field, before: beforeText, after: afterText, state }
  })
}

function resetFilters() {
  filterAction.value = ''
  filterObjectType.value = ''
  filterUser.value = ''
  filterRange.value = null
}

/** 分页拉取审计日志（后端分页 size=100，最多 LOAD_CAP 条） */
async function loadAll() {
  if (!projectId.value) return
  loading.value = true
  error.value = ''
  try {
    const collected: AuditLogItem[] = []
    let page = 1
    let total = Infinity
    while (collected.length < LOAD_CAP && (page - 1) * PAGE_FETCH_SIZE < total) {
      const data = await api.get<PageResult<AuditLogItem>>(`/projects/${projectId.value}/audit-logs/`, {
        params: { page, page_size: PAGE_FETCH_SIZE },
      })
      total = data.total
      collected.push(...data.items)
      if (!data.items.length) break
      page += 1
    }
    rows.value = collected.slice(0, LOAD_CAP)
    currentPage.value = 1
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载操作日志失败，请稍后重试'
    notifyError(e)
  } finally {
    loading.value = false
  }
}

onMounted(loadAll)
</script>

<style scoped>
.page {
  padding: var(--sp-6);
}

/* ---------------- 筛选栏 ---------------- */
.filter-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--sp-2);
  margin-bottom: var(--sp-3);
}

.filter-select {
  width: 150px;
}

.filter-range {
  max-width: 360px;
}

.filter-note {
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
}

/* ---------------- 表格 ---------------- */
.table-panel {
  background: var(--bg-surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.time-cell {
  color: var(--text-secondary);
  font-size: var(--fs-sm);
  font-variant-numeric: tabular-nums;
}

.user-cell {
  color: var(--text-primary);
}

.type-cell {
  color: var(--text-secondary);
}

.ref-cell {
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
  color: var(--text-primary);
}

/* ---------------- 展开行：变更对比 ---------------- */
.diff-wrap {
  padding: var(--sp-3) var(--sp-6) var(--sp-4);
  background: var(--bg-sunken);
}

.diff-meta {
  display: flex;
  gap: var(--sp-6);
  margin-bottom: var(--sp-3);
  color: var(--text-tertiary);
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
}

.diff-meta-label {
  margin-right: var(--sp-2);
  color: var(--text-placeholder);
  font-family: var(--font-sans);
}

.diff-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--bg-surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  table-layout: fixed;
}

.diff-table th,
.diff-table td {
  padding: var(--sp-1) var(--sp-3);
  border-bottom: 1px solid var(--border-light);
  text-align: left;
  vertical-align: top;
  font-size: var(--fs-sm);
  line-height: var(--lh-base);
  word-break: break-all;
}

.diff-table th {
  color: var(--text-tertiary);
  font-weight: 600;
  background: var(--bg-sunken);
}

.diff-table tr:last-child td {
  border-bottom: none;
}

.diff-col-field {
  width: 160px;
  color: var(--text-secondary);
  font-family: var(--font-mono);
}

.diff-value {
  color: var(--text-secondary);
}

/* 差异高亮：新增 / 删除 / 变更 */
.diff-table tr.is-added .diff-col-value:last-child,
.diff-table tr.is-changed .diff-col-value:last-child {
  background: var(--success-50);
}

.diff-table tr.is-added .diff-col-value:last-child .diff-value,
.diff-table tr.is-changed .diff-col-value:last-child .diff-value {
  color: var(--status-pass);
}

.diff-table tr.is-removed .diff-col-value:nth-child(2),
.diff-table tr.is-changed .diff-col-value:nth-child(2) {
  background: var(--danger-50);
}

.diff-table tr.is-removed .diff-col-value:nth-child(2) .diff-value,
.diff-table tr.is-changed .diff-col-value:nth-child(2) .diff-value {
  color: var(--status-fail);
}

.diff-table tr.is-same .diff-value {
  color: var(--text-placeholder);
}

.diff-empty {
  margin: 0;
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
}

/* ---------------- 分页与状态 ---------------- */
.pager {
  display: flex;
  justify-content: flex-end;
  padding: var(--sp-3) var(--sp-4);
  border-top: 1px solid var(--border-light);
}

.state-panel,
.empty-state {
  padding: var(--sp-10) var(--sp-6);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-3);
}

.state-panel {
  background: var(--bg-surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
}

.state-text {
  margin: 0;
  color: var(--text-tertiary);
  font-size: var(--fs-base);
}

:deep(.el-table td.el-table__cell) {
  padding: 9px 0;
}

:deep(.el-table__expand-icon) {
  color: var(--text-placeholder);
}
</style>
