<template>
  <section class="panel">
    <div class="panel-head">
      <div class="panel-head-main">
        <h2 class="panel-title">辅助能力</h2>
        <p class="panel-desc">评审、重复检测与需求分析的输出同样只作参考建议，不会改动正式用例库数据</p>
      </div>
    </div>

    <div class="tool-grid">
      <!-- 用例评审 -->
      <div class="tool-card">
        <div class="tool-head">
          <h3 class="tool-title">用例评审</h3>
          <p class="tool-desc">从覆盖度、预期结果、前置条件等角度对已有用例打分并给出问题清单</p>
        </div>
        <el-select v-model="reviewCaseId" class="tool-control" clearable filterable placeholder="选择要评审的用例">
          <el-option v-for="item in caseOptions" :key="item.id" :label="`${item.case_key} ${item.title}`" :value="item.id" />
        </el-select>
        <el-button type="primary" plain :loading="reviewLoading" @click="runReview">开始评审</el-button>

        <div class="tool-result">
          <p v-if="reviewError" class="result-error">{{ reviewError }}</p>
          <template v-else-if="reviewResult">
            <div class="score-row">
              <span class="score-value" :class="scoreClass(reviewResult.score)">{{ reviewResult.score }}</span>
              <span class="score-label">评审得分</span>
            </div>
            <p class="result-hint">问题（{{ reviewResult.issues.length }}）</p>
            <ul class="result-list">
              <li v-for="(issue, index) in reviewResult.issues" :key="index" class="result-row">
                <StatusTag :tone="levelTone(issue.severity)" :label="levelLabel(issue.severity)" />
                <span>{{ issue.message }}</span>
              </li>
              <li v-if="!reviewResult.issues.length" class="result-empty">未发现问题</li>
            </ul>
            <p class="result-hint">改进建议（{{ reviewResult.suggestions.length }}）</p>
            <ul class="result-list">
              <li v-for="(item, index) in reviewResult.suggestions" :key="index">{{ item }}</li>
              <li v-if="!reviewResult.suggestions.length" class="result-empty">暂无建议</li>
            </ul>
          </template>
          <p v-else class="result-idle">选择用例后点击「开始评审」，结果只读、不改动用例数据。</p>
        </div>
      </div>

      <!-- 重复用例检测 -->
      <div class="tool-card">
        <div class="tool-head">
          <h3 class="tool-title">重复用例检测</h3>
          <p class="tool-desc">基于标题与步骤文本相似度，找出项目内可能重复的用例对，建议人工合并</p>
        </div>
        <div class="tool-plain">
          <span class="plain-text">检测范围：当前项目全部用例（相似度阈值 60%）</span>
        </div>
        <el-button type="primary" plain :loading="duplicateLoading" @click="runDetect">开始检测</el-button>

        <div class="tool-result">
          <p v-if="duplicateError" class="result-error">{{ duplicateError }}</p>
          <template v-else-if="duplicatePairs">
            <p class="result-hint">相似用例对 {{ duplicatePairs.length }}</p>
            <ul class="result-list">
              <li v-for="(pair, index) in duplicatePairs" :key="index" class="result-row pair-row">
                <el-button link type="primary" size="small" @click="goCase(pair.case_a)">用例 #{{ pair.case_a }}</el-button>
                <span class="pair-mark">↔</span>
                <el-button link type="primary" size="small" @click="goCase(pair.case_b)">用例 #{{ pair.case_b }}</el-button>
                <span class="pair-similarity">{{ (pair.similarity * 100).toFixed(0) }}%</span>
              </li>
              <li v-if="!duplicatePairs.length" class="result-empty">未发现相似用例对</li>
            </ul>
          </template>
          <p v-else class="result-idle">点击「开始检测」，检测结果只读，是否合并由人工决定。</p>
        </div>
      </div>

      <!-- 需求分析 -->
      <div class="tool-card">
        <div class="tool-head">
          <h3 class="tool-title">需求分析</h3>
          <p class="tool-desc">输出需求摘要、风险提示与建议用例，为生成草案提供参考</p>
        </div>
        <el-select v-model="analyzeReqId" class="tool-control" clearable filterable placeholder="选择要分析的需求">
          <el-option v-for="item in requirementOptions" :key="item.id" :label="`${item.key} ${item.title}`" :value="item.id" />
        </el-select>
        <el-button type="primary" plain :loading="analyzeLoading" @click="runAnalyze">开始分析</el-button>

        <div class="tool-result">
          <p v-if="analyzeError" class="result-error">{{ analyzeError }}</p>
          <template v-else-if="analyzeResult">
            <p class="result-hint">分析摘要</p>
            <p class="result-summary">{{ analyzeResult.summary }}</p>
            <p class="result-hint">风险提示（{{ analyzeResult.risks.length }}）</p>
            <ul class="result-list">
              <li v-for="(risk, index) in analyzeResult.risks" :key="index" class="result-row">
                <StatusTag :tone="levelTone(risk.level)" :label="levelLabel(risk.level)" />
                <span>{{ risk.message }}</span>
              </li>
              <li v-if="!analyzeResult.risks.length" class="result-empty">暂无风险提示</li>
            </ul>
            <p class="result-hint">建议用例（{{ analyzeResult.suggested_cases.length }}）</p>
            <ul class="result-list">
              <li v-for="(item, index) in analyzeResult.suggested_cases" :key="index">{{ item.title }}</li>
            </ul>
          </template>
          <p v-else class="result-idle">选择需求后点击「开始分析」，分析结果不会写入需求或用例。</p>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api, type PageResult } from '@/api/client'
