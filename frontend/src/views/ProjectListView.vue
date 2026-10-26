<template>
  <section class="page">
    <PageHeader title="项目" subtitle="管理可访问的测试项目，点击进入项目工作区">
      <template #actions>
        <el-input
          v-model="keyword"
          class="search-input"
          placeholder="按名称 / Key 搜索"
          clearable
          :prefix-icon="Search"
        />
        <el-button type="primary" @click="createVisible = true">新建项目</el-button>
      </template>
    </PageHeader>

    <!-- 错误态 -->
    <div v-if="error" class="state-panel">
      <p class="state-text">{{ error }}</p>
      <el-button size="small" @click="loadProjects">重新加载</el-button>
    </div>

    <!-- 列表 -->
    <div v-else v-loading="loading" class="table-panel">
      <el-table :data="filteredProjects" @row-click="onRowClick">
        <el-table-column prop="key" label="Key" width="120">
          <template #default="{ row }">
            <span class="key-cell">{{ row.key }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="项目名称" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="name-cell">{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <StatusTag :tone="row.status === 'active' ? 'accent' : 'neutral'">
              {{ row.status === 'active' ? '进行中' : '已归档' }}
            </StatusTag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="desc-cell">{{ row.description || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="150">
          <template #default="{ row }">
            <span class="time-cell">{{ formatTime(row.updated_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="" width="90" align="right">
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="enterProject(row)">进入</el-button>
          </template>
        </el-table-column>

        <template #empty>
          <div class="empty-state">
            <template v-if="keyword">
              <p class="state-text">没有匹配「{{ keyword }}」的项目</p>
              <el-button size="small" text type="primary" @click="keyword = ''">清空搜索</el-button>
            </template>
            <template v-else>
              <p class="state-text">暂无项目</p>
              <el-button size="small" type="primary" @click="createVisible = true">新建项目</el-button>
            </template>
          </div>
        </template>
      </el-table>
    </div>

    <ProjectForm v-model:visible="createVisible" @created="loadProjects" />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import { api, notifyError, type PageResult } from '@/api/client'
import PageHeader from '@/components/ui/PageHeader.vue'
import StatusTag from '@/components/ui/StatusTag.vue'
import ProjectForm from '@/views/projects/ProjectForm.vue'

/** 项目列表项（ProjectSerializer） */
interface ProjectItem {
  id: number
  key: string
  name: string
  description: string
  status: string
  updated_at: string
}

const router = useRouter()
const projects = ref<ProjectItem[]>([])
const loading = ref(false)
const error = ref('')
const keyword = ref('')
const createVisible = ref(false)

/** 前端按名称 / Key 过滤 */
const filteredProjects = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  if (!q) return projects.value
  return projects.value.filter(
    (item) => item.name.toLowerCase().includes(q) || item.key.toLowerCase().includes(q),
  )
})

function formatTime(value: string): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

async function loadProjects() {
  loading.value = true
  error.value = ''
  try {
    const data = await api.get<PageResult<ProjectItem>>('/projects/', {
      params: { page_size: 100 },
    })
    projects.value = data.items
  } catch (e) {
    error.value = notifyErrorAndGet(e)
  } finally {
    loading.value = false
  }
}

function notifyErrorAndGet(e: unknown): string {
  const message = e instanceof Error ? e.message : '加载项目列表失败，请稍后重试'
  notifyError(e)
  return message
}

function enterProject(row: ProjectItem) {
  router.push({ name: 'project-overview', params: { projectId: String(row.id) } })
}

function onRowClick(row: ProjectItem) {
  enterProject(row)
}

onMounted(loadProjects)
</script>

<style scoped>
.page {
  padding: var(--sp-6);
}

.search-input {
  width: 220px;
}

.table-panel {
  background: var(--bg-surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.key-cell {
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--accent-600);
}

.name-cell {
  font-weight: 500;
  color: var(--text-primary);
}

.desc-cell {
  color: var(--text-secondary);
}

.time-cell {
  font-size: var(--fs-sm);
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
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

/* 整行可点击进入项目；行高收敛到 38px 左右 */
:deep(.el-table__row) {
  cursor: pointer;
}

:deep(.el-table td.el-table__cell) {
  padding: 9px 0;
}
</style>
