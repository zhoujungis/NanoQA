<template>
  <section class="page">
    <PageHeader title="成员管理" subtitle="管理项目成员及其角色，角色决定成员在本项目中的权限">
      <template #actions>
        <el-button v-if="canManage" type="primary" :disabled="loading" @click="openAddDialog">
          添加成员
        </el-button>
      </template>
    </PageHeader>

    <!-- 错误态 -->
    <div v-if="error" class="state-panel">
      <p class="state-text">{{ error }}</p>
      <el-button size="small" @click="loadAll">重新加载</el-button>
    </div>

    <!-- 成员表格 -->
    <div v-else v-loading="loading" class="table-panel">
      <el-table :data="members">
        <el-table-column label="成员" min-width="220">
          <template #default="{ row }">
            <div class="member-cell">
              <span class="member-avatar">{{ memberInitial(row) }}</span>
              <span class="member-names">
                <span class="member-name">{{ row.user.display_name || row.user.username }}</span>
                <span class="member-account">{{ row.user.email || row.user.username }}</span>
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="角色" width="180">
          <template #default="{ row }">
            <StatusTag tone="accent">{{ row.role.name }}</StatusTag>
            <span class="role-code">{{ row.role.code }}</span>
          </template>
        </el-table-column>
        <el-table-column label="加入时间" width="160">
          <template #default="{ row }">
            <span class="time-cell">{{ formatTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column v-if="canManage" label="" width="170" align="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openRoleDialog(row)">调整角色</el-button>
            <el-button link type="danger" @click="removeMember(row)">移除</el-button>
          </template>
        </el-table-column>

        <template #empty>
          <div class="empty-state">
            <p class="state-text">暂无成员</p>
            <el-button v-if="canManage" size="small" type="primary" @click="openAddDialog">
              添加成员
            </el-button>
          </div>
        </template>
      </el-table>
    </div>

    <!-- 添加成员 -->
    <el-dialog v-model="addVisible" title="添加成员" width="420px" :close-on-click-modal="false">
      <el-form label-width="64px" @submit.prevent>
        <el-form-item label="用户">
          <el-select
            v-model="addForm.userId"
            filterable
            placeholder="选择用户"
            class="full-select"
            :loading="usersLoading"
          >
            <el-option
              v-for="user in addableUsers"
              :key="user.id"
              :label="`${user.display_name || user.username}（${user.email || user.username}）`"
              :value="user.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="addForm.roleId" placeholder="选择角色" class="full-select">
            <el-option v-for="role in roles" :key="role.id" :label="role.name" :value="role.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitAdd">确定</el-button>
      </template>
    </el-dialog>

    <!-- 调整角色 -->
    <el-dialog v-model="roleVisible" title="调整角色" width="420px" :close-on-click-modal="false">
      <el-form label-width="64px" @submit.prevent>
        <el-form-item label="成员">
          <span class="dialog-member">{{ roleTarget?.user.display_name || roleTarget?.user.username }}</span>
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="roleForm.roleId" placeholder="选择角色" class="full-select">
            <el-option v-for="role in roles" :key="role.id" :label="role.name" :value="role.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="roleVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitRole">确定</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, notifyError, type PageResult } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import PageHeader from '@/components/ui/PageHeader.vue'
import StatusTag from '@/components/ui/StatusTag.vue'

/** GET /projects/{id}/members/ 列表项（ProjectMemberSerializer） */
interface MemberItem {
  id: number
  user: { id: number; username: string; display_name: string; email: string }
  role: { id: number; code: string; name: string }
  created_at: string
}

/** GET /roles/ 列表项（RoleSerializer） */
interface RoleItem {
  id: number
  code: string
  name: string
  is_system: boolean
}

/** GET /users/ 列表项（UserSerializer） */
interface UserItem {
  id: number
  username: string
  display_name: string
  email: string
}

const route = useRoute()
const auth = useAuthStore()

const projectId = computed(() => String(route.params.projectId || ''))

/** 成员管理权限：后端 PERMISSION_CODENAMES 中为 user.manage */
const canManage = computed(() => auth.hasPermission('user.manage'))

const members = ref<MemberItem[]>([])
const roles = ref<RoleItem[]>([])
const users = ref<UserItem[]>([])
const loading = ref(false)
const usersLoading = ref(false)
const saving = ref(false)
const error = ref('')

const addVisible = ref(false)
const addForm = ref<{ userId: number | ''; roleId: number | '' }>({ userId: '', roleId: '' })
const roleVisible = ref(false)
const roleTarget = ref<MemberItem | null>(null)
const roleForm = ref<{ roleId: number | '' }>({ roleId: '' })

/** 已是成员的用户不再出现在添加下拉中 */
const addableUsers = computed(() => {
  const existing = new Set(members.value.map((m) => m.user.id))
  return users.value.filter((u) => !existing.has(u.id))
})

function memberInitial(row: MemberItem): string {
  const name = row.user.display_name || row.user.username || '?'
  return name.slice(0, 1).toUpperCase()
}

function formatTime(value: string): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

async function loadMembers() {
  members.value = await api.get<MemberItem[]>(`/projects/${projectId.value}/members/`)
}

async function loadRoles() {
  roles.value = await api.get<RoleItem[]>('/roles/')
}

async function loadUsers() {
  const data = await api.get<PageResult<UserItem>>('/users/', { params: { page_size: 100 } })
  users.value = data.items
}

async function loadAll() {
  if (!projectId.value) return
  loading.value = true
  error.value = ''
  try {
    await Promise.all([loadMembers(), loadRoles(), loadUsers()])
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载成员列表失败，请稍后重试'
    notifyError(e)
  } finally {
    loading.value = false
  }
}

function openAddDialog() {
  addForm.value = { userId: '', roleId: '' }
  addVisible.value = true
}

async function submitAdd() {
  const { userId, roleId } = addForm.value
  if (!userId || !roleId) {
    ElMessage.warning('请选择用户和角色')
    return
  }
  saving.value = true
  try {
    await api.post(`/projects/${projectId.value}/members/`, { user_id: userId, role_id: roleId })
    ElMessage.success('成员已添加')
    addVisible.value = false
    await loadMembers()
  } catch (e) {
    notifyError(e)
  } finally {
    saving.value = false
  }
}

function openRoleDialog(row: MemberItem) {
  roleTarget.value = row
  roleForm.value = { roleId: row.role.id }
  roleVisible.value = true
}

async function submitRole() {
  const target = roleTarget.value
  const roleId = roleForm.value.roleId
  if (!target || !roleId) {
    ElMessage.warning('请选择角色')
    return
  }
  saving.value = true
  try {
    await api.patch(`/projects/members/${target.id}/`, { role_id: roleId })
    ElMessage.success('角色已更新')
    roleVisible.value = false
    await loadMembers()
  } catch (e) {
    notifyError(e)
  } finally {
    saving.value = false
  }
}

async function removeMember(row: MemberItem) {
  const name = row.user.display_name || row.user.username
  try {
    await ElMessageBox.confirm(`确定将「${name}」移出本项目？`, '移除成员', {
      confirmButtonText: '移除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await api.delete(`/projects/members/${row.id}/`)
    ElMessage.success('成员已移除')
    await loadMembers()
  } catch (e) {
    notifyError(e)
  }
}

onMounted(loadAll)
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

.member-cell {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
}

.member-avatar {
  flex: none;
  width: 26px;
  height: 26px;
  border-radius: var(--radius-sm);
  background: var(--bg-sunken);
  color: var(--text-secondary);
  font-size: var(--fs-sm);
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}

.member-names {
  display: flex;
  flex-direction: column;
  line-height: var(--lh-tight);
}

.member-name {
  font-weight: 500;
  color: var(--text-primary);
}

.member-account {
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
}

.role-code {
  margin-left: var(--sp-2);
  color: var(--text-tertiary);
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
}

.time-cell {
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
  font-variant-numeric: tabular-nums;
}

.full-select {
  width: 100%;
}

.dialog-member {
  color: var(--text-primary);
  font-weight: 500;
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
