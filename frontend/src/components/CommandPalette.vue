<template>
  <!-- 命令面板：Ctrl+K 唤起 / Esc 关闭，Teleport 到 body -->
  <Teleport to="body">
    <Transition name="cp-fade">
      <div v-if="open" class="cp-overlay" @mousedown.self="closePalette">
        <div class="cp-panel" role="dialog" aria-label="命令面板">
          <div class="cp-input-row">
            <span class="cp-input-prefix">/</span>
            <input
              ref="inputRef"
              v-model="query"
              class="cp-input"
              type="text"
              placeholder="搜索页面、项目、用例、缺陷…"
              autocomplete="off"
              spellcheck="false"
              @keydown="onInputKeydown"
            />
            <span class="cp-input-hint">Esc 关闭</span>
          </div>

          <div ref="listRef" class="cp-list">
            <template v-for="group in groups" :key="group.key">
              <div class="cp-group-title">
                {{ group.label }}
                <span v-if="group.loading" class="cp-group-loading">搜索中…</span>
              </div>
              <div
                v-for="item in group.items"
                :key="item.key"
                :data-index="item.flatIndex"
                class="cp-item"
                :class="{ 'is-active': item.flatIndex === selectedIndex }"
                @mousemove="selectedIndex = item.flatIndex"
                @click="execute(item)"
              >
                <span class="cp-item-label">{{ item.label }}</span>
                <span v-if="item.sub" class="cp-item-sub">{{ item.sub }}</span>
                <span class="cp-item-kind">{{ item.kindLabel }}</span>
              </div>
            </template>

            <div v-if="groups.length === 0" class="cp-empty">
              <template v-if="searching">正在搜索…</template>
              <template v-else>没有匹配「{{ query }}」的结果</template>
            </div>
          </div>

          <div class="cp-footer">
            <span><kbd>↑</kbd><kbd>↓</kbd> 选择</span>
            <span><kbd>Enter</kbd> 打开</span>
            <span><kbd>Esc</kbd> 关闭</span>
            <span class="cp-footer-right"><kbd>?</kbd> 快捷键帮助</span>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>

  <!-- 快捷键帮助浮层："?" 打开 -->
  <Teleport to="body">
    <Transition name="cp-fade">
      <div v-if="helpOpen" class="cp-overlay" @mousedown.self="helpOpen = false">
        <div class="cp-help" role="dialog" aria-label="快捷键帮助">
          <div class="cp-help-head">
            <h2 class="cp-help-title">快捷键</h2>
            <span class="cp-input-hint">Esc 关闭</span>
          </div>
          <div class="cp-help-body">
            <div class="cp-help-group-title">全局</div>
            <div v-for="row in globalShortcuts" :key="row.keys" class="cp-help-row">
              <span class="cp-help-keys">
                <kbd v-for="k in row.keys.split(' ')" :key="k">{{ k }}</kbd>
              </span>
              <span class="cp-help-desc">{{ row.desc }}</span>
            </div>
            <div class="cp-help-group-title">项目内（g 前缀跳转）</div>
            <div v-for="row in navShortcuts" :key="row.keys" class="cp-help-row">
              <span class="cp-help-keys">
                <kbd v-for="k in row.keys.split(' ')" :key="k">{{ k }}</kbd>
              </span>
              <span class="cp-help-desc">{{ row.desc }}</span>
            </div>
            <div class="cp-help-group-title">测试执行页（局部）</div>
            <div v-for="row in runShortcuts" :key="row.keys" class="cp-help-row">
              <span class="cp-help-keys">
                <kbd v-for="k in row.keys.split(' ')" :key="k">{{ k }}</kbd>
              </span>
              <span class="cp-help-desc">{{ row.desc }}</span>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter, type RouteParams } from 'vue-router'
import { api, type PageResult } from '@/api/client'

/** 命令面板条目 */
interface PaletteItem {
  key: string
  label: string
  sub?: string
  kindLabel: string
  flatIndex: number
  routeName: string
  params?: RouteParams
}

interface PaletteGroup {
  key: string
  label: string
  loading?: boolean
  items: PaletteItem[]
}

/** 近期访问记录（localStorage） */
interface RecentEntry {
  label: string
  kindLabel: string
  routeName: string
  params?: RouteParams
}

interface ProjectBrief {
  id: number
  key: string
  name: string
}

interface CaseBrief {
  id: number
  case_key: string
  title: string
}

