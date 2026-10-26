<template>
  <article class="draft-card" :class="{ 'is-invalid': draft.invalid, 'is-locked': locked }">
    <div class="card-head">
      <el-checkbox
        v-if="!locked && !draft.caseKey"
        :model-value="draft.selected"
        :disabled="locked"
        @change="onSelect"
      />
      <span class="card-index">{{ String(index + 1).padStart(2, '0') }}</span>
      <el-input
        v-model="draft.title"
        class="card-title"
        maxlength="255"
        placeholder="用例标题"
        :disabled="locked"
        @input="onChange"
      />
      <el-select v-model="draft.priority" class="card-select" :disabled="locked" @change="onChange">
        <el-option v-for="item in PRIORITY_OPTIONS" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <el-select v-model="draft.caseType" class="card-select card-type" :disabled="locked" @change="onChange">
        <el-option v-for="item in CASE_TYPE_OPTIONS" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <StatusTag v-if="draft.caseKey" tone="pass" :label="`已入库 ${draft.caseKey}`" />
      <el-button
        v-else-if="!locked"
        link
        type="danger"
        size="small"
        class="card-remove"
        @click="emit('remove')"
      >
        移除
      </el-button>
    </div>

    <div class="card-row">
      <span class="row-label">前置条件</span>
      <el-input
        v-model="draft.precondition"
        :disabled="locked"
        placeholder="执行前需要满足的条件，可留空"
        @input="onChange"
      />
    </div>

    <div class="card-steps">
      <div class="steps-head">
        <span class="row-label">测试步骤</span>
        <el-button v-if="!locked" link size="small" @click="addStep">添加步骤</el-button>
      </div>
      <div v-for="(step, stepIndex) in draft.steps" :key="stepIndex" class="step-row">
        <span class="step-order">{{ stepIndex + 1 }}</span>
        <el-input
          v-model="step.action"
          class="step-input"
          :disabled="locked"
          placeholder="操作动作"
          @input="onChange"
        />
        <span class="step-arrow">→</span>
        <el-input
          v-model="step.expected"
          class="step-input"
          :disabled="locked"
          placeholder="预期结果"
          @input="onChange"
        />
        <el-button
          v-if="!locked"
          link
          type="danger"
          size="small"
          class="step-remove"
          :disabled="draft.steps.length <= 1"
          @click="removeStep(stepIndex)"
        >
          删除
        </el-button>
      </div>
    </div>

    <div class="card-row">
      <span class="row-label">预期结果</span>
      <el-input
        v-model="draft.expectedResult"
        :disabled="locked"
        placeholder="整体预期结果，可留空"
        @input="onChange"
      />
    </div>

    <div v-if="draft.invalid" class="card-error">{{ invalidText }}</div>

    <div v-if="!locked" class="card-foot">
      <span class="foot-hint">草案内容仅在本次审核前有效，入库后进入正式用例库</span>
      <el-button
        v-if="!draft.caseKey"
        size="small"
        plain
        type="primary"
        :loading="busy"
        @click="emit('accept-one')"
      >
        入库此条
      </el-button>
      <el-button v-else size="small" plain @click="emit('open-case', draft.caseId)">查看用例</el-button>
    </div>
  </article>
</template>

<script setup lang="ts">
import StatusTag from '@/components/ui/StatusTag.vue'
import { CASE_TYPE_OPTIONS, PRIORITY_OPTIONS, validateDraft, type CaseDraft } from './shared'

const props = defineProps<{
  /** 草案卡片模型（父组件持有，双向修改） */
  draft: CaseDraft
  /** 卡片序号（从 0 开始） */
  index: number
  /** 锁定态：已整单入库 / 已丢弃后禁止编辑 */
  locked: boolean
  /** 逐条入库进行中 */
  busy: boolean
}>()

const emit = defineEmits<{
  (e: 'update:selected', value: boolean): void
  (e: 'change'): void
  (e: 'remove'): void
  (e: 'accept-one'): void
  (e: 'open-case', caseId: number | null): void
}>()

const invalidText = validateDraft(props.draft) ?? '内容校验未通过'

function onSelect(value: string | number | boolean) {
  emit('update:selected', Boolean(value))
}

function onChange() {
  props.draft.invalid = false
  emit('change')
}

function addStep() {
  props.draft.steps.push({ action: '', expected: '' })
  onChange()
}

function removeStep(stepIndex: number) {
  props.draft.steps.splice(stepIndex, 1)
  onChange()
}
</script>

<style scoped>
.draft-card {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  padding: var(--sp-3) var(--sp-4) var(--sp-3);
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.draft-card.is-invalid {
  border-color: var(--danger-600);
}

.draft-card.is-locked {
  background: var(--bg-sunken);
}

.card-head {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.card-index {
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
  color: var(--text-tertiary);
  flex: none;
}

.card-title {
  flex: 1;
  min-width: 200px;
}

.card-title :deep(.el-input__inner) {
  font-weight: 500;
  color: var(--text-primary);
}

.card-select {
  width: 92px;
  flex: none;
}

.card-type {
  width: 104px;
}

.card-remove {
  flex: none;
}

.card-row {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.row-label {
  flex: none;
  width: 56px;
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
}

.card-steps {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}

.steps-head {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.step-row {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding-left: var(--sp-2);
}

.step-order {
  flex: none;
  width: 18px;
  height: 18px;
  border-radius: var(--radius-sm);
  background: var(--bg-sunken);
  color: var(--text-tertiary);
  font-size: var(--fs-xs);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.step-input {
  flex: 1;
  min-width: 0;
}

.step-arrow {
  flex: none;
  color: var(--text-placeholder);
}

.step-remove {
  flex: none;
}

.card-error {
  color: var(--danger-600);
  font-size: var(--fs-sm);
}

.card-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
  border-top: 1px dashed var(--border-light);
  padding-top: var(--sp-2);
}

.foot-hint {
  color: var(--text-placeholder);
  font-size: var(--fs-xs);
}
</style>
