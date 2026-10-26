<template>
  <div class="login-page">
    <div class="login-card">
      <header class="login-brand">
        <h1 class="login-title">NanoQA</h1>
        <p class="login-subtitle">AI 原生的测试用例管理与测试执行协同平台</p>
      </header>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        class="login-form"
        @submit.prevent="onSubmit"
      >
        <el-form-item label="邮箱" prop="email">
          <el-input
            v-model="form.email"
            placeholder="请输入邮箱"
            size="large"
            autocomplete="username"
            @keyup.enter="onSubmit"
          />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            size="large"
            show-password
            autocomplete="current-password"
            @keyup.enter="onSubmit"
          />
        </el-form-item>

        <el-button
          type="primary"
          size="large"
          class="login-submit"
          :loading="loading"
          native-type="submit"
          @click="onSubmit"
        >
          登录
        </el-button>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  email: '',
  password: '',
})

const rules: FormRules = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' },
  ],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

/** 登录成功后回跳地址：优先 ?redirect=，否则进项目列表 */
const redirect = computed(() => {
  const value = route.query.redirect
  return typeof value === 'string' && value.startsWith('/') ? value : '/projects'
})

async function onSubmit() {
  if (loading.value) return
  const formEl = formRef.value
  if (!formEl) return
  const valid = await formEl.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await auth.login(form.email.trim(), form.password)
    ElMessage.success('登录成功')
    router.push(redirect.value)
  } catch (error) {
    // 登录失败：统一错误提示（密码错误 / 账号禁用等）
    const message = error instanceof Error ? error.message : '登录失败，请稍后重试'
    ElMessage.error(message)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--sp-6);
  background: var(--bg-page);
}

.login-card {
  width: 360px;
  padding: var(--sp-8) var(--sp-6) var(--sp-6);
  background: var(--bg-surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
}

.login-brand {
  text-align: center;
  margin-bottom: var(--sp-6);
}

.login-title {
  margin: 0;
  font-size: var(--fs-2xl);
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--text-primary);
}

.login-subtitle {
  margin: var(--sp-2) 0 0;
  font-size: var(--fs-base);
  color: var(--text-tertiary);
}

.login-form :deep(.el-form-item) {
  margin-bottom: var(--sp-5);
}

.login-form :deep(.el-form-item__label) {
  font-size: var(--fs-sm);
  font-weight: 500;
  color: var(--text-secondary);
  line-height: var(--lh-tight);
  margin-bottom: var(--sp-1);
}

.login-submit {
  width: 100%;
  margin-top: var(--sp-2);
}
</style>