interface DefectBrief {
  id: number
  key: string
  title: string
}

const RECENT_KEY = 'nanoqa.palette.recent'
const RECENT_MAX = 6

const route = useRoute()
const router = useRouter()

const open = ref(false)
const helpOpen = ref(false)
const query = ref('')
const selectedIndex = ref(0)
const inputRef = ref<HTMLInputElement | null>(null)
const listRef = ref<HTMLElement | null>(null)

const projects = ref<ProjectBrief[]>([])
const caseResults = ref<CaseBrief[]>([])
const defectResults = ref<DefectBrief[]>([])
const searching = ref(false)
const recent = ref<RecentEntry[]>(loadRecent())

const projectId = computed(() => Number(route.params.projectId) || 0)

/* ---------------- 静态导航项 ---------------- */

interface PageEntry {
  routeName: string
  label: string
  kindLabel: string
  scope: 'global' | 'project'
}

/** 全部菜单页：与 AppLayout 导航保持一致 */
const PAGE_ENTRIES: PageEntry[] = [
  { routeName: 'projects', label: '项目列表', kindLabel: '页面', scope: 'global' },
  { routeName: 'workbench', label: '工作台', kindLabel: '页面', scope: 'global' },
  { routeName: 'project-overview', label: '项目概览', kindLabel: '页面', scope: 'project' },
  { routeName: 'requirements', label: '需求', kindLabel: '页面', scope: 'project' },
  { routeName: 'testcases', label: '测试用例', kindLabel: '页面', scope: 'project' },
  { routeName: 'testplans', label: '测试计划', kindLabel: '页面', scope: 'project' },
  { routeName: 'runs', label: '测试执行', kindLabel: '页面', scope: 'project' },
  { routeName: 'defects', label: '缺陷', kindLabel: '页面', scope: 'project' },
  { routeName: 'reports', label: '测试报告', kindLabel: '页面', scope: 'project' },
  { routeName: 'ai-workspace', label: 'AI 助手', kindLabel: '页面', scope: 'project' },
  { routeName: 'members', label: '成员', kindLabel: '页面', scope: 'project' },
  { routeName: 'roles', label: '权限', kindLabel: '页面', scope: 'project' },
  { routeName: 'audit', label: '操作日志', kindLabel: '页面', scope: 'project' },
]

/* ---------------- 快捷键清单（帮助浮层） ---------------- */

const globalShortcuts = [
  { keys: 'Ctrl K', desc: '打开 / 关闭命令面板' },
  { keys: '?', desc: '打开快捷键帮助' },
  { keys: 'Esc', desc: '关闭面板与弹层' },
]

const navShortcuts = [
  { keys: 'g p', desc: '项目概览' },
  { keys: 'g t', desc: '测试用例' },
  { keys: 'g d', desc: '缺陷' },
  { keys: 'g r', desc: '需求' },
  { keys: 'g l', desc: '测试计划' },
  { keys: 'g e', desc: '测试执行' },
  { keys: 'g m', desc: '成员' },
  { keys: 'g a', desc: '操作日志' },
]

const runShortcuts = [
  { keys: 'P F B S', desc: '标记 Pass / Fail / Block / Skip' },
  { keys: 'N', desc: '下一条用例' },
]

/** g 前缀跳转映射（仅项目上下文） */
const G_PREFIX: Record<string, string> = {
  p: 'project-overview',
  t: 'testcases',
  d: 'defects',
  r: 'requirements',
  l: 'testplans',
  e: 'runs',
  m: 'members',
  a: 'audit',
}

/* ---------------- 结果分组 ---------------- */

