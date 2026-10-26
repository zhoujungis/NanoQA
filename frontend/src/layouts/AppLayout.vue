<template>
  <div class="app-shell">
    <!-- 左侧固定导航（200px） -->
    <aside class="app-sidebar">
      <div class="brand">
        <span class="brand-name">NanoQA</span>
      </div>

      <!-- 项目切换器：项目上下文显示当前项目，否则显示"选择项目" -->
      <div class="switcher-wrap">
        <el-dropdown trigger="click" placement="bottom-start" @command="onSwitchProject">
          <button type="button" class="switcher">
            <span class="switcher-text">
              <template v-if="currentProject">
                <span class="switcher-key">{{ currentProject.key }}</span>
                <span class="switcher-name">{{ currentProject.name }}</span>
              </template>
              <span v-else class="switcher-placeholder">选择项目</span>
            </span>
            <el-icon class="switcher-arrow"><ArrowDown /></el-icon>
          </button>
          <template #dropdown>
            <el-dropdown-menu class="switcher-menu">
              <div v-if="projectsLoading" class="switcher-state">加载中…</div>
              <div v-else-if="projects.length === 0" class="switcher-state">暂无可访问的项目</div>
              <template v-else>
                <el-dropdown-item
                  v-for="item in projects"
                  :key="item.id"
                  :command="item.id"
                  :class="{ 'is-current': currentProject?.id === item.id }"
                >
                  <span class="menu-key">{{ item.key }}</span>
                  <span class="menu-name">{{ item.name }}</span>
                </el-dropdown-item>
              </template>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>

      <nav class="side-nav">
        <!-- 项目菜单：仅项目上下文显示 -->
        <template v-if="isProjectContext">
          <div class="nav-group">
            <div class="nav-group-title">项目</div>
            <router-link
              v-for="item in projectNav"
              :key="item.name"
              class="nav-item"
              :class="{ 'is-active': isActive(item) }"
              :to="{ name: item.name, params: routeParams }"
            >
              {{ item.label }}
            </router-link>
          </div>

          <div class="nav-group">
            <div class="nav-group-title">AI 助手</div>
            <router-link
              class="nav-item"
              :class="{ 'is-active': isActive(aiNavItem) }"
              :to="{ name: aiNavItem.name, params: routeParams }"
            >
              {{ aiNavItem.label }}
            </router-link>
          </div>

          <div class="nav-group">
            <div class="nav-group-title">系统</div>
            <router-link
              v-for="item in systemNav"
              :key="item.name"
              class="nav-item"
              :class="{ 'is-active': isActive(item) }"
              :to="{ name: item.name, params: routeParams }"
            >
              {{ item.label }}
            </router-link>
          </div>
        </template>

        <!-- 全局入口：始终显示 -->
        <div class="nav-group">
          <div class="nav-group-title">全局</div>
          <router-link
            v-for="item in globalNav"
            :key="item.name"
            class="nav-item"
            :class="{ 'is-active': isActive(item) }"
            :to="{ name: item.name }"
          >
            {{ item.label }}
          </router-link>
        </div>
      </nav>
    </aside>

    <div class="app-main">
      <!-- 顶栏：项目名 + 当前页标题 + 用户区 -->
      <header class="app-topbar">
        <div class="topbar-context">
          <template v-if="currentProject">
            <span class="topbar-project">{{ currentProject.name }}</span>
            <span class="topbar-divider">/</span>
          </template>
          <span class="topbar-title">{{ pageTitle }}</span>
        </div>
        <div class="topbar-actions">
          <el-dropdown trigger="click" @command="onUserCommand">
            <button type="button" class="user-trigger">
              <span class="user-avatar">{{ userInitial }}</span>
              <span class="user-name">{{ displayName }}</span>
              <el-icon class="switcher-arrow"><ArrowDown /></el-icon>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <main class="app-content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowDown } from '@element-plus/icons-vue'
import { api, notifyError, type PageResult } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

