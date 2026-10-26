/**
 * NanoQA API 客户端
 * - 统一信封解包：{ code, message, data }，code === 0 才视为成功
 * - 401/40002 单飞刷新 token 后重放原请求（并发只发一次刷新）
 * - 40003 乐观锁冲突弹统一确认框
 */
import axios, { AxiosError, type AxiosRequestConfig } from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'

export interface ApiEnvelope<T = unknown> {
  code: number
  message: string
  data: T
}

export interface PageResult<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export class ApiError extends Error {
  code: number
  status: number
  detail: unknown

  constructor(message: string, code: number, status: number, detail?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.detail = detail
  }
}

const ACCESS_KEY = 'nanoqa.access'
const REFRESH_KEY = 'nanoqa.refresh'

export const tokenStore = {
  get access(): string {
    return localStorage.getItem(ACCESS_KEY) || ''
  },
  get refresh(): string {
    return localStorage.getItem(REFRESH_KEY) || ''
  },
  set(access: string, refresh: string) {
    localStorage.setItem(ACCESS_KEY, access)
    localStorage.setItem(REFRESH_KEY, refresh)
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}

const client = axios.create({ baseURL: '/api/v1', timeout: 30000 })

/** 不参与自动刷新的端点（否则会死循环） */
const NO_REFRESH_PATHS = ['/auth/login/', '/auth/refresh/', '/auth/logout/']

client.interceptors.request.use((config) => {
  const token = tokenStore.access
  if (token) {
    config.headers = config.headers ?? {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

let refreshPromise: Promise<string> | null = null

async function refreshTokens(): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const { data } = await axios.post<ApiEnvelope<{ access: string; refresh: string }>>(
        '/api/v1/auth/refresh/',
        { refresh: tokenStore.refresh },
      )
      const payload = data.data
      tokenStore.set(payload.access, payload.refresh)
      return payload.access
    })()
    refreshPromise.catch(() => tokenStore.clear()).finally(() => {
      refreshPromise = null
    })
  }
  return refreshPromise
}

let conflictBoxOpen = false

function showConflictBox(message: string) {
  if (conflictBoxOpen) return
  conflictBoxOpen = true
  ElMessageBox.alert(message, '保存冲突', {
    confirmButtonText: '刷新后重试',
    type: 'warning',
  })
    .catch(() => undefined)
    .finally(() => {
      conflictBoxOpen = false
    })
}

interface ApiRequestConfig extends AxiosRequestConfig {
  /** 命中 401 时不自动刷新（刷新请求本身） */
  skipAuthRefresh?: boolean
  /** 已重放过一次的标记 */
  _retried?: boolean
}

async function handleResponse<T>(config: ApiRequestConfig, raw = false): Promise<T> {
  try {
    const response = await client.request<ApiEnvelope<T>>(config)
    const body = response.data as ApiEnvelope<T>
    if (raw) return body as unknown as T
    if (body && typeof body === 'object' && 'code' in body) {
      if (body.code === 0) return body.data
      if (body.code === 40003) {
        showConflictBox(body.message || '该记录已被其他用户修改，请刷新后重新编辑')
      }
      throw new ApiError(body.message || '请求失败', body.code, response.status, body.data)
    }
    return body as unknown as T
  } catch (error) {
    if (error instanceof ApiError) throw error
    const axiosError = error as AxiosError<ApiEnvelope>
    const status = axiosError.response?.status ?? 0
    const envelope = axiosError.response?.data
    const code = envelope?.code ?? (status === 401 ? 40002 : status === 404 ? 40005 : 50000)

    // 401 → 单飞刷新后重放
    const isAuthPath = NO_REFRESH_PATHS.some((p) => (config.url || '').startsWith(p))
    if ((status === 401 || code === 40002) && !isAuthPath && !config._retried && tokenStore.refresh) {
      try {
        const access = await refreshTokens()
        return await handleResponse<T>(
          { ...config, _retried: true, headers: { ...(config.headers ?? {}), Authorization: `Bearer ${access}` } },
          raw,
        )
      } catch {
        tokenStore.clear()
      }
    }

    if (code === 40003) {
      showConflictBox(envelope?.message || '该记录已被其他用户修改，请刷新后重新编辑')
    }

    const message =
      envelope?.message ||
      (status === 0 ? '网络异常，请检查服务是否可用' : status === 404 ? '资源不存在' : '请求失败')
    throw new ApiError(message, code, status, envelope?.data)
  }
}

export const api = {
  get: <T>(url: string, config?: ApiRequestConfig) =>
    handleResponse<T>({ ...config, url, method: 'get' }),
  post: <T>(url: string, data?: unknown, config?: ApiRequestConfig) =>
    handleResponse<T>({ ...config, url, method: 'post', data }),
  put: <T>(url: string, data?: unknown, config?: ApiRequestConfig) =>
    handleResponse<T>({ ...config, url, method: 'put', data }),
  patch: <T>(url: string, data?: unknown, config?: ApiRequestConfig) =>
    handleResponse<T>({ ...config, url, method: 'patch', data }),
  delete: <T>(url: string, config?: ApiRequestConfig) =>
    handleResponse<T>({ ...config, url, method: 'delete' }),
  /** 需要拿到 code/warning 等信封字段时使用，返回完整 { code, message, data } */
  raw: <T>(config: ApiRequestConfig) => handleResponse<ApiEnvelope<T>>(config, true),
}

/** 统一错误提示（页面里可直接 catch 后调用） */
export function notifyError(error: unknown) {
  const message = error instanceof ApiError ? error.message : '操作失败，请稍后重试'
  ElMessage.error(message)
}
