<template>
  <section class="run-page">
    <!-- 加载失败：错误态 + 重试 -->
    <div v-if="error" class="state-box">
      <p class="state-text">{{ error }}</p>
      <el-button size="small" @click="loadAll">重新加载</el-button>
    </div>

    <template v-else-if="run">
      <!-- 顶部：Run 信息 + 进度统计 + 出口 -->
      <header class="run-top">
        <div class="run-ident">
          <div class="run-title-row">
            <h1 class="run-name">{{ run.name }}</h1>
            <StatusTag :tone="runTone(run.status)" :label="runLabel(run.status)" />
          </div>
          <div class="run-meta">
            <span>环境 <b>{{ run.environment || '—' }}</b></span>
            <span>构建 <b class="mono">{{ run.build_version || '—' }}</b></span>
            <span v-if="run.started_at" class="muted">开始于 {{ fmtTime(run.started_at) }}</span>
          </div>
        </div>

        <div class="run-progress">
          <div class="stat-row">
            <span class="stat">总计 {{ stats.total }}</span>
            <span class="stat pass">通过 {{ stats.passed }}</span>
            <span class="stat fail">失败 {{ stats.failed }}</span>
            <span class="stat block">阻塞 {{ stats.blocked }}</span>
            <span class="stat">跳过 {{ stats.skipped }}</span>
            <span class="stat">未执行 {{ stats.not_run }}</span>
          </div>
          <el-progress
            :percentage="progressPercent"
            :stroke-width="5"
            :show-text="false"
            class="progress-bar"
          />
        </div>

        <div class="run-actions">
          <el-button :disabled="submitting" @click="finishRun">结束执行</el-button>
          <el-button type="primary" @click="goReport">查看报告</el-button>
        </div>
      </header>

      <div class="run-body">
        <!-- 左侧：结果列表 -->
        <aside class="result-side">
          <div class="filter-bar">
            <button
              v-for="item in filters"
              :key="item.value"
              type="button"
              class="filter-btn"
              :class="{ 'is-active': statusFilter === item.value }"
              @click="statusFilter = item.value"
            >
              {{ item.label }}<span class="filter-count">{{ item.count }}</span>
            </button>
          </div>

          <div v-loading="resultsLoading" class="result-list">
            <button
              v-for="item in filteredResults"
              :key="item.id"
              type="button"
              class="result-item"
              :class="{ 'is-active': item.id === currentId }"
              @click="selectResult(item)"
            >
              <span class="result-line">
                <span class="result-key mono">{{ item.case_key }}</span>
                <StatusTag :tone="resultTone(item.status)" :label="resultLabel(item.status)" />
              </span>
              <span class="result-title">{{ item.title }}</span>
            </button>

            <div v-if="!resultsLoading && filteredResults.length === 0" class="state-line">
              没有符合筛选条件的用例
            </div>
            <div v-if="!resultsLoading && results.length === 0" class="state-line">
              该执行轮次暂无结果，请从测试计划开启执行
            </div>
          </div>

          <div class="result-foot">
            <span>{{ executedCount }} / {{ results.length }} 已执行</span>
            <span class="muted">当前 {{ currentIndexLabel }}</span>
          </div>
        </aside>

        <!-- 右侧：当前用例执行面板 -->
        <main v-if="currentResult" class="case-pane">
          <div class="case-scroll">
            <header class="case-head">
              <div class="case-line">
                <span class="case-key mono">{{ currentResult.case_key }}</span>
                <StatusTag
                  :tone="resultTone(currentResult.status)"
                  :label="resultLabel(currentResult.status)"
                />
                <span v-if="currentResult.module" class="muted">{{ currentResult.module }}</span>
              </div>
              <h2 class="case-title">{{ snapshot?.title || currentResult.title }}</h2>
            </header>

            <!-- 版本快照：前置条件 / 步骤 / 上次结果 -->
            <CaseSnapshot
              :snapshot="snapshot"
              :loading="snapshotLoading"
              :result="currentResult"
            />

            <!-- 记录结果 -->
            <section class="record-block">
              <div class="block-title">记录结果</div>
              <div class="record-grid">
                <div class="record-field">
                  <label class="field-label">实际结果</label>
                  <el-input
                    v-model="recordForm.actual_result"
                    type="textarea"
                    :rows="2"
                    placeholder="执行时观察到的实际表现（可选）"
                  />
                </div>
                <div class="record-field">
                  <label class="field-label">备注</label>
                  <el-input
                    v-model="recordForm.comment"
                    type="textarea"
                    :rows="2"
                    placeholder="补充说明（可选）"
                  />
                </div>
                <div class="record-field record-field-short">
                  <label class="field-label">耗时（秒）</label>
                  <el-input v-model="recordForm.duration" type="number" :min="0" placeholder="0" />
                </div>
              </div>
            </section>
          </div>

          <!-- 提交操作条：键盘优先 -->
          <footer class="action-bar">
            <div class="action-btns">
              <button type="button" class="act-btn tone-pass" :disabled="submitting" @click="submit('passed')">
                <kbd>P</kbd>通过
              </button>
              <button type="button" class="act-btn tone-fail" :disabled="submitting" @click="submit('failed')">
                <kbd>F</kbd>失败
              </button>
              <button type="button" class="act-btn tone-block" :disabled="submitting" @click="submit('blocked')">
                <kbd>B</kbd>阻塞
              </button>
              <button type="button" class="act-btn tone-skip" :disabled="submitting" @click="submit('skipped')">
                <kbd>S</kbd>跳过
              </button>
              <button type="button" class="act-btn tone-notrun" :disabled="submitting" @click="submit('not_run')">
                <kbd>N</kbd>未执行
              </button>
            </div>
            <div class="shortcut-hint">快捷键：P 通过 · F 失败 · B 阻塞 · S 跳过 · N 未执行（输入时自动让位）</div>
          </footer>
        </main>

        <main v-else class="case-pane case-pane-empty">
          <el-empty description="请选择左侧用例开始执行" />
        </main>
      </div>
    </template>

    <!-- 加载中占位 -->
    <div v-else v-loading="loading" class="state-box loading-box" />

    <!-- FAIL 弹窗：创建缺陷并关联 -->
    <ResultSubmitDialog
      v-model:visible="failVisible"
      :case-key="currentResult?.case_key || ''"
      :case-title="snapshot?.title || currentResult?.title || ''"
      :environment="run?.environment || ''"
      :build-version="run?.build_version || ''"
      :submitting="submitting"
      @submit="onDefectSubmit"
      @skip="onFailSkip"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, notifyError, type PageResult } from '@/api/client'
