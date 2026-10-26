<template>
  <el-form ref="formRef" :model="model" :rules="rules" label-width="80px" class="defect-form">
    <el-form-item label="标题" prop="title">
      <el-input
        v-model="model.title"
        maxlength="255"
        placeholder="一句话描述缺陷现象，如：支付宝支付回调返回 500"
      />
    </el-form-item>
    <el-form-item label="描述" prop="description">
      <el-input
        v-model="model.description"
        type="textarea"
        :rows="4"
        placeholder="补充复现步骤、期望结果与实际结果"
      />
    </el-form-item>
    <el-form-item label="严重程度" prop="severity">
      <el-select v-model="model.severity" style="width: 100%">
        <el-option v-for="item in SEVERITY_OPTIONS" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
    </el-form-item>
    <el-form-item label="优先级" prop="priority">
      <el-radio-group v-model="model.priority">
        <el-radio-button v-for="item in PRIORITY_OPTIONS" :key="item.value" :value="item.value">
          {{ item.label }}
        </el-radio-button>
      </el-radio-group>
    </el-form-item>
    <el-form-item label="环境" prop="environment">
      <el-input v-model="model.environment" maxlength="64" placeholder="如：Staging / Chrome 120" />
    </el-form-item>
    <el-form-item label="影响版本" prop="version">
      <el-input v-model="model.version" maxlength="64" placeholder="如：1.0.0" />
    </el-form-item>
    <el-form-item label="经办人" prop="assignee_id">
      <el-select
        v-model="model.assignee_id"
        placeholder="选择经办人（可留空）"
        clearable
        filterable
        style="width: 100%"
      >
        <el-option
          v-for="user in users"
          :key="user.id"
          :label="user.display_name || user.username"
          :value="user.id"
        />
      </el-select>
    </el-form-item>
  </el-form>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import {
  PRIORITY_OPTIONS,
  SEVERITY_OPTIONS,
  type DefectFormModel,
  type UserBrief,
} from './shared'

defineProps<{
  /** 表单草稿模型（父组件持有，双向修改） */
  model: DefectFormModel
  /** 可选经办人列表 */
  users: UserBrief[]
}>()

const formRef = ref<FormInstance>()

const rules: FormRules = {
  title: [{ required: true, message: '请输入缺陷标题', trigger: 'blur' }],
}

function validate() {
  return formRef.value?.validate() ?? Promise.reject(new Error('表单未就绪'))
}

function clearValidate() {
  formRef.value?.clearValidate()
}

defineExpose({ validate, clearValidate })
</script>

<style scoped>
.defect-form :deep(.el-form-item) {
  margin-bottom: var(--sp-4);
}
</style>
