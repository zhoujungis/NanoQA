<template>
  <el-form
    ref="formRef"
    class="case-form"
    :model="model"
    :rules="rules"
    label-width="76px"
    label-position="left"
    @submit.prevent
  >
    <el-form-item label="用例标题" prop="title">
      <el-input
        v-model="model.title"
        maxlength="255"
        show-word-limit
        placeholder="简洁描述验证目标，如：正确账号密码登录成功"
      />
    </el-form-item>

    <div class="form-grid">
      <el-form-item label="所属模块" prop="module_id">
        <el-tree-select
          v-model="model.module_id"
          class="full-control"
          :data="modules"
          :props="{ value: 'id', label: 'name', children: 'children' }"
          node-key="id"
          check-strictly
          clearable
          :render-after-expand="false"
          placeholder="选择模块（可留空）"
        />
      </el-form-item>
      <el-form-item label="优先级" prop="priority">
        <el-select v-model="model.priority" placeholder="选择优先级">
          <el-option
            v-for="item in PRIORITY_OPTIONS"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
      </el-form-item>
    </div>

    <div class="form-grid">
      <el-form-item label="用例类型" prop="case_type">
        <el-select v-model="model.case_type" placeholder="选择类型">
          <el-option
            v-for="item in TYPE_OPTIONS"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="负责人" prop="owner_id">
        <el-select v-model="model.owner_id" clearable placeholder="选择负责人（可留空）">
          <el-option
            v-for="item in members"
            :key="item.id"
            :label="userLabel(item)"
            :value="item.id"
          />
        </el-select>
      </el-form-item>
    </div>

    <el-form-item label="标签" prop="tag_ids">
      <el-select v-model="model.tag_ids" multiple clearable placeholder="选择标签（可多选）">
        <el-option v-for="tag in tags" :key="tag.id" :label="tag.name" :value="tag.id" />
      </el-select>
    </el-form-item>

    <el-form-item label="前置条件" prop="precondition">
      <el-input
        v-model="model.precondition"
        type="textarea"
        :autosize="{ minRows: 2, maxRows: 6 }"
        placeholder="执行前需满足的条件，如：用户已注册且未被锁定"
      />
    </el-form-item>

    <el-form-item class="step-form-item" label="测试步骤" prop="steps">
      <StepEditor v-model="model.steps" />
    </el-form-item>

    <el-form-item label="预期结果" prop="expected_result">
      <el-input
        v-model="model.expected_result"
        type="textarea"
        :autosize="{ minRows: 2, maxRows: 6 }"
        placeholder="整体预期结果（各步骤的预期结果已在其内逐条描述，可留空）"
      />
    </el-form-item>

    <el-form-item label="描述" prop="description">
      <el-input
        v-model="model.description"
        type="textarea"
        :autosize="{ minRows: 2, maxRows: 6 }"
        placeholder="补充说明（可留空）"
      />
    </el-form-item>

    <el-form-item v-if="mode === 'edit'" label="变更摘要" prop="change_summary">
      <el-input
        v-model="model.change_summary"
        maxlength="255"
        placeholder="本次修改的简要说明，将记入版本历史（可留空）"
      />
    </el-form-item>
  </el-form>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import StepEditor from './StepEditor.vue'
import {
  PRIORITY_OPTIONS,
  TYPE_OPTIONS,
  userLabel,
  type CaseFormModel,
  type ModuleNode,
  type TagBrief,
  type UserBrief,
} from './shared'

const props = defineProps<{
  model: CaseFormModel
  modules: ModuleNode[]
  tags: TagBrief[]
  members: UserBrief[]
  mode: 'create' | 'edit'
}>()

const formRef = ref<FormInstance>()

/** steps 校验：至少 1 步，且每步操作与预期结果非空（后端强校验） */
function validateSteps(_rule: unknown, _value: unknown, callback: (error?: Error) => void) {
  const steps = props.model.steps || []
  if (!steps.length) {
    callback(new Error('请至少添加 1 个测试步骤'))
    return
  }
  for (let index = 0; index < steps.length; index += 1) {
    const step = steps[index]
    if (!step.action.trim()) {
      callback(new Error(`步骤 ${index + 1}：操作描述不能为空`))
      return
    }
    if (!step.expected.trim()) {
      callback(new Error(`步骤 ${index + 1}：预期结果不能为空`))
      return
    }
  }
  callback()
}

const rules: FormRules = {
  title: [{ required: true, message: '请输入用例标题', trigger: 'blur' }],
  priority: [{ required: true, message: '请选择优先级', trigger: 'change' }],
  steps: [{ validator: validateSteps, trigger: 'change' }],
}

/** 供父级在提交前调用；校验失败返回 false */
async function validate(): Promise<boolean> {
  if (!formRef.value) return true
  try {
    await formRef.value.validate()
    return true
  } catch {
    return false
  }
}

defineExpose({ validate })
</script>

<style scoped>
.case-form {
  padding-right: var(--sp-2);
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 var(--sp-4);
}

.form-grid :deep(.el-form-item) {
  margin-bottom: 16px;
}

.full-control {
  width: 100%;
}

.case-form :deep(.el-select) {
  width: 100%;
}

.step-form-item {
  align-items: flex-start;
}

.step-form-item :deep(.el-form-item__content) {
  display: block;
}

.step-form-item :deep(.step-editor) {
  width: 100%;
}
</style>