import StatusTag from '@/components/ui/StatusTag.vue'
import CaseSnapshot from './executions/CaseSnapshot.vue'
import ResultSubmitDialog from './executions/ResultSubmitDialog.vue'
import type {
  DefectBrief,
  DefectForm,
  ResultStatus,
  RunDetail,
  RunResult,
  VersionSnapshot,
} from './executions/types'

type Tone = 'pass' | 'fail' | 'block' | 'skip' | 'warn' | 'info' | 'neutral' | 'accent'

const RESULT_STATUS: Record<ResultStatus, { label: string; tone: Tone }> = {
  not_run: { label: '未执行', tone: 'neutral' },
  passed: { label: '通过', tone: 'pass' },
  failed: { label: '失败', tone: 'fail' },
  blocked: { label: '阻塞', tone: 'block' },
  skipped: { label: '跳过', tone: 'skip' },
}

const RUN_STATUS: Record<string, { label: string; tone: Tone }> = {
  created: { label: '已创建', tone: 'info' },
  running: { label: '执行中', tone: 'accent' },
  finished: { label: '已完成', tone: 'pass' },
  cancelled: { label: '已取消', tone: 'skip' },
}

function resultLabel(status: ResultStatus): string {
  return RESULT_STATUS[status]?.label ?? status
}
function resultTone(status: ResultStatus): Tone {
  return RESULT_STATUS[status]?.tone ?? 'neutral'
}
function runLabel(status: string): string {
  return RUN_STATUS[status]?.label ?? status
}
function runTone(status: string): Tone {
  return RUN_STATUS[status]?.tone ?? 'neutral'
}

