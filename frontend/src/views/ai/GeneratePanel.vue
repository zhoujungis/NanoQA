<template>
  <section class="panel">
    <div class="panel-head">
      <div class="panel-head-main">
        <h2 class="panel-title">生成用例草案</h2>
        <p class="panel-desc">输入需求信息，AI 产出结构化用例草案；草案仅存在于 AI 任务记录中，需人工审核入库后才进入正式用例库</p>
      </div>
      <StatusTag v-if="draftTask" :tone="draftStatus.tone" :label="draftStatus.label" />
    </div>

    <div class="panel-body">
      <!-- 左：生成表单 -->
      <div class="gen-form">
        <div class="field">
          <label class="field-label">需求描述 / 标题</label>
          <el-input
            v-model="form.titleHint"
            type="textarea"
            :rows="4"
            maxlength="255"
            show-word-limit
            placeholder="一句话描述要覆盖的功能，如：购物车结算与优惠券抵扣"
          />
        </div>

        <div class="field">
          <label class="field-label">关联需求（可选）</label>
          <el-select
            v-model="form.requirementId"
            class="field-control"
            clearable
            filterable
            placeholder="选择需求后按需求描述生成"
          >
            <el-option
              v-for="item in requirements"
              :key="item.id"
              :label="`${item.key} ${item.title}`"
              :value="item.id"
            />
          </el-select>
        </div>

        <div class="field">
          <label class="field-label">生成数量</label>
          <el-input-number v-model="form.count" :min="1" :max="50" class="field-control" />
        </div>

        <div class="field">
          <label class="field-label">覆盖范围</label>
          <div class="checks">
            <el-checkbox v-model="form.includeEdgeCases">边界场景</el-checkbox>
            <el-checkbox v-model="form.includeSecurity">安全场景</el-checkbox>
            <el-checkbox v-model="form.includeCompatibility">兼容场景</el-checkbox>
          </div>
        </div>

        <el-button type="primary" class="generate-btn" :loading="generating" @click="submitGenerate">
          生成用例草案
        </el-button>
        <p class="form-hint">AI 输出只是草案，不会自动写入正式用例库；请在右侧逐条审核。</p>
      </div>

      <!-- 右：结构化草案预览 -->
      <div class="gen-preview">
        <!-- 空态 -->
        <div v-if="!drafts.length && !generateError" class="preview-state">
          <p class="state-title">尚未生成草案</p>
          <p class="state-text">
            填写左侧需求信息后点击「生成用例草案」，结果会以可编辑的结构化草案展示在这里，支持逐条修改、删除与勾选入库。
          </p>
        </div>

        <!-- 错误态 -->
        <div v-else-if="generateError && !drafts.length" class="preview-state">
          <p class="state-title">生成失败</p>
          <p class="state-text">{{ generateError }}</p>
          <el-button size="small" type="primary" plain @click="submitGenerate">重试</el-button>
        </div>

        <!-- 草案区 -->
        <template v-else>
          <div class="preview-bar">
            <div class="bar-left">
              <el-checkbox
                :model-value="allSelected"
                :indeterminate="someSelected"
                :disabled="locked"
                @change="toggleAll"
              >
                全选
              </el-checkbox>
              <span class="bar-count">已选 {{ selectedCount }} / {{ drafts.length }} 条</span>
              <span class="bar-meta">任务 #{{ draftTask?.id }}</span>
            </div>
            <div class="bar-right">
              <el-tooltip :disabled="!selectedDisabledReason" :content="selectedDisabledReason" placement="top">
                <span class="tip-wrap">
                  <el-button
                    type="primary"
                    plain
                    :disabled="Boolean(selectedDisabledReason)"
                    :loading="acceptingSelected"
                    @click="acceptSelected"
                  >
                    入库所选（逐条）
                  </el-button>
                </span>
              </el-tooltip>
              <el-tooltip :disabled="!wholeDisabledReason" :content="wholeDisabledReason" placement="top">
                <span class="tip-wrap">
                  <el-button
                    type="primary"
                    :disabled="Boolean(wholeDisabledReason)"
                    :loading="acceptingAll"
                    @click="acceptAll"
                  >
                    整单入库（全部）
                  </el-button>
                </span>
              </el-tooltip>
              <el-tooltip :disabled="!rejectDisabledReason" :content="rejectDisabledReason" placement="top">
                <span class="tip-wrap">
                  <el-button :disabled="Boolean(rejectDisabledReason)" :loading="rejecting" @click="rejectDraft">
                    丢弃草案
                  </el-button>
                </span>
              </el-tooltip>
            </div>
          </div>

          <!-- 审核结果提示条 -->
          <div v-if="reviewState === 'accepted'" class="preview-banner tone-pass">
            该草案已审核入库，共 {{ resultCases.length }} 条正式用例；如需调整请在用例管理中修改。
          </div>
          <div v-else-if="reviewState === 'rejected'" class="preview-banner tone-muted">
            该草案已丢弃，不会写入正式用例库，仅保留 AI 任务记录。
          </div>
          <div v-else class="preview-banner tone-review">
            草案待人工审核：「入库所选」按当前编辑内容逐条写入，「整单入库」按 AI 原始输出一次性写入，「丢弃」仅保留任务记录。
          </div>

          <div class="draft-list">
            <DraftCaseCard
              v-for="(draft, index) in drafts"
              :key="draft.uid"
              :draft="draft"
              :index="index"
              :locked="locked"
              :busy="acceptingSelected"
              @update:selected="(value) => (draft.selected = value)"
              @change="markDirty"
              @remove="removeDraft(draft.uid)"
              @accept-one="acceptOne(draft)"
              @open-case="goCase"
            />
          </div>
        </template>
      </div>
    </div>

    <AcceptedCasesDialog v-model="resultVisible" :cases="resultCases" />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, notifyError, type PageResult } from '@/api/client'