const groups = computed<PaletteGroup[]>(() => {
  const q = query.value.trim().toLowerCase()
  const params: RouteParams | undefined = projectId.value
    ? { projectId: String(projectId.value) }
    : undefined

  const list: PaletteGroup[] = []
  let flat = 0
  const build = (key: string, label: string, raw: Omit<PaletteItem, 'flatIndex'>[], loading = false): PaletteGroup | null => {
    if (!raw.length) return null
    const items = raw.map((item) => ({ ...item, flatIndex: flat++ }))
    return { key, label, loading, items }
  }

  // 页面导航：项目内页面需项目上下文
  const pageItems = PAGE_ENTRIES.filter((entry) => {
    if (entry.scope === 'project' && !projectId.value) return false
    return !q || entry.label.toLowerCase().includes(q)
  }).map((entry) => ({
    key: `page:${entry.routeName}`,
    label: entry.label,
    kindLabel: entry.kindLabel,
    routeName: entry.routeName,
    params,
  }))

  // 项目切换
  const projectItems = projects.value
    .filter((p) => !q || p.name.toLowerCase().includes(q) || p.key.toLowerCase().includes(q))
    .map((p) => ({
      key: `project:${p.id}`,
      label: p.name,
      sub: p.key,
      kindLabel: '项目',
      routeName: 'project-overview',
      params: { projectId: String(p.id) } as RouteParams,
    }))

  if (q) {
    const pageGroup = build('pages', '页面', pageItems)
    if (pageGroup) list.push(pageGroup)
    const projectGroup = build('projects', '项目', projectItems.slice(0, 5))
    if (projectGroup) list.push(projectGroup)
    if (projectId.value) {
      const caseGroup = build(
        'cases',
        '用例',
        caseResults.value.map((c) => ({
          key: `case:${c.id}`,
          label: c.title,
          sub: c.case_key,
          kindLabel: '用例',
          routeName: 'testcase-detail',
          params: { projectId: String(projectId.value), caseId: String(c.id) } as RouteParams,
        })),
        searching.value,
      )
      if (caseGroup) list.push(caseGroup)
      const defectGroup = build(
        'defects',
        '缺陷',
        defectResults.value.map((d) => ({
          key: `defect:${d.id}`,
          label: d.title,
          sub: d.key,
          kindLabel: '缺陷',
          routeName: 'defect-detail',
          params: { projectId: String(projectId.value), defectId: String(d.id) } as RouteParams,
        })),
        searching.value,
      )
      if (defectGroup) list.push(defectGroup)
    }
  } else {
    const recentGroup = build(
      'recent',
      '近期访问',
      recent.value.map((r, i) => ({
        key: `recent:${i}:${r.routeName}`,
        label: r.label,
        kindLabel: r.kindLabel,
        routeName: r.routeName,
        params: r.params,
      })),
    )
    if (recentGroup) list.push(recentGroup)
    const pageGroup = build('pages', '页面', pageItems)
    if (pageGroup) list.push(pageGroup)
    const projectGroup = build('projects', '项目', projectItems)
    if (projectGroup) list.push(projectGroup)
  }
  return list
})

const flatItems = computed<PaletteItem[]>(() => groups.value.flatMap((g) => g.items))

watch(groups, () => {
  if (selectedIndex.value >= flatItems.value.length) selectedIndex.value = 0
})

/* ---------------- 搜索（300ms 防抖） ---------------- */

let debounceTimer: ReturnType<typeof setTimeout> | null = null
let searchSeq = 0

watch(query, () => {
  selectedIndex.value = 0
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(runEntitySearch, 300)
})

async function runEntitySearch() {
  const q = query.value.trim()
  if (!q || !projectId.value) {
    caseResults.value = []
    defectResults.value = []
    searching.value = false
    return
  }
  const seq = ++searchSeq
  searching.value = true
  try {
    const [cases, defects] = await Promise.all([
      api.get<PageResult<CaseBrief>>(`/projects/${projectId.value}/testcases/`, {
        params: { q, page_size: 5 },
      }),
      api.get<PageResult<DefectBrief>>(`/projects/${projectId.value}/defects/`, {
        params: { q, page_size: 5 },
      }),
    ])
    if (seq !== searchSeq) return
    caseResults.value = cases.items
    defectResults.value = defects.items
  } catch {
    if (seq !== searchSeq) return
    caseResults.value = []
    defectResults.value = []
  } finally {
    if (seq === searchSeq) searching.value = false
  }
}

async function loadProjects() {
  try {
    const data = await api.get<PageResult<ProjectBrief>>('/projects/', { params: { page_size: 100 } })
    projects.value = data.items
  } catch {
    projects.value = []
  }
}

/* ---------------- 近期访问 ---------------- */

function loadRecent(): RecentEntry[] {
  try {
    const raw = localStorage.getItem(RECENT_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed.slice(0, RECENT_MAX) : []
  } catch {
    return []
  }
}

function saveRecent(item: PaletteItem) {
  const entry: RecentEntry = {
    label: item.label,
    kindLabel: item.kindLabel,
    routeName: item.routeName,
    params: item.params,
  }
  const next = [
    entry,
    ...recent.value.filter((r) => !(r.routeName === entry.routeName && JSON.stringify(r.params) === JSON.stringify(entry.params))),
  ].slice(0, RECENT_MAX)
  recent.value = next
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(next))
  } catch {
    // localStorage 不可用时静默降级
  }
}