/** 项目简要信息（GET /projects/ 列表项） */
interface ProjectBrief {
  id: number
  key: string
  name: string
  status: string
}

interface NavItem {
  name: string
  label: string
  /** 命中高亮的路由名（含详情页回落到所属列表） */
  match: string[]
}

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const projects = ref<ProjectBrief[]>([])
const projectsLoading = ref(false)
/** 项目列表未覆盖到当前项目时的兜底详情 */
const fallbackProject = ref<ProjectBrief | null>(null)

const projectNav: NavItem[] = [
  { name: 'project-overview', label: '项目概览', match: ['project-overview'] },
  { name: 'requirements', label: '需求', match: ['requirements', 'requirement-detail'] },
  { name: 'testcases', label: '测试用例', match: ['testcases', 'testcase-detail'] },
  { name: 'testplans', label: '测试计划', match: ['testplans', 'testplan-detail'] },
  { name: 'runs', label: '测试执行', match: ['runs', 'run-execution', 'run-report'] },
  { name: 'defects', label: '缺陷', match: ['defects', 'defect-detail'] },
  { name: 'reports', label: '测试报告', match: ['reports'] },
]

const aiNavItem: NavItem = { name: 'ai-workspace', label: 'AI 助手', match: ['ai-workspace'] }

const systemNav: NavItem[] = [
  { name: 'members', label: '成员', match: ['members'] },
  { name: 'roles', label: '权限', match: ['roles'] },
  { name: 'audit', label: '操作日志', match: ['audit'] },
]

const globalNav: NavItem[] = [
  { name: 'projects', label: '项目', match: ['projects'] },
  { name: 'workbench', label: '工作台', match: ['workbench'] },
]

/** 切换项目后停留的页面（详情页回落到所属列表页） */
const SWITCH_TARGET: Record<string, string> = {
  'requirement-detail': 'requirements',
  'testcase-detail': 'testcases',
  'testplan-detail': 'testplans',
  'run-execution': 'runs',
  'run-report': 'runs',
  'defect-detail': 'defects',
}

const currentProjectId = computed(() => Number(route.params.projectId) || 0)
const isProjectContext = computed(() => Boolean(currentProjectId.value))

const currentProject = computed<ProjectBrief | null>(() => {
  if (!isProjectContext.value) return null
  return (
    projects.value.find((p) => p.id === currentProjectId.value) ??
    (fallbackProject.value?.id === currentProjectId.value ? fallbackProject.value : null)
  )
})

const routeParams = computed(() => ({ projectId: route.params.projectId }))
const pageTitle = computed(() => (route.meta.title as string) || '')
const displayName = computed(() => auth.user?.display_name || auth.user?.username || '')
const userInitial = computed(() => (displayName.value || '?').slice(0, 1).toUpperCase())

function isActive(item: NavItem): boolean {
  return item.match.includes(String(route.name || ''))
}

async function loadProjects() {
  projectsLoading.value = true
  try {
    const data = await api.get<PageResult<ProjectBrief>>('/projects/', {
      params: { page_size: 100 },
    })
    projects.value = data.items
  } catch (error) {
    notifyError(error)
  } finally {
    projectsLoading.value = false
  }
}

/** 项目列表（分页）没覆盖当前项目时，拉详情兜底显示项目名 */
async function ensureProjectBrief() {
  const id = currentProjectId.value
  if (!id || projects.value.some((p) => p.id === id)) return
  try {
    fallbackProject.value = await api.get<ProjectBrief>(`/projects/${id}/`)
  } catch {
    fallbackProject.value = null
  }
}

function onSwitchProject(id: number) {
  if (id === currentProjectId.value) return
  const currentName = String(route.name || '')
  const target = SWITCH_TARGET[currentName] ?? (isProjectContext.value ? currentName : 'project-overview')
  router.push({ name: target, params: { projectId: String(id) } })
}

async function onUserCommand(command: string) {
  if (command !== 'logout') return
  await auth.logout()
  router.push({ name: 'login' })
}