import StatusTag from '@/components/ui/StatusTag.vue'
import AcceptedCasesDialog from './AcceptedCasesDialog.vue'
import DraftCaseCard from './DraftCaseCard.vue'
import {
  toDrafts,
  validateDraft,
  toCasePayload,
  type AcceptedCase,
  type AiGeneratedCase,
  type CaseDraft,
  type GenerateForm,
  type RequirementBrief,
  type Tone,
} from './shared'

const props = defineProps<{
  /** 当前项目 id（路由参数） */
  projectId: number
}>()

const emit = defineEmits<{
  /** 任务记录变化（生成 / 入库 / 丢弃）后通知父组件刷新任务列表 */
  (e: 'changed'): void
  /** 逐条入库发生后通知父组件记录任务 id，避免任务列表重复入库 */
  (e: 'manual-accepted', taskId: number): void
}>()

const router = useRouter()

/* ---------------- 生成表单 ---------------- */
const form = reactive<GenerateForm>({
  titleHint: '',
  requirementId: null,
  count: 10,
  includeEdgeCases: true,
  includeSecurity: false,
  includeCompatibility: false,
})

const requirements = ref<RequirementBrief[]>([])

async function fetchRequirements() {
  try {
    const data = await api.get<PageResult<RequirementBrief>>(`/projects/${props.projectId}/requirements/`, {
      params: { page_size: 100 },
    })
    requirements.value = data.items.map((item) => ({ id: item.id, key: item.key, title: item.title }))
  } catch {
    // 需求下拉缺失不阻塞主流程，静默降级
  }
}

/* ---------------- 草案状态 ---------------- */
const generating = ref(false)
const generateError = ref<string | null>(null)
const drafts = ref<CaseDraft[]>([])
const draftTask = ref<{ id: number; status: string } | null>(null)
const reviewState = ref<'pending' | 'accepted' | 'rejected'>('pending')
const dirty = ref(false)
const removed = ref(false)

const acceptingSelected = ref(false)
const acceptingAll = ref(false)
const rejecting = ref(false)

const resultVisible = ref(false)
const resultCases = ref<AcceptedCase[]>([])

const locked = computed(() => reviewState.value !== 'pending')
const selectedCount = computed(() => drafts.value.filter((item) => item.selected && !item.caseKey).length)
const allSelected = computed(
  () => drafts.value.length > 0 && drafts.value.every((item) => item.selected || item.caseKey),
)
const someSelected = computed(() => selectedCount.value > 0 && !allSelected.value)

const draftStatus = computed<{ label: string; tone: Tone }>(() => {
  if (reviewState.value === 'accepted') return { label: '已入库', tone: 'pass' }
  if (reviewState.value === 'rejected') return { label: '已丢弃', tone: 'neutral' }
  return { label: '待审核', tone: 'warn' }
})

const selectedDisabledReason = computed(() => {
  if (reviewState.value === 'accepted') return '该草案已整单入库，请勿重复入库'
  if (reviewState.value === 'rejected') return '该草案已丢弃，无法入库'
  if (!selectedCount.value) return '请先勾选需要入库的草案'
  return ''
})