/* ---------------- 打开 / 关闭 / 执行 ---------------- */

function openPalette() {
  if (open.value) return
  helpOpen.value = false
  open.value = true
  selectedIndex.value = 0
  if (!projects.value.length) loadProjects()
  nextTick(() => inputRef.value?.focus())
}

function closePalette() {
  open.value = false
  query.value = ''
  caseResults.value = []
  defectResults.value = []
}

function togglePalette() {
  if (open.value) closePalette()
  else openPalette()
}

function execute(item: PaletteItem) {
  saveRecent(item)
  closePalette()
  router.push({ name: item.routeName, params: item.params ?? {} })
}

function scrollSelectedIntoView() {
  nextTick(() => {
    const container = listRef.value
    if (!container) return
    const el = container.querySelector<HTMLElement>(`[data-index="${selectedIndex.value}"]`)
    el?.scrollIntoView({ block: 'nearest' })
  })
}

function onInputKeydown(event: KeyboardEvent) {
  const total = flatItems.value.length
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    if (!total) return
    selectedIndex.value = (selectedIndex.value + 1) % total
    scrollSelectedIntoView()
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    if (!total) return
    selectedIndex.value = (selectedIndex.value - 1 + total) % total
    scrollSelectedIntoView()
  } else if (event.key === 'Enter') {
    event.preventDefault()
    const item = flatItems.value[selectedIndex.value]
    if (item) execute(item)
  } else if (event.key === 'Escape') {
    event.preventDefault()
    closePalette()
  }
}

/* ---------------- 全局快捷键（§58） ---------------- */

/** 输入框 / 文本域 / 可编辑区聚焦时不触发 */
function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  const tag = target.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target.isContentEditable
}

/** Element Plus 弹层打开时不抢快捷键（命令面板自身除外） */
function elOverlayOpen(): boolean {
  return Boolean(document.querySelector('.el-overlay'))
}

let gPending = false
let gTimer: ReturnType<typeof setTimeout> | null = null

function clearGPending() {
  gPending = false
  if (gTimer) {
    clearTimeout(gTimer)
    gTimer = null
  }
}

function onGlobalKeydown(event: KeyboardEvent) {
  // Ctrl+K（Mac 同样按 Ctrl+K）：唤起 / 关闭命令面板
  if ((event.ctrlKey || event.metaKey) && !event.altKey && event.key.toLowerCase() === 'k') {
    event.preventDefault()
    togglePalette()
    return
  }

  if (event.ctrlKey || event.metaKey || event.altKey) return

  // 面板打开时由输入框处理键盘
  if (open.value) return

  if (event.key === 'Escape' && helpOpen.value) {
    event.preventDefault()
    helpOpen.value = false
    return
  }

  if (isTypingTarget(event.target) || elOverlayOpen()) {
    clearGPending()
    return
  }

  // "?"：快捷键帮助
  if (event.key === '?') {
    event.preventDefault()
    helpOpen.value = !helpOpen.value
    return
  }

  // g 前缀跳转（仅项目上下文，不影响执行页单键快捷键）
  if (event.key === 'g') {
    gPending = true
    if (gTimer) clearTimeout(gTimer)
    gTimer = setTimeout(clearGPending, 1200)
    return
  }

  if (gPending) {
    clearGPending()
    const target = G_PREFIX[event.key.toLowerCase()]
    if (target && projectId.value) {
      // 消费该按键，避免执行页 P/F/B/S/N 局部快捷键误触发
      event.preventDefault()
      event.stopImmediatePropagation()
      router.push({ name: target, params: { projectId: String(projectId.value) } })
    }
  }
}

onMounted(() => {
  window.addEventListener('keydown', onGlobalKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onGlobalKeydown)
  if (debounceTimer) clearTimeout(debounceTimer)
  if (gTimer) clearTimeout(gTimer)
})
</script>

<style scoped>
/* ---------------- 遮罩与面板 ---------------- */
.cp-overlay {
  position: fixed;
  inset: 0;
  z-index: var(--z-dialog);
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding-top: 12vh;
  background: color-mix(in srgb, var(--ink-900) 30%, transparent);
}

