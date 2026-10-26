<template>
  <el-dialog
    :model-value="visible"
    title="新建项目"
    width="480px"
    destroy-on-close
    @update:model-value="onVisibleChange"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-position="top"
      @submit.prevent="onSubmit"
    >
      <el-form-item label="项目名称" prop="name">
        <el-input v-model="form.name" placeholder="如：电商交易平台" maxlength="128" />
      </el-form-item>

      <el-form-item prop="key">
        <template #label>
          项目 Key
          <span class="field-hint">创建后不可修改</span>
        </template>
        <el-input
          v-model="form.key"
          placeholder="大写短码，如 SHOP"
          maxlength="16"
          style="text-transform: uppercase"
          @input="form.key = form.key.toUpperCase()"
        />
      </el-form-item>

      <el-form-item label="描述" prop="description">
        <el-input
          v-model="form.description"
          type="textarea"
          :rows="3"
          placeholder="一句话说明项目背景与测试范围（选填）"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="onVisibleChange(false)">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="onSubmit">创建</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { api, notifyError } from '@/api/client'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'created'): void
}>()

const formRef = ref<FormInstance>()
const submitting = ref(false)

const form = reactive({
  name: '',
  key: '',
  description: '',
})

const rules: FormRules = {
  name: [{ required: true, message: '请输入项目名称', trigger: 'blur' }],
  key: [
    { required: true, message: '请输入项目 Key', trigger: 'blur' },
    {
      pattern: /^[A-Z][A-Z0-9]{1,15}$/,
      message: 'Key 只能是 2-16 位大写字母或数字，且以字母开头',
      trigger: 'blur',
    },
  ],
}

function onVisibleChange(value: boolean) {
  emit('update:visible', value)
}

function resetForm() {
  form.name = ''
  form.key = ''
  form.description = ''
  formRef.value?.clearValidate()
}

async function onSubmit() {
  if (submitting.value) return
  const formEl = formRef.value
  if (!formEl) return
  const valid = await formEl.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    await api.post('/projects/', {
      name: form.name.trim(),
      key: form.key.trim(),
      description: form.description.trim(),
    })
    ElMessage.success('项目已创建')
    emit('created')
    onVisibleChange(false)
    resetForm()
  } catch (error) {
    notifyError(error)
  } finally {
    submitting.value = false
  }
}

// 关闭弹窗时清空表单，避免残留上次输入
watch(
  () => props.visible,
  (value) => {
    if (!value) resetForm()
  },
)
</script>

<style scoped>
.field-hint {
  margin-left: var(--sp-2);
  font-size: var(--fs-xs);
  font-weight: 400;
  color: var(--text-tertiary);
}
</style>