const wholeDisabledReason = computed(() => {
  if (reviewState.value !== 'pending') return '该草案已审核处理，无法再次整单入库'
  if (drafts.value.some((item) => item.caseKey)) return '已有逐条入库的用例，整单入库会造成重复'
  if (dirty.value || removed.value) return '本地已编辑或删除草案，整单入库会按 AI 原始输出写入，请改用「入库所选」'
  return ''
})

const rejectDisabledReason = computed(() => {
  if (reviewState.value !== 'pending') return '该草案已审核处理'
  if (drafts.value.some((item) => item.caseKey)) return '已有逐条入库的用例，无法整体丢弃'
  return ''
})

function markDirty() {
  dirty.value = true
}

function toggleAll(value: string | number | boolean) {
  const checked = Boolean(value)
  drafts.value.forEach((item) => {
    if (!item.caseKey) item.selected = checked
  })
}

function removeDraft(uid: number) {
  const index = drafts.value.findIndex((item) => item.uid === uid)
  if (index >= 0) {
    drafts.value.splice(index, 1)
    removed.value = true
    dirty.value = true
  }
}

/* ---------------- 生成 ---------------- */
async function submitGenerate() {
  const titleHint = form.titleHint.trim()
  if (!titleHint && !form.requirementId) {
    ElMessage.warning('请填写需求描述，或选择一个关联需求')
    return
  }
  generating.value = true
  generateError.value = null
  try {
    const data = await api.post<{ task_id: number; status: string; cases: AiGeneratedCase[] }>(
      '/ai/testcases/generate/',
      {
        project_id: props.projectId,
        requirement_id: form.requirementId ?? undefined,
        title_hint: titleHint || undefined,
        count: form.count,
        include_edge_cases: form.includeEdgeCases,
        include_security: form.includeSecurity,
        include_compatibility: form.includeCompatibility,
      },
    )
    drafts.value = toDrafts(data.cases ?? [])
    draftTask.value = { id: data.task_id, status: data.status }
    reviewState.value = 'pending'
    dirty.value = false
    removed.value = false
    resultCases.value = []
    ElMessage.success(`已生成 ${drafts.value.length} 条用例草案，请逐条审核`)
    emit('changed')
  } catch (err) {
    generateError.value = err instanceof Error ? err.message : '生成失败，请稍后重试'
  } finally {
    generating.value = false
  }
}

/* ---------------- 入库 / 丢弃 ---------------- */
function collectInvalid(list: CaseDraft[]): string[] {
  const errors: string[] = []
  list.forEach((draft) => {
    const message = validateDraft(draft)
    if (message) {
      draft.invalid = true
      errors.push(`第 ${drafts.value.indexOf(draft) + 1} 条：${message}`)
    } else {
      draft.invalid = false
    }
  })
  return errors
}

async function createCase(draft: CaseDraft) {
  const created = await api.post<AcceptedCase>(`/projects/${props.projectId}/testcases/`, toCasePayload(draft))
  draft.caseId = created.id
  draft.caseKey = created.case_key
  draft.selected = false
  return created
}

async function acceptDrafts(list: CaseDraft[], tip: string) {
  const errors = collectInvalid(list)
  if (errors.length) {
    ElMessage.warning(errors[0] + (errors.length > 1 ? `（共 ${errors.length} 处待修正）` : ''))
    return
  }
  try {
    await ElMessageBox.confirm(tip, '审核入库', {
      type: 'warning',
      confirmButtonText: '确认入库',
      cancelButtonText: '再看看',
    })
  } catch {
    return
  }

  acceptingSelected.value = true
  const created: AcceptedCase[] = []
  let failed = 0
  for (const draft of list) {
    try {
      created.push(await createCase(draft))
    } catch (err) {
      failed += 1
      notifyError(err)
    }
  }
  acceptingSelected.value = false

  if (created.length) {
    resultCases.value = created
    resultVisible.value = true
    ElMessage.success(`已审核入库 ${created.length} 条` + (failed ? `，失败 ${failed} 条` : ''))
    if (draftTask.value) emit('manual-accepted', draftTask.value.id)
    emit('changed')
  }
}

function acceptSelected() {
  const list = drafts.value.filter((item) => item.selected && !item.caseKey)
  acceptDrafts(
    list,
    `将把勾选的 ${list.length} 条草案按当前编辑内容逐条写入正式用例库（初始状态为「草稿」），确认继续？`,
  )
}

function acceptOne(draft: CaseDraft) {
  acceptDrafts([draft], '将把这条草案按当前编辑内容写入正式用例库（初始状态为「草稿」），确认继续？')
}