onMounted(loadProjects)
watch(currentProjectId, ensureProjectBrief, { immediate: true })
</script>

<style scoped>
.app-shell {
  display: flex;
  height: 100%;
}

/* ---------- 左侧导航 ---------- */
.app-sidebar {
  width: var(--sidebar-w);
  flex: none;
  background: var(--bg-surface);
  border-right: 1px solid var(--border-light);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.brand {
  height: var(--topbar-h);
  flex: none;
  display: flex;
  align-items: center;
  padding: 0 var(--sp-4);
  border-bottom: 1px solid var(--border-light);
}

.brand-name {
  font-size: var(--fs-lg);
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--text-primary);
}

.switcher-wrap {
  flex: none;
  padding: var(--sp-3) var(--sp-3) var(--sp-2);
}

.switcher {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
  padding: var(--sp-2) var(--sp-3);
  background: var(--bg-sunken);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-family: inherit;
  transition: border-color var(--dur-fast) var(--ease-out);
}

.switcher:hover {
  border-color: var(--border-strong);
}

.switcher-text {
  min-width: 0;
  display: flex;
  align-items: baseline;
  gap: var(--sp-2);
}

.switcher-key {
  flex: none;
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--accent-600);
}

.switcher-name {
  min-width: 0;
  font-size: var(--fs-sm);
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.switcher-placeholder {
  font-size: var(--fs-sm);
  color: var(--text-tertiary);
}

.switcher-arrow {
  flex: none;
  font-size: var(--fs-sm);
  color: var(--text-tertiary);
}

.switcher-menu {
  max-height: 320px;
  overflow-y: auto;
  min-width: 220px;
}

.switcher-state {
  padding: var(--sp-3) var(--sp-4);
  font-size: var(--fs-sm);
  color: var(--text-tertiary);
}

.menu-key {
  flex: none;
  min-width: 52px;
  margin-right: var(--sp-2);
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
  font-weight: 600;
  color: var(--accent-600);
}

.menu-name {
  color: var(--text-primary);
}

.el-dropdown-menu__item.is-current .menu-name {
  color: var(--accent-600);
  font-weight: 500;
}

/* ---------- 导航分组 ---------- */
.side-nav {
  flex: 1;
  padding: var(--sp-2) var(--sp-3) var(--sp-5);
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}

.nav-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-group-title {
  padding: 0 var(--sp-3) var(--sp-2);
  font-size: var(--fs-xs);
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--text-tertiary);
}

.nav-item {
  padding: 7px var(--sp-3);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  text-decoration: none;
  font-size: var(--fs-base);
  transition: background-color var(--dur-fast) var(--ease-out),
    color var(--dur-fast) var(--ease-out);
}

.nav-item:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.nav-item.is-active {
  background: var(--accent-50);
  color: var(--accent-600);
  font-weight: 500;
}

/* ---------- 顶栏 ---------- */
.app-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.app-topbar {
  height: var(--topbar-h);
  flex: none;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-light);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-4);
  padding: 0 var(--sp-5);
}

.topbar-context {
  display: flex;
  align-items: baseline;
  gap: var(--sp-3);
  min-width: 0;
}

.topbar-project {
  font-size: var(--fs-base);
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.topbar-divider {
  color: var(--text-placeholder);
}

.topbar-title {
  font-size: var(--fs-base);
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.topbar-actions {
  flex: none;
  display: flex;
  align-items: center;
}

.user-trigger {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-1) var(--sp-2);
  background: none;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  font-family: inherit;
  transition: background-color var(--dur-fast) var(--ease-out);
}

.user-trigger:hover {
  background: var(--bg-hover);
}

.user-avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--accent-50);
  color: var(--accent-600);
  font-size: var(--fs-sm);
  font-weight: 600;
  display: grid;
  place-items: center;
}

.user-name {
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--fs-base);
  color: var(--text-secondary);
}

.app-content {
  flex: 1;
  min-height: 0;
  overflow: auto;
}
</style>
