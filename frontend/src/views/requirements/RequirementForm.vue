<template>
  <el-form ref="formRef" :model="model" :rules="rules" label-width="80px" class="req-form">
    <el-form-item label="标题" prop="title">
      <el-input
        v-model="model.title"
        maxlength="255"
        placeholder="一句话描述需求，如：下单与支付主流程"
      />
    </el-form-item>
    <el-form-item label="描述" prop="description">
      <el-input
        v-model="model.description"
        type="textarea"
        :rows="4"
        placeholder="补充需求背景、范围与验收口径"
      />
    </el-form-item>
    <el-form-item label="状态" prop="status">
      <el-select v-model="model.status" style="width: 100%">
        <el-option v-for="item in statusItems" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
    </el-form-item>
    <el-form-item label="优先级" prop="priority">
      <el-radio-group v-model="model.priority">
        <el-radio-button v-for="item in PRIORITY_OPTIONS" :key="item.value" :value="item.value">
          {{ item.label }}
        </el-radio-button>
      </el-radio-group>
    </el-form-item>
    <el-form-item label="负责人" prop="owner_id">
      <el-select
        v-model="model.owner_id"
        placeholder="选择负责人（可留空）"
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
import { computed, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { PRIORITY_OPTIONS, STATUS_OPTIONS, statusLabel, type RequirementFormModel, type UserBrief } from './shared'

const props = defineProps<{
  /** 表单草稿模型（父组件持有，双向修改） */
  model: RequirementFormModel
  /** 可选负责人列表 */
  users: UserBrief[]
  /** create=创建（状态默认草稿）；edit=编辑（保留历史未知状态） */
  mode: 'create' | 'edit'
}>()

const formRef = ref<FormInstance>()

/** 状态下拉：编辑时若历史数据存在未知状态，补一项兜底，避免值被吞掉 */
const statusItems = computed<{ value: string; label: string }[]>(() => {
  const known = STATUS_OPTIONS.some((item) => item.value === props.model.status)
  if (known || !props.model.status) return STATUS_OPTIONS
  return [...STATUS_OPTIONS, { value: props.model.status, label: statusLabel(props.model.status) }]
})

const rules: FormRules = {
  title: [{ required: true, message: '请输入需求标题', trigger: 'blur' }],
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
.req-form :deep(.el-form-item) {
  margin-bottom: var(--sp-4);
}
</style>
