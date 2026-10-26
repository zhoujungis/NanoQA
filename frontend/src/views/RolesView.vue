<template>
  <section class="page">
    <PageHeader title="角色与权限" subtitle="角色决定成员在项目中的操作权限，系统内置角色只读">
      <template #actions>
        <el-button v-if="canManageRoles" type="primary" :disabled="loading" @click="openCreate">
          新建角色
        </el-button>
      </template>
    </PageHeader>

    <!-- 错误态 -->
    <div v-if="error" class="state-panel">
      <p class="state-text">{{ error }}</p>
      <el-button size="small" @click="loadRoles">重新加载</el-button>
    </div>

    <!-- 角色列表 -->
    <div v-else v-loading="loading" class="table-panel">
      <el-table :data="roles">
        <el-table-column label="角色" min-width="200">
          <template #default="{ row }">
            <div class="role-cell">
              <span class="role-name">{{ row.name }}</span>
              <span class="role-code">{{ row.code }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="来源" width="130">
          <template #default="{ row }">
            <StatusTag v-if="row.is_system" tone="info">系统内置</StatusTag>
            <StatusTag v-else tone="neutral">自定义</StatusTag>
          </template>
        </el-table-column>
        <el-table-column label="权限数" width="110">
          <template #default="{ row }">
            <span class="count-cell">{{ row.permission_codenames.length }} 项</span>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="160">
          <template #default="{ row }">
            <span class="time-cell">{{ formatTime(row.updated_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="" width="170" align="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">查看权限</el-button>
            <el-button
              v-if="canManageRoles && !row.is_system"
              link
              type="primary"
              @click="openEdit(row)"
            >
              编辑
            </el-button>
          </template>
        </el-table-column>

        <template #empty>
          <div class="empty-state">
            <p class="state-text">暂无角色</p>
            <el-button v-if="canManageRoles" size="small" type="primary" @click="openCreate">
              新建角色
            </el-button>
          </div>
        </template>
      </el-table>
    </div>

    <!-- 权限矩阵：查看 / 编辑 / 新建 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="680px"
      :close-on-click-modal="false"
    >
      <div v-if="mode !== 'view'" class="role-form">
        <label class="role-form-label">
          <span>角色名称</span>
          <el-input v-model="form.name" maxlength="64" placeholder="如：测试负责人" />
        </label>
        <label class="role-form-label">
          <span>角色编码</span>
          <el-input v-model="form.code" maxlength="32" placeholder="如：qa_lead" :disabled="mode === 'edit'" />
        </label>
      </div>

      <div v-else class="role-summary">
        <span class="role-summary-name">{{ form.name }}</span>
        <span class="role-code">{{ form.code }}</span>
        <StatusTag v-if="isSystemRole" tone="info">系统内置</StatusTag>
      </div>

      <p v-if="isSystemRole" class="matrix-note">系统内置角色，权限只读，不可修改。</p>

      <div class="matrix">
        <div v-for="group in permissionGroups" :key="group.key" class="matrix-group">
          <div class="matrix-group-title">
            <el-checkbox
              :model-value="isGroupChecked(group)"
              :disabled="matrixDisabled"
              :indeterminate="isGroupIndeterminate(group)"
              @change="(checked: boolean | string | number) => toggleGroup(group, Boolean(checked))"
            >
              {{ group.label }}
            </el-checkbox>
          </div>
          <div class="matrix-grid">
            <el-checkbox
              v-for="perm in group.items"
              :key="perm.codename"
              :model-value="form.permissions.includes(perm.codename)"
              :disabled="matrixDisabled"
              @change="(checked: boolean | string | number) => togglePermission(perm.codename, Boolean(checked))"
            >
              <span class="perm-label">{{ perm.label }}</span>
              <span class="perm-code">{{ perm.codename }}</span>
            </el-checkbox>
          </div>
        </div>
      </div>

      <template #footer>
        <el-button @click="dialogVisible = false">{{ mode === 'view' ? '关闭' : '取消' }}</el-button>
        <el-button v-if="mode !== 'view'" type="primary" :loading="saving" @click="submit">
          保存
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, notifyError } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import PageHeader from '@/components/ui/PageHeader.vue'
import StatusTag from '@/components/ui/StatusTag.vue'

/** GET /roles/ 列表项（RoleSerializer） */
interface RoleItem {
  id: number
  code: string
  name: string
  is_system: boolean
  organization: number | null
  permission_codenames: string[]
  updated_at: string
}

interface PermissionEntry {
  codename: string
  label: string
}

interface PermissionGroup {
  key: string
  label: string
  items: PermissionEntry[]
}

type DialogMode = 'view' | 'edit' | 'create'

/**
 * 权限目录：与后端 common/permissions.py 的 PERMISSION_CODENAMES 全集一致，
 * 按模块分组展示；后端仍是最终判定方，前端只做勾选展示。
 */
const PERMISSION_GROUPS: PermissionGroup[] = [
  {
    key: 'project',
    label: '项目',
    items: [
      { codename: 'project.read', label: '查看项目' },
      { codename: 'project.create', label: '创建项目' },
      { codename: 'project.update', label: '修改项目' },
      { codename: 'project.delete', label: '删除项目' },
    ],
  },
  {
    key: 'requirement',
    label: '需求',
    items: [
      { codename: 'requirement.read', label: '查看需求' },
      { codename: 'requirement.create', label: '创建需求' },
      { codename: 'requirement.update', label: '修改需求' },
      { codename: 'requirement.delete', label: '删除需求' },
    ],
  },
  {
    key: 'testcase',
    label: '测试用例',
    items: [
      { codename: 'testcase.read', label: '查看用例' },
      { codename: 'testcase.create', label: '创建用例' },
      { codename: 'testcase.update', label: '修改用例' },
      { codename: 'testcase.delete', label: '删除用例' },
      { codename: 'testcase.execute', label: '执行用例' },
      { codename: 'testcase.review', label: '评审用例' },
    ],
  },
  {
    key: 'testplan',
    label: '测试计划',
    items: [
      { codename: 'testplan.read', label: '查看计划' },
      { codename: 'testplan.create', label: '创建计划' },
      { codename: 'testplan.update', label: '修改计划' },
      { codename: 'testplan.delete', label: '删除计划' },
      { codename: 'testplan.execute', label: '执行计划' },
    ],
  },
  {
    key: 'defect',
    label: '缺陷',
    items: [
      { codename: 'defect.read', label: '查看缺陷' },
      { codename: 'defect.create', label: '创建缺陷' },
      { codename: 'defect.update', label: '修改缺陷' },
      { codename: 'defect.delete', label: '删除缺陷' },
    ],
  },
  {
    key: 'report',
    label: '报告',
    items: [{ codename: 'report.read', label: '查看报告' }],
  },
  {
    key: 'system',
    label: '系统管理',
    items: [
      { codename: 'user.manage', label: '成员管理' },
      { codename: 'role.manage', label: '角色管理' },
      { codename: 'audit.read', label: '查看操作日志' },
    ],
  },
]

const auth = useAuthStore()

/** 角色管理权限：后端 PERMISSION_CODENAMES 中为 role.manage */
const canManageRoles = computed(() => auth.hasPermission('role.manage'))

const roles = ref<RoleItem[]>([])
const loading = ref(false)
const saving = ref(false)
const error = ref('')

const dialogVisible = ref(false)
const mode = ref<DialogMode>('view')
const editingId = ref<number | null>(null)
const isSystemRole = ref(false)
/** 乐观锁版本字段，PATCH 时原样回传 */
const updatedAt = ref('')
const form = ref<{ code: string; name: string; permissions: string[] }>({
  code: '',
  name: '',
  permissions: [],
})

const permissionGroups = PERMISSION_GROUPS

const dialogTitle = computed(() => {
  if (mode.value === 'create') return '新建角色'
  if (mode.value === 'edit') return '编辑角色'
  return '角色权限'
})

const matrixDisabled = computed(() => mode.value === 'view' || isSystemRole.value)

function formatTime(value: string): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

async function loadRoles() {
  loading.value = true
  error.value = ''
  try {
    roles.value = await api.get<RoleItem[]>('/roles/')
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载角色列表失败，请稍后重试'
    notifyError(e)
  } finally {
    loading.value = false
  }
}

function openDetail(row: RoleItem) {
  mode.value = 'view'
  editingId.value = row.id
  isSystemRole.value = row.is_system
  updatedAt.value = row.updated_at
  form.value = { code: row.code, name: row.name, permissions: [...row.permission_codenames] }
  dialogVisible.value = true
}

function openEdit(row: RoleItem) {
  openDetail(row)
  mode.value = 'edit'
}

function openCreate() {
  mode.value = 'create'
  editingId.value = null
  isSystemRole.value = false
  updatedAt.value = ''
  form.value = { code: '', name: '', permissions: [] }
  dialogVisible.value = true
}

function togglePermission(codename: string, checked: boolean) {
  const list = form.value.permissions
  if (checked && !list.includes(codename)) list.push(codename)
  if (!checked) form.value.permissions = list.filter((c) => c !== codename)
}

function isGroupChecked(group: PermissionGroup): boolean {
  return group.items.every((p) => form.value.permissions.includes(p.codename))
}

function isGroupIndeterminate(group: PermissionGroup): boolean {
  const count = group.items.filter((p) => form.value.permissions.includes(p.codename)).length
  return count > 0 && count < group.items.length
}

function toggleGroup(group: PermissionGroup, checked: boolean) {
  for (const perm of group.items) togglePermission(perm.codename, checked)
}

async function submit() {
  const { code, name, permissions } = form.value
  if (!name.trim()) {
    ElMessage.warning('请填写角色名称')
    return
  }
  if (mode.value === 'create' && !/^[a-z0-9_-]{2,32}$/.test(code.trim())) {
    ElMessage.warning('角色编码需为 2-32 位小写字母、数字、下划线或连字符')
    return
  }
  saving.value = true
  try {
    if (mode.value === 'create') {
      await api.post('/roles/', {
        code: code.trim(),
        name: name.trim(),
        permission_codenames: permissions,
      })
      ElMessage.success('角色已创建')
    } else if (editingId.value !== null) {
      // 乐观锁：updated_at 原样回传，禁止格式化
      await api.patch(`/roles/${editingId.value}/`, {
        code: code.trim(),
        name: name.trim(),
        permission_codenames: permissions,
        updated_at: updatedAt.value,
      })
      ElMessage.success('角色已保存')
    }
    dialogVisible.value = false
    await loadRoles()
  } catch (e) {
    notifyError(e)
  } finally {
    saving.value = false
  }
}

onMounted(loadRoles)
</script>

<style scoped>
.page {
  padding: var(--sp-6);
}

.table-panel {
  background: var(--bg-surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.role-cell {
  display: flex;
  flex-direction: column;
  line-height: var(--lh-tight);
}

.role-name {
  font-weight: 500;
  color: var(--text-primary);
}

.role-code {
  color: var(--text-tertiary);
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
}

.count-cell {
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

.time-cell {
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
  font-variant-numeric: tabular-nums;
}

/* ---------------- 弹窗表单 ---------------- */
.role-form {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--sp-3);
  margin-bottom: var(--sp-4);
}

.role-form-label {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
  color: var(--text-secondary);
  font-size: var(--fs-sm);
}

.role-summary {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  margin-bottom: var(--sp-3);
}

.role-summary-name {
  font-size: var(--fs-lg);
  font-weight: 600;
  color: var(--text-primary);
}

.matrix-note {
  margin: 0 0 var(--sp-3);
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
}

/* ---------------- 权限矩阵 ---------------- */
.matrix {
  max-height: 48vh;
  overflow-y: auto;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
}

.matrix-group {
  padding: var(--sp-3) var(--sp-4);
  border-bottom: 1px solid var(--border-light);
}

.matrix-group:last-child {
  border-bottom: none;
}

.matrix-group-title {
  margin-bottom: var(--sp-2);
  font-weight: 600;
  color: var(--text-primary);
}

.matrix-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--sp-1) var(--sp-3);
}

.perm-label {
  color: var(--text-secondary);
  font-size: var(--fs-base);
}

.perm-code {
  margin-left: var(--sp-2);
  color: var(--text-placeholder);
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
}

.state-panel,
.empty-state {
  padding: var(--sp-10) var(--sp-6);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-3);
}

.state-panel {
  background: var(--bg-surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
}

.state-text {
  margin: 0;
  color: var(--text-tertiary);
  font-size: var(--fs-base);
}

:deep(.el-table td.el-table__cell) {
  padding: 9px 0;
}
</style>