function fmtTime(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.projectId)
const runId = Number(route.params.runId)

const run = ref<RunDetail | null>(null)
const results = ref<RunResult[]>([])
const loading = ref(false)
const resultsLoading = ref(false)
const error = ref('')
const submitting = ref(false)

const statusFilter = ref<'all' | ResultStatus>('all')
const currentId = ref<number | null>(null)

const snapshot = ref<VersionSnapshot | null>(null)
const snapshotLoading = ref(false)
const snapshotCache = new Map<number, VersionSnapshot>()

const failVisible = ref(false)

const recordForm = reactive({
  actual_result: '',
  comment: '',
  duration: '',
})

/* ---------- 统计与列表 ---------- */
const stats = computed(() => {
  const base = { total: 0, not_run: 0, passed: 0, failed: 0, blocked: 0, skipped: 0 }
  results.value.forEach((item) => {
    base[item.status] += 1
  })
  return base
})

const progressPercent = computed(() => {
  const total = stats.value.total
  if (!total) return 0
  return Math.round(((total - stats.value.not_run) / total) * 100)
})

const executedCount = computed(() => stats.value.total - stats.value.not_run)

const filters = computed(() => [
  { value: 'all' as const, label: '全部', count: stats.value.total },
  { value: 'not_run' as const, label: '未执行', count: stats.value.not_run },
  { value: 'passed' as const, label: '通过', count: stats.value.passed },
  { value: 'failed' as const, label: '失败', count: stats.value.failed },
  { value: 'blocked' as const, label: '阻塞', count: stats.value.blocked },
  { value: 'skipped' as const, label: '跳过', count: stats.value.skipped },
])

const filteredResults = computed(() =>
  statusFilter.value === 'all'
    ? results.value
    : results.value.filter((item) => item.status === statusFilter.value),
)

const currentResult = computed(() => results.value.find((item) => item.id === currentId.value) ?? null)

const currentIndexLabel = computed(() => {
  if (!currentResult.value) return '—'
  const index = results.value.findIndex((item) => item.id === currentResult.value?.id)
  return index >= 0 ? `${index + 1} / ${results.value.length}` : '—'
})

/* ---------- 数据加载 ---------- */
async function loadRun() {
  loading.value = true
  error.value = ''
  try {
    const data = await api.get<RunDetail>(`/runs/${runId}/`)
    // URL 中的 projectId 与 Run 实际归属不一致时（手工输入错误 URL），拒绝渲染
    if (data.project !== Number(route.params.projectId)) {
      run.value = null
      error.value = '该执行轮次不属于当前项目'
      return
    }
    run.value = data
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载执行信息失败'
  } finally {
    loading.value = false
  }
}

async function loadResults(preserveSelection = false) {
  resultsLoading.value = true
  try {
    const data = await api.get<PageResult<RunResult>>(`/runs/${runId}/results/`, {
      params: { page_size: 100 },
    })
    results.value = data.items
    if (!preserveSelection || !results.value.some((item) => item.id === currentId.value)) {
      // 默认选中第一条未执行，全部执行完则停在第一条
      const next = results.value.find((item) => item.status === 'not_run') ?? results.value[0] ?? null
      currentId.value = next?.id ?? null
    }
  } catch (e) {
    notifyError(e)
  } finally {
    resultsLoading.value = false
  }
}

function loadAll() {
  loadRun()
  loadResults()
}

