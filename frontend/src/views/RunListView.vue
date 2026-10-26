<template>
  <section class="page">
    <PageHeader title="测试执行" subtitle="项目内全部执行轮次，进入执行页记录结果或查看报告" />

    <div class="panel">
      <!-- 加载失败：错误态 + 重试 -->
      <div v-if="error" class="state-box">
        <p class="state-text">{{ error }}</p>
        <el-button size="small" @click="load">重新加载</el-button>
      </div>

      <template v-else>
        <el-table v-loading="loading" :data="runs" row-key="run_id" @row-click="goRun">
          <el-table-column label="轮次名称" min-width="240">
            <template #default="{ row }">
              <span class="run-name">{{ row.name }}</span>
            </template>
          </el-table-column>
          <el-table-column label="环境" width="110">
            <template #default="{ row }">{{ row.environment || '—' }}</template>
          </el-table-column>
          <el-table-column label="构建版本" width="110">
            <template #default="{ row }">
              <span class="mono">{{ row.build_version || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <StatusTag :tone="runTone(row.status)" :label="runLabel(row.status)" />
            </template>
          </el-table-column>
          <el-table-column label="结果统计" width="180">
            <template #default="{ row }">
              <span class="stat-line">
                <span class="stat pass">通过 {{ row.passed }}</span>
                <span class="stat fail">失败 {{ row.failed }}</span>
                <span class="stat">未执行 {{ row.not_run }}</span>
              </span>
            </template>
          </el-table-column>
          <el-table-column label="通过率" width="150">
            <template #default="{ row }">
              <div class="rate-cell">
                <el-progress
                  :percentage="Math.round(row.pass_rate * 100)"
                  :stroke-width="4"
                  :show-text="false"
                  class="rate-bar"
                />
                <span class="mono rate-text">{{ Math.round(row.pass_rate * 100) }}%</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="开始时间" width="150">
            <template #default="{ row }">
              <span class="muted">{{ fmtTime(row.started_at) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="" width="130" align="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click.stop="goRun(row)">执行</el-button>
              <el-button link size="small" @click.stop="goReport(row)">报告</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-empty v-if="!loading && runs.length === 0" description="暂无执行轮次，请先在测试计划中开始执行" />

        <div v-if="total > 0" class="pager">
          <el-pagination
            :current-page="page"
            :page-size="pageSize"
            :total="total"
            layout="total, prev, pager, next"
            @current-change="onPageChange"
          />
        </div>
      </template>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, type PageResult } from '@/api/client'
import PageHeader from '@/components/ui/PageHeader.vue'
import StatusTag from '@/components/ui/StatusTag.vue'

/** run 摘要（GET /projects/{id}/reports/ 列表项） */
interface RunSummary {
  run_id: number
  name: string
  status: string
  environment: string
  build_version: string
  started_at: string | null
  finished_at: string | null
  total: number
  passed: number
  failed: number
  not_run: number
  pass_rate: number
}

type Tone = 'pass' | 'fail' | 'block' | 'skip' | 'warn' | 'info' | 'neutral' | 'accent'

const RUN_STATUS: Record<string, { label: string; tone: Tone }> = {
  created: { label: '已创建', tone: 'info' },
  running: { label: '执行中', tone: 'accent' },
  finished: { label: '已完成', tone: 'pass' },
  cancelled: { label: '已取消', tone: 'skip' },
}

function runLabel(status: string): string {
  return RUN_STATUS[status]?.label ?? status
}
function runTone(status: string): Tone {
  return RUN_STATUS[status]?.tone ?? 'neutral'
}

function fmtTime(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.projectId)

const runs = ref<RunSummary[]>([])
const loading = ref(false)
const error = ref('')
const page = ref(1)
const pageSize = 20
const total = ref(0)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await api.get<PageResult<RunSummary>>(`/projects/${projectId}/reports/`, {
      params: { page: page.value, page_size: pageSize },
    })
    runs.value = data.items
    total.value = data.total
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载执行列表失败'
  } finally {
    loading.value = false
  }
}

function onPageChange(value: number) {
  page.value = value
  load()
}

function goRun(row: RunSummary) {
  router.push({ name: 'run-execution', params: { projectId, runId: row.run_id } })
}

function goReport(row: RunSummary) {
  router.push({ name: 'run-report', params: { projectId, runId: row.run_id } })
}

onMounted(load)
</script>

<style scoped>
.page {
  padding: var(--sp-6);
}

.panel {
  background: var(--bg-surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
}

.panel :deep(.el-table__row) {
  cursor: pointer;
}

.run-name {
  font-weight: 500;
  color: var(--text-primary);
}

.mono {
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
}

.muted {
  color: var(--text-tertiary);
  font-size: var(--fs-sm);
}

.stat-line {
  display: flex;
  gap: var(--sp-3);
  font-size: var(--fs-sm);
  color: var(--text-tertiary);
  white-space: nowrap;
}

.stat.pass {
  color: var(--status-pass);
}

.stat.fail {
  color: var(--status-fail);
}

.rate-cell {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.rate-bar {
  flex: 1;
  min-width: 60px;
}

.rate-text {
  width: 38px;
  text-align: right;
  color: var(--text-secondary);
}

.state-box {
  padding: var(--sp-10) var(--sp-6);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-3);
}

.state-text {
  margin: 0;
  color: var(--text-tertiary);
}

.pager {
  display: flex;
  justify-content: flex-end;
  padding: var(--sp-3) var(--sp-4);
  border-top: 1px solid var(--border-light);
}
</style>