.cp-panel {
  width: min(620px, calc(100vw - var(--sp-8)));
  background: var(--bg-surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.cp-input-row {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: 0 var(--sp-4);
  height: 46px;
  border-bottom: 1px solid var(--border-light);
}

.cp-input-prefix {
  color: var(--text-placeholder);
  font-family: var(--font-mono);
  font-size: var(--fs-md);
  flex: none;
}

.cp-input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text-primary);
  font-size: var(--fs-lg);
  font-family: var(--font-sans);
}

.cp-input::placeholder {
  color: var(--text-placeholder);
}

.cp-input-hint {
  flex: none;
  color: var(--text-placeholder);
  font-size: var(--fs-xs);
}

/* ---------------- 结果列表 ---------------- */
.cp-list {
  max-height: 46vh;
  overflow-y: auto;
  padding: var(--sp-2) 0;
}

.cp-group-title {
  padding: var(--sp-2) var(--sp-4) var(--sp-1);
  color: var(--text-tertiary);
  font-size: var(--fs-xs);
  font-weight: 600;
  letter-spacing: 0.08em;
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.cp-group-loading {
  font-weight: 400;
  letter-spacing: 0;
  color: var(--text-placeholder);
}

.cp-item {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  margin: 0 var(--sp-2);
  padding: 0 var(--sp-3);
  height: 38px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--dur-fast) var(--ease-out);
}

.cp-item.is-active {
  background: var(--bg-active);
}

.cp-item-label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-primary);
  font-size: var(--fs-md);
}

.cp-item.is-active .cp-item-label {
  font-weight: 600;
}

.cp-item-sub {
  flex: none;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
  font-family: var(--font-mono);
}

.cp-item-kind {
  flex: none;
  color: var(--text-placeholder);
  font-size: var(--fs-xs);
}

.cp-empty {
  padding: var(--sp-8) var(--sp-4);
  text-align: center;
  color: var(--text-tertiary);
  font-size: var(--fs-base);
}

/* ---------------- 底部提示 ---------------- */
.cp-footer {
  display: flex;
  align-items: center;
  gap: var(--sp-4);
  padding: var(--sp-2) var(--sp-4);
  border-top: 1px solid var(--border-light);
  background: var(--bg-sunken);
  color: var(--text-tertiary);
  font-size: var(--fs-xs);
}

.cp-footer-right {
  margin-left: auto;
}

.cp-footer kbd,
.cp-help-keys kbd {
  display: inline-block;
  min-width: 18px;
  padding: 0 5px;
  margin: 0 2px;
  border: 1px solid var(--border-default);
  border-bottom-width: 2px;
  border-radius: var(--radius-sm);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
  line-height: 18px;
  text-align: center;
}

/* ---------------- 快捷键帮助浮层 ---------------- */
.cp-help {
  width: min(520px, calc(100vw - var(--sp-8)));
  max-height: 70vh;
  background: var(--bg-surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.cp-help-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--sp-3) var(--sp-4);
  border-bottom: 1px solid var(--border-light);
}

.cp-help-title {
  margin: 0;
  font-size: var(--fs-lg);
  font-weight: 600;
}

.cp-help-body {
  padding: var(--sp-3) var(--sp-4) var(--sp-4);
  overflow-y: auto;
}

.cp-help-group-title {
  margin: var(--sp-3) 0 var(--sp-1);
  color: var(--text-tertiary);
  font-size: var(--fs-xs);
  font-weight: 600;
  letter-spacing: 0.08em;
}

.cp-help-group-title:first-child {
  margin-top: 0;
}

.cp-help-row {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  height: 34px;
  border-bottom: 1px solid var(--border-light);
}

.cp-help-row:last-child {
  border-bottom: none;
}

.cp-help-keys {
  flex: none;
  width: 110px;
}

.cp-help-desc {
  color: var(--text-secondary);
  font-size: var(--fs-base);
}

/* ---------------- 动效（短促） ---------------- */
.cp-fade-enter-active,
.cp-fade-leave-active {
  transition: opacity var(--dur-fast) var(--ease-out);
}

.cp-fade-enter-from,
.cp-fade-leave-to {
  opacity: 0;
}

.cp-fade-enter-active .cp-panel,
.cp-fade-enter-active .cp-help,
.cp-fade-leave-active .cp-panel,
.cp-fade-leave-active .cp-help {
  transition: transform var(--dur-base) var(--ease-out);
}

.cp-fade-enter-from .cp-panel,
.cp-fade-enter-from .cp-help {
  transform: translateY(-8px);
}
</style>