/** 版本快照：结果绑定 test_case_version，取版本详情展示（带缓存） */
async function loadSnapshot(versionId: number) {
  const cached = snapshotCache.get(versionId)
  if (cached) {
    snapshot.value = cached
    return
  }
  snapshotLoading.value = true
  snapshot.value = null
  try {
    const data = await api.get<VersionSnapshot>(`/testcase-versions/${versionId}/`)
    snapshotCache.set(versionId, data)
    snapshot.value = data
  } catch (e) {
    notifyError(e)
  } finally {
    snapshotLoading.value = false
  }
}

watch(
  () => currentResult.value?.test_case_version ?? null,
  (versionId) => {
    if (versionId) loadSnapshot(versionId)
    else snapshot.value = null
  },
)

/* 切换用例时回填上次记录，方便在此基础上改 */
watch(currentResult, (item) => {
  recordForm.actual_result = item?.actual_result ?? ''
  recordForm.comment = item?.comment ?? ''
  recordForm.duration = item?.duration ? String(item.duration) : ''
})

function selectResult(item: RunResult) {
  currentId.value = item.id
}

/* ---------- 提交结果 ---------- */
async function submit(status: ResultStatus) {
  if (!currentResult.value || submitting.value) return
  if (status === 'failed') {
    // §34：失败先弹缺陷创建框，可选择仅标记失败
    failVisible.value = true
    return
  }
  await doSubmit(status)
}

async function doSubmit(status: ResultStatus, defectForm?: DefectForm) {
  const item = currentResult.value
  if (!item) return
  submitting.value = true
  try {
    const payload = {
      status,
      actual_result: recordForm.actual_result,
      comment: recordForm.comment,
      duration: Number(recordForm.duration) || 0,
    }
    // 覆盖式提交：同用例再次执行覆盖旧值。
    // POST 仅接受 passed/failed/blocked/skipped；标记未执行走 PATCH 已有结果。
    const saved =
      status === 'not_run'
        ? await api.patch<RunResult>(`/results/${item.id}/`, payload)
        : await api.post<RunResult>(`/runs/${runId}/results/`, {
            test_case_id: item.test_case,
            ...payload,
          })
    const index = results.value.findIndex((row) => row.id === saved.id)
    if (index >= 0) results.value.splice(index, 1, saved)
    failVisible.value = false

    if (defectForm) {
      await createDefect(saved, defectForm)
    } else {
      ElMessage.success(`已记录「${resultLabel(status)}」`)
    }
    advance()
  } catch (e) {
    notifyError(e)
  } finally {
    submitting.value = false
  }
}

/** 先提交 failed 结果，再由结果建缺陷并关联 */
async function createDefect(result: RunResult, defectForm: DefectForm) {
  try {
    const data = await api.post<{ defect: DefectBrief; warning: string | null }>(
      `/results/${result.id}/defects/`,
      {
        title: defectForm.title,
        description: defectForm.description,
        severity: defectForm.severity,
        priority: defectForm.priority,
        comment: defectForm.comment,
      },
    )
    if (data.warning) ElMessage.warning(data.warning)
    try {
      await ElMessageBox.confirm(
        `缺陷 ${data.defect.key}「${data.defect.title}」已创建并关联本条结果。`,
        '缺陷已创建',
        { type: 'success', confirmButtonText: '查看缺陷', cancelButtonText: '继续执行' },
      )
      router.push({ name: 'defect-detail', params: { projectId, defectId: data.defect.id } })
    } catch {
      // 用户选择继续执行
    }
  } catch (e) {
    // 结果已记录为失败，仅缺陷创建失败时提示
    notifyError(e)
  }
}

function onDefectSubmit(payload: DefectForm) {
  doSubmit('failed', payload)
}

function onFailSkip() {
  failVisible.value = false
  doSubmit('failed')
}

/** 提交后自动跳下一条未执行（从当前位置向后找，找不到则回头找） */
function advance() {
  const list = results.value
  const current = list.findIndex((item) => item.id === currentId.value)
  for (let i = current + 1; i < list.length; i += 1) {
    if (list[i].status === 'not_run') {
      currentId.value = list[i].id
      return
    }
  }
  for (let i = 0; i < current; i += 1) {
    if (list[i].status === 'not_run') {
      currentId.value = list[i].id
      return
    }
  }
  ElMessage.info('本轮次用例已全部执行完毕')
}