import StatusTag from '@/components/ui/StatusTag.vue'
import {
  levelLabel,
  levelTone,
  type AiGeneratedCase,
  type CaseBrief,
  type DuplicatePair,
  type RequirementBrief,
} from './shared'

const props = defineProps<{
  /** 当前项目 id（路由参数） */
  projectId: number
}>()

const emit = defineEmits<{
  /** AI 任务落库后通知父组件刷新任务记录 */
  (e: 'changed'): void
}>()

const router = useRouter()

/* ---------------- 候选数据 ---------------- */
const caseOptions = ref<CaseBrief[]>([])
const requirementOptions = ref<RequirementBrief[]>([])

async function fetchOptions() {
  try {
    const data = await api.get<PageResult<CaseBrief>>(`/projects/${props.projectId}/testcases/`, {
      params: { page_size: 100 },
    })
    caseOptions.value = data.items.map((item) => ({ id: item.id, case_key: item.case_key, title: item.title }))
  } catch {
    // 候选缺失时下拉为空，不影响其他工具
  }
  try {
    const data = await api.get<PageResult<RequirementBrief>>(`/projects/${props.projectId}/requirements/`, {
      params: { page_size: 100 },
    })
    requirementOptions.value = data.items.map((item) => ({ id: item.id, key: item.key, title: item.title }))
  } catch {
    // 同上，静默降级
  }
}

/* ---------------- 用例评审 ---------------- */
interface ReviewResult {
  score: number
  issues: { severity: string; message: string }[]
  suggestions: string[]
}

const reviewCaseId = ref<number | null>(null)
const reviewLoading = ref(false)
const reviewError = ref<string | null>(null)
const reviewResult = ref<ReviewResult | null>(null)

function scoreClass(score: number): string {
  if (score >= 85) return 'tone-pass'
  if (score >= 60) return 'tone-warn'
  return 'tone-fail'
}

async function runReview() {
  if (!reviewCaseId.value) {
    ElMessage.warning('请先选择要评审的用例')
    return
  }
  reviewLoading.value = true
  reviewError.value = null
  try {
    const data = await api.post<ReviewResult>(`/ai/testcases/${reviewCaseId.value}/review/`)
    reviewResult.value = { score: data.score, issues: data.issues ?? [], suggestions: data.suggestions ?? [] }
    emit('changed')
  } catch (err) {
    reviewResult.value = null
    reviewError.value = err instanceof Error ? err.message : '评审失败，请稍后重试'
  } finally {
    reviewLoading.value = false
  }
}

/* ---------------- 重复用例检测 ---------------- */
const duplicateLoading = ref(false)
const duplicateError = ref<string | null>(null)
const duplicatePairs = ref<DuplicatePair[] | null>(null)

