/**
 * 路由表（预先定型）：后续阶段只实现视图，不再改动本文件结构。
 * - /login 登录
 * - /projects 项目列表、/workbench 工作台
 * - /p/:projectId/* 项目内全部页面（左导航 + 顶栏布局）
 */
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { tokenStore } from '@/api/client'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/auth/LoginView.vue'),
    meta: { public: true, title: '登录' },
  },
  {
    path: '/',
    component: () => import('@/layouts/AppLayout.vue'),
    children: [
      { path: '', redirect: '/projects' },
      {
        path: 'projects',
        name: 'projects',
        component: () => import('@/views/ProjectListView.vue'),
        meta: { title: '项目' },
      },
      {
        path: 'workbench',
        name: 'workbench',
        component: () => import('@/views/WorkbenchView.vue'),
        meta: { title: '工作台' },
      },
    ],
  },
  {
    path: '/p/:projectId',
    component: () => import('@/layouts/AppLayout.vue'),
    children: [
      { path: '', redirect: { name: 'project-overview' } },
      {
        path: 'overview',
        name: 'project-overview',
        component: () => import('@/views/ProjectOverviewView.vue'),
        meta: { title: '项目概览' },
      },
      {
        path: 'testcases',
        name: 'testcases',
        component: () => import('@/views/TestCaseListView.vue'),
        meta: { title: '用例管理' },
      },
      {
        path: 'testcases/:caseId',
        name: 'testcase-detail',
        component: () => import('@/views/TestCaseDetailView.vue'),
        meta: { title: '用例详情' },
      },
      {
        path: 'requirements',
        name: 'requirements',
        component: () => import('@/views/RequirementListView.vue'),
        meta: { title: '需求' },
      },
      {
        path: 'requirements/:reqId',
        name: 'requirement-detail',
        component: () => import('@/views/RequirementDetailView.vue'),
        meta: { title: '需求详情' },
      },
      {
        path: 'testplans',
        name: 'testplans',
        component: () => import('@/views/TestPlanListView.vue'),
        meta: { title: '测试计划' },
      },
      {
        path: 'runs',
        name: 'runs',
        component: () => import('@/views/RunListView.vue'),
        meta: { title: '测试执行' },
      },
      {
        path: 'testplans/:planId',
        name: 'testplan-detail',
        component: () => import('@/views/TestPlanDetailView.vue'),
        meta: { title: '测试计划' },
      },
      {
        path: 'runs/:runId',
        name: 'run-execution',
        component: () => import('@/views/RunExecutionView.vue'),
        meta: { title: '测试执行' },
      },
      {
        path: 'runs/:runId/report',
        name: 'run-report',
        component: () => import('@/views/RunReportView.vue'),
        meta: { title: '测试报告' },
      },
      {
        path: 'defects',
        name: 'defects',
        component: () => import('@/views/DefectListView.vue'),
        meta: { title: '缺陷' },
      },
      {
        path: 'defects/:defectId',
        name: 'defect-detail',
        component: () => import('@/views/DefectDetailView.vue'),
        meta: { title: '缺陷详情' },
      },
      {
        path: 'reports',
        name: 'reports',
        component: () => import('@/views/ReportsView.vue'),
        meta: { title: '报告' },
      },
      {
        path: 'ai',
        name: 'ai-workspace',
        component: () => import('@/views/AiWorkspaceView.vue'),
        meta: { title: 'AI 助手' },
      },
      {
        path: 'members',
        name: 'members',
        component: () => import('@/views/MembersView.vue'),
        meta: { title: '成员' },
      },
      {
        path: 'roles',
        name: 'roles',
        component: () => import('@/views/RolesView.vue'),
        meta: { title: '角色权限' },
      },
      {
        path: 'audit',
        name: 'audit',
        component: () => import('@/views/AuditLogView.vue'),
        meta: { title: '审计日志' },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFoundView.vue'),
    meta: { public: true, title: '页面不存在' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.afterEach((to) => {
  const title = to.meta.title as string | undefined
  document.title = title ? `${title} · NanoQA` : 'NanoQA'
})

router.beforeEach(async (to) => {
  if (to.meta.public) return true
  const auth = useAuthStore()
  if (!tokenStore.access) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (!auth.loaded) {
    try {
      await auth.fetchMe()
    } catch {
      tokenStore.clear()
      return { name: 'login', query: { redirect: to.fullPath } }
    }
  }
  return true
})

export default router