/* ---------- 顶部出口 ---------- */
function goReport() {
  router.push({ name: 'run-report', params: { projectId, runId } })
}

async function finishRun() {
  try {
    await ElMessageBox.confirm('结束本轮执行并查看测试报告？', '结束执行', {
      confirmButtonText: '结束并查看报告',
      cancelButtonText: '继续执行',
    })
  } catch {
    return
  }
  goReport()
}

/* ---------- 快捷键（§58，仅本页生效） ---------- */
const KEY_MAP: Record<string, ResultStatus> = {
  p: 'passed',
  f: 'failed',
  b: 'blocked',
  s: 'skipped',
  n: 'not_run',
}

/** 输入框 / 文本域 / 弹层聚焦时不触发快捷键 */
function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  const tag = target.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target.isContentEditable
}

function overlayOpen(): boolean {
  return Boolean(document.querySelector('.el-overlay'))
}

function onKeydown(event: KeyboardEvent) {
  if (event.ctrlKey || event.metaKey || event.altKey) return
  if (isTypingTarget(event.target) || overlayOpen() || failVisible.value) return
  const status = KEY_MAP[event.key.toLowerCase()]
  if (!status) return
  event.preventDefault()
  submit(status)
}

onMounted(() => {
  loadAll()
  window.addEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
})
</script>

<style scoped>
.run-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--bg-page);
}

/* ---------- 顶部 Run 信息 ---------- */
.run-top {
  flex: none;
  display: flex;
  align-items: center;
  gap: var(--sp-6);
  padding: var(--sp-3) var(--sp-5);
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-light);
}

.run-ident {
  flex: 1;
  min-width: 0;
}

.run-title-row {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.run-name {
  margin: 0;
  font-size: var(--fs-lg);
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.run-meta {
  display: flex;
  gap: var(--sp-4);
  margin-top: 2px;
  font-size: var(--fs-sm);
  color: var(--text-tertiary);
}

.run-meta b {
  font-weight: 500;
  color: var(--text-secondary);
}

.mono {
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
}

.muted {
  color: var(--text-tertiary);
}

.run-progress {
  flex: none;
  width: 300px;
}

.stat-row {
  display: flex;
  gap: var(--sp-3);
  margin-bottom: var(--sp-2);
  font-size: var(--fs-sm);
  color: var(--text-tertiary);
  white-space: nowrap;
}

.stat.pass {
  color: var(--status-pass);
}

.stat.fail {
  color: var(--status-fail);
}

.stat.block {
  color: var(--status-block);
}

.run-actions {
  flex: none;
  display: flex;
  gap: var(--sp-2);
}

/* ---------- 主体两栏 ---------- */
.run-body {
  flex: 1;
  min-height: 0;
  display: flex;
}

.result-side {
  width: 300px;
  flex: none;
  display: flex;
  flex-direction: column;
  background: var(--bg-surface);
  border-right: 1px solid var(--border-light);
}

.filter-bar {
  flex: none;
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-1);
  padding: var(--sp-2) var(--sp-3);
  border-bottom: 1px solid var(--border-light);
}

.filter-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  background: none;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  font-family: inherit;
  font-size: var(--fs-sm);
  color: var(--text-tertiary);
  cursor: pointer;
  transition: background-color var(--dur-fast) var(--ease-out),
    color var(--dur-fast) var(--ease-out);
}

.filter-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.filter-btn.is-active {
  background: var(--accent-50);
  border-color: var(--accent-100);
  color: var(--accent-600);
  font-weight: 500;
}

.filter-count {
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
}

.result-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: var(--sp-1) 0;
}

