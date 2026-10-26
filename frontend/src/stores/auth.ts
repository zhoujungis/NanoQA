/** 认证状态：登录 / 退出 / /auth/me 身份与权限 */
import { defineStore } from 'pinia'
import { api, tokenStore } from '@/api/client'

export interface AuthUser {
  id: number
  username: string
  display_name: string
  email?: string
  avatar?: string
}

export interface Membership {
  project_id: number
  project_key: string
  project_name: string
  role: string
  role_name: string
}

export interface MeData {
  user: AuthUser
  memberships: Membership[]
  permissions: string[]
  is_system_admin: boolean
}

interface LoginResult {
  access: string
  refresh: string
  user: AuthUser
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as AuthUser | null,
    memberships: [] as Membership[],
    permissions: [] as string[],
    isSystemAdmin: false,
    loaded: false,
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.user) && Boolean(tokenStore.access),
  },
  actions: {
    async login(email: string, password: string) {
      const data = await api.post<LoginResult>('/auth/login/', { email, password })
      tokenStore.set(data.access, data.refresh)
      this.user = data.user
      await this.fetchMe()
    },
    async fetchMe() {
      const data = await api.get<MeData>('/auth/me/')
      this.user = data.user
      this.memberships = data.memberships
      this.permissions = data.permissions
      this.isSystemAdmin = data.is_system_admin
      this.loaded = true
    },
    async logout() {
      try {
        await api.post('/auth/logout/', { refresh: tokenStore.refresh })
      } catch {
        // 登出接口失败不阻塞本地清理
      }
      tokenStore.clear()
      this.user = null
      this.memberships = []
      this.permissions = []
      this.isSystemAdmin = false
      this.loaded = false
    },
    hasPermission(codename: string): boolean {
      return this.isSystemAdmin || this.permissions.includes(codename)
    },
  },
})
