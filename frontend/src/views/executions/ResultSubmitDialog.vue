<template>
  <el-dialog
    :model-value="visible"
    title="失败确认 · 创建缺陷"
    width="560px"
    :close-on-click-modal="false"
    class="fail-dialog"
    @update:model-value="emit('update:visible', $event)"
  >
    <p class="fail-hint">
      用例 <span class="mono accent">{{ caseKey }}</span>「{{ caseTitle }}」执行失败，可顺手创建缺陷并关联本条结果。
    </p>

    <el-form :model="form" label-width="80px" @submit.prevent>
      <el-form-item label="标题" required>
        <el-input v-model="form.title" maxlength="255" placeholder="缺陷标题" />
      </el-form-item>
      <div class="form-row">
        <el-form-item label="严重程度">
          <el-select v-model="form.severity" style="width: 100%">
            <el-option v-for="item in severities" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="form.priority" style="width: 100%">
            <el-option v-for="item in priorities" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
      </div>
      <el-form-item label="描述">
        <el-input
          v-model="form.description"
          type="textarea"
          :rows="4"
          placeholder="复现步骤、实际表现、日志等（可选）"
        />
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="form.comment" type="textarea" :rows="2" placeholder="给缺陷跟踪人的补充说明（可选）" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button :disabled="submitting" @click="onSkip">仅标记失败</el-button>
      <el-button type="primary" :loading="submitting" :disabled="!form.title.trim()" @click="onSubmit">
        创建并关联缺陷
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue'
import type { DefectForm } from './types'

const props = withDefaults(
  defineProps<{
    visible: boolean
    caseKey: string
    caseTitle: string
    /** 标题预填用的环境 / 构建版本（写入缺陷的 environment / version 字段） */
    environment?: string
    buildVersion?: string
    submitting?: boolean
  }>(),
  { environment: '', buildVersion: '', submitting: false },
)

const emit = defineEmits<{
  'update:visible': [value: boolean]
  /** 创建并关联缺陷（含缺陷字段） */
  submit: [payload: DefectForm]
  /** 仅标记失败，不建缺陷 */
  skip: []
}>()

const severities = [
  { value: 'Blocker', label: '致命' },
  { value: 'Critical', label: '严重' },
  { value: 'Major', label: '一般' },
  { value: 'Minor', label: '次要' },
  { value: 'Trivial', label: '轻微' },
]

const priorities = ['P0', 'P1', 'P2', 'P3']

const form = reactive<DefectForm>({
  title: '',
  description: '',
  severity: 'Major',
  priority: 'P1',
  comment: '',
})

/** 每次打开重置并按当前用例预填标题与描述骨架 */
watch(
  () => props.visible,
  (open) => {
    if (!open) return
    form.title = `${props.caseKey} ${props.caseTitle} 执行失败`
    form.description = [
      `【测试环境】${props.environment || '—'}`,
      `【构建版本】${props.buildVersion || '—'}`,
      `【复现步骤】`,
      ``,
      `【实际表现】`,
      ``,
    ].join('\n')
    form.severity = 'Major'
    form.priority = 'P1'
    form.comment = ''
  },
  { immediate: true },
)

function onSubmit() {
  if (!form.title.trim()) return
  emit('submit', {
    title: form.title.trim(),
    description: form.description,
    severity: form.severity,
    priority: form.priority,
    comment: form.comment,
  })
}

function onSkip() {
  emit('skip')
}
</script>

<style scoped>
.fail-hint {
  margin: 0 0 var(--sp-4);
  font-size: var(--fs-base);
  color: var(--text-secondary);
}

.mono {
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
}

.accent {
  color: var(--accent-600);
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--sp-3);
}
</style>