async function runDetect() {
  duplicateLoading.value = true
  duplicateError.value = null
  try {
    const data = await api.post<{ pairs: DuplicatePair[] }>('/ai/testcases/detect-duplicates/', {
      project_id: props.projectId,
    })
    duplicatePairs.value = data.pairs ?? []
    emit('changed')
  } catch (err) {
    duplicatePairs.value = null
    duplicateError.value = err instanceof Error ? err.message : '检测失败，请稍后重试'
  } finally {
    duplicateLoading.value = false
  }
}

/* ---------------- 需求分析 ---------------- */
interface AnalyzeResult {
  summary: string
  suggested_cases: AiGeneratedCase[]
  risks: { level: string; message: string }[]
}

const analyzeReqId = ref<number | null>(null)
const analyzeLoading = ref(false)
const analyzeError = ref<string | null>(null)
const analyzeResult = ref<AnalyzeResult | null>(null)

async function runAnalyze() {
  if (!analyzeReqId.value) {
    ElMessage.warning('请先选择要分析的需求')
    return
  }
  analyzeLoading.value = true
  analyzeError.value = null
  try {
    const data = await api.post<AnalyzeResult>(`/ai/requirements/${analyzeReqId.value}/analyze/`)
    analyzeResult.value = {
      summary: data.summary ?? '',
      suggested_cases: data.suggested_cases ?? [],
      risks: data.risks ?? [],
    }
    emit('changed')
  } catch (err) {
    analyzeResult.value = null
    analyzeError.value = err instanceof Error ? err.message : '分析失败，请稍后重试'
  } finally {
    analyzeLoading.value = false
  }
}

function goCase(caseId: number) {
  router.push({ name: 'testcase-detail', params: { projectId: props.projectId, caseId } })
}

onMounted(() => {
  fetchOptions()
})
</script>

<style scoped>
.panel {
  background: var(--bg-surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  margin-bottom: var(--sp-6);
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

.tool-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--sp-4);
  padding: var(--sp-4) var(--sp-5) var(--sp-5);
}

.tool-card {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  padding: var(--sp-3) var(--sp-4) var(--sp-4);
  min-width: 0;
}

.tool-head {
  margin-bottom: var(--sp-1);
}

.tool-title {
  margin: 0;
  font-size: var(--fs-md);
  font-weight: 600;
}

.tool-desc {
  margin: var(--sp-1) 0 0;
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
  line-height: var(--lh-base);
}

.tool-control {
  width: 100%;
}

.tool-plain {
  display: flex;
  align-items: center;
  min-height: 32px;
}

.plain-text {
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
}

.tool-result {
  margin-top: var(--sp-2);
  border-top: 1px dashed var(--border-light);
  padding-top: var(--sp-2);
  min-height: 120px;
}

.result-idle {
  margin: 0;
  color: var(--text-placeholder);
  font-size: var(--fs-sm);
  line-height: var(--lh-base);
}

.result-error {
  margin: 0;
  color: var(--danger-600);
  font-size: var(--fs-sm);
}

.result-hint {
  margin: var(--sp-2) 0 var(--sp-1);
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
  font-weight: 500;
}

.result-list {
  margin: 0;
  padding-left: var(--sp-4);
  color: var(--text-secondary);
  font-size: var(--fs-sm);
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}

.result-row {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.result-empty {
  list-style: none;
  margin-left: calc(var(--sp-4) * -1);
  color: var(--text-placeholder);
}

.result-summary {
  margin: 0;
  padding: var(--sp-2) var(--sp-3);
  background: var(--bg-sunken);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: var(--fs-sm);
  line-height: var(--lh-base);
}

.score-row {
  display: flex;
  align-items: baseline;
  gap: var(--sp-2);
}

.score-value {
  font-size: var(--fs-2xl);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.score-value.tone-pass {
  color: var(--success-600);
}
.score-value.tone-warn {
  color: var(--warning-600);
}
.score-value.tone-fail {
  color: var(--danger-600);
}

.score-label {
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
}

.pair-row {
  display: flex;
  align-items: center;
  gap: var(--sp-1);
}

.pair-mark {
  color: var(--text-placeholder);
}

.pair-similarity {
  margin-left: var(--sp-1);
  color: var(--accent-600);
  font-variant-numeric: tabular-nums;
}

@media (max-width: 1280px) {
  .tool-grid {
    grid-template-columns: 1fr;
  }
}
</style>