async function acceptAll() {
  if (!draftTask.value) return
  try {
    await ElMessageBox.confirm(
      `将按 AI 原始输出一次性写入 ${drafts.value.length} 条正式用例（不含本地修改），确认继续？`,
      '整单入库',
      { type: 'warning', confirmButtonText: '确认入库', cancelButtonText: '再看看' },
    )
  } catch {
    return
  }

  acceptingAll.value = true
  try {
    const data = await api.post<{ task_id: number; cases: AcceptedCase[] }>(
      `/ai/tasks/${draftTask.value.id}/accept/`,
    )
    reviewState.value = 'accepted'
    resultCases.value = data.cases
    resultVisible.value = true
    // 与 AI 原始输出顺序一致，按序回填入库信息
    data.cases.forEach((item, index) => {
      const draft = drafts.value[index]
      if (draft && data.cases.length === drafts.value.length) {
        draft.caseId = item.id
        draft.caseKey = item.case_key
        draft.selected = false
      }
    })
    ElMessage.success(`已审核入库 ${data.cases.length} 条正式用例`)
    emit('changed')
  } catch (err) {
    notifyError(err)
  } finally {
    acceptingAll.value = false
  }
}

async function rejectDraft() {
  if (!draftTask.value) return
  try {
    await ElMessageBox.confirm('丢弃后 AI 草案不会写入正式用例库，仅保留任务记录，确认丢弃？', '丢弃草案', {
      type: 'warning',
      confirmButtonText: '确认丢弃',
      cancelButtonText: '再看看',
    })
  } catch {
    return
  }

  rejecting.value = true
  try {
    await api.post(`/ai/tasks/${draftTask.value.id}/reject/`)
    reviewState.value = 'rejected'
    ElMessage.success('草案已丢弃，仅保留 AI 任务记录')
    emit('changed')
  } catch (err) {
    notifyError(err)
  } finally {
    rejecting.value = false
  }
}

function goCase(caseId: number | null) {
  if (!caseId) return
  router.push({ name: 'testcase-detail', params: { projectId: props.projectId, caseId } })
}

onMounted(() => {
  fetchRequirements()
})
</script>

<style scoped>
.panel {
  background: var(--bg-surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  margin-bottom: var(--sp-5);
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--sp-4);
  padding: var(--sp-4) var(--sp-5);
  border-bottom: 1px solid var(--border-light);
}

.panel-title {
  margin: 0;
  font-size: var(--fs-lg);
  font-weight: 600;
  line-height: var(--lh-tight);
}

.panel-desc {
  margin: var(--sp-1) 0 0;
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
}

.panel-body {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: var(--sp-5);
  padding: var(--sp-4) var(--sp-5) var(--sp-5);
}

/* ---------- 左侧表单 ---------- */
.gen-form {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  border-right: 1px solid var(--border-light);
  padding-right: var(--sp-5);
}

.field {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}

.field-label {
  color: var(--text-secondary);
  font-size: var(--fs-sm);
  font-weight: 500;
}

.field-control {
  width: 100%;
}

.checks {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-1) var(--sp-3);
}

.generate-btn {
  width: 100%;
  margin-top: var(--sp-1);
}

.form-hint {
  margin: 0;
  color: var(--text-placeholder);
  font-size: var(--fs-xs);
  line-height: var(--lh-base);
}

/* ---------- 右侧草案预览 ---------- */
.gen-preview {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.preview-state {
  flex: 1;
  min-height: 220px;
  border: 1px dashed var(--border-default);
  border-radius: var(--radius-md);
  background: var(--bg-sunken);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--sp-2);
  padding: var(--sp-6);
  text-align: center;
}

.state-title {
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--fs-md);
  font-weight: 600;
}

.state-text {
  margin: 0;
  max-width: 420px;
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
}

.preview-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  flex-wrap: wrap;
}

.bar-left {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
}

.bar-count {
  color: var(--text-secondary);
  font-size: var(--fs-sm);
  font-variant-numeric: tabular-nums;
}

.bar-meta {
  color: var(--text-placeholder);
  font-size: var(--fs-xs);
  font-family: var(--font-mono);
}

.bar-right {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.tip-wrap {
  display: inline-flex;
}

.preview-banner {
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-sm);
  font-size: var(--fs-sm);
  line-height: var(--lh-base);
}

.tone-review {
  background: var(--accent-50);
  border-left: 3px solid var(--accent-600);
  color: var(--text-secondary);
}

.tone-pass {
  background: var(--success-50);
  border-left: 3px solid var(--success-600);
  color: var(--text-secondary);
}

.tone-muted {
  background: var(--bg-sunken);
  border-left: 3px solid var(--border-strong);
  color: var(--text-tertiary);
}

.draft-list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}
</style>