.result-item {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--sp-2) var(--sp-3);
  background: none;
  border: none;
  border-left: 2px solid transparent;
  text-align: left;
  cursor: pointer;
  font-family: inherit;
  transition: background-color var(--dur-fast) var(--ease-out);
}

.result-item:hover {
  background: var(--bg-hover);
}

.result-item.is-active {
  background: var(--accent-50);
  border-left-color: var(--accent-600);
}

.result-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
}

.result-key {
  color: var(--text-secondary);
}

.result-item.is-active .result-key {
  color: var(--accent-600);
  font-weight: 600;
}

.result-title {
  font-size: var(--fs-sm);
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.result-foot {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--sp-2) var(--sp-3);
  border-top: 1px solid var(--border-light);
  font-size: var(--fs-sm);
  color: var(--text-secondary);
}

.state-line {
  padding: var(--sp-5) var(--sp-3);
  font-size: var(--fs-sm);
  color: var(--text-tertiary);
  text-align: center;
}

/* ---------- 右侧执行面板 ---------- */
.case-pane {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-surface);
}

.case-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: var(--sp-5) var(--sp-6);
  display: flex;
  flex-direction: column;
  gap: var(--sp-5);
}

.case-pane-empty {
  align-items: center;
  justify-content: center;
}

.case-line {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.case-key {
  color: var(--accent-600);
  font-weight: 600;
}

.case-title {
  margin: var(--sp-1) 0 0;
  font-size: var(--fs-xl);
  font-weight: 600;
  line-height: var(--lh-tight);
  color: var(--text-primary);
}

.record-block {
  border-top: 1px solid var(--border-light);
  padding-top: var(--sp-4);
}

.block-title {
  margin-bottom: var(--sp-2);
  font-size: var(--fs-xs);
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--text-tertiary);
}

.record-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 140px;
  gap: var(--sp-3);
}

.field-label {
  display: block;
  margin-bottom: var(--sp-1);
  font-size: var(--fs-sm);
  color: var(--text-secondary);
}

/* ---------- 提交操作条 ---------- */
.action-bar {
  flex: none;
  border-top: 1px solid var(--border-light);
  padding: var(--sp-3) var(--sp-6);
  background: var(--bg-surface);
}

.action-btns {
  display: flex;
  gap: var(--sp-2);
}

.act-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-2);
  padding: 6px 14px;
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  font-family: inherit;
  font-size: var(--fs-base);
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background-color var(--dur-fast) var(--ease-out),
    border-color var(--dur-fast) var(--ease-out),
    color var(--dur-fast) var(--ease-out);
}

.act-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.act-btn kbd {
  min-width: 16px;
  padding: 0 3px;
  border: 1px solid var(--border-default);
  border-radius: 3px;
  background: var(--bg-sunken);
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
  line-height: 16px;
  text-align: center;
  color: var(--text-tertiary);
}

.tone-pass {
  color: var(--status-pass);
}
.tone-pass:hover:not(:disabled) {
  background: var(--success-50);
  border-color: var(--status-pass);
}

.tone-fail {
  color: var(--status-fail);
}
.tone-fail:hover:not(:disabled) {
  background: var(--danger-50);
  border-color: var(--status-fail);
}

.tone-block {
  color: var(--status-block);
}
.tone-block:hover:not(:disabled) {
  background: var(--warning-50);
  border-color: var(--status-block);
}

.tone-skip,
.tone-notrun {
  color: var(--text-tertiary);
}
.tone-skip:hover:not(:disabled),
.tone-notrun:hover:not(:disabled) {
  background: var(--bg-sunken);
  border-color: var(--border-strong);
}

.shortcut-hint {
  margin-top: var(--sp-2);
  font-size: var(--fs-xs);
  color: var(--text-placeholder);
}

/* ---------- 状态 ---------- */
.state-box {
  margin: auto;
  padding: var(--sp-10);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-3);
}

.state-text {
  margin: 0;
  color: var(--text-tertiary);
}

.loading-box {
  min-height: 320px;
  width: 100%;
}
</style>
