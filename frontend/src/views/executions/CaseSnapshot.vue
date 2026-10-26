<template>
  <div class="snapshot">
    <!-- 版本快照标识：结果固定绑定执行时的用例版本 -->
    <div class="snapshot-head">
      <span class="version-badge">版本快照 v{{ snapshot?.version ?? '—' }}</span>
      <span v-if="snapshot?.change_summary" class="change-summary">{{ snapshot.change_summary }}</span>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="state-line">正在加载用例版本快照…</div>
    <!-- 空态 / 错误态 -->
    <div v-else-if="!snapshot" class="state-line">版本快照不可用，请刷新重试</div>

    <template v-else>
      <section v-if="snapshot.description" class="block">
        <div class="block-title">描述</div>
        <p class="block-text">{{ snapshot.description }}</p>
      </section>

      <section class="block">
        <div class="block-title">前置条件</div>
        <p class="block-text">{{ snapshot.precondition || '无' }}</p>
      </section>

      <section class="block">
        <div class="block-title">测试步骤</div>
        <el-table :data="snapshot.steps" size="small" class="steps-table">
          <el-table-column label="序号" width="64" align="center">
            <template #default="{ row }">
              <span class="mono">{{ row.order }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" min-width="240">
            <template #default="{ row }">
              <span class="step-text">{{ row.action }}</span>
            </template>
          </el-table-column>
          <el-table-column label="预期结果" min-width="240">
            <template #default="{ row }">
              <span class="step-expected">{{ row.expected }}</span>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="snapshot.steps.length === 0" description="该版本没有步骤" :image-size="48" />
      </section>

      <section v-if="snapshot.expected_result" class="block">
        <div class="block-title">预期结果</div>
        <p class="block-text">{{ snapshot.expected_result }}</p>
      </section>
    </template>

    <!-- 上次结果 / 备注 -->
    <section class="block">
      <div class="block-title">上次结果 / 备注</div>
      <div class="last-grid">
        <div class="last-item">
          <span class="last-label">结果</span>
          <span class="last-value">{{ result?.actual_result || '—' }}</span>
        </div>
        <div class="last-item">
          <span class="last-label">备注</span>
          <span class="last-value">{{ result?.comment || '—' }}</span>
        </div>
        <div class="last-item">
          <span class="last-label">执行</span>
          <span class="last-value muted">
            {{ result?.executed_by_name || '未执行' }}<template v-if="result?.executed_at"> · {{ fmtTime(result.executed_at) }}</template>
          </span>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import type { RunResult, VersionSnapshot } from './types'

defineProps<{
  snapshot: VersionSnapshot | null
  loading: boolean
  /** 当前结果（展示上次执行结果与备注） */
  result: RunResult | null
}>()

function fmtTime(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}
</script>

<style scoped>
.snapshot {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}

.snapshot-head {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
}

.version-badge {
  padding: 1px 8px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
  color: var(--text-secondary);
  background: var(--bg-sunken);
}

.change-summary {
  font-size: var(--fs-sm);
  color: var(--text-tertiary);
}

.state-line {
  padding: var(--sp-4) 0;
  font-size: var(--fs-sm);
  color: var(--text-tertiary);
}

.block-title {
  margin-bottom: var(--sp-2);
  font-size: var(--fs-xs);
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--text-tertiary);
}

.block-text {
  margin: 0;
  font-size: var(--fs-base);
  line-height: var(--lh-base);
  color: var(--text-primary);
  white-space: pre-wrap;
}

.steps-table {
  width: 100%;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
}

.step-text {
  color: var(--text-primary);
  white-space: pre-wrap;
}

.step-expected {
  color: var(--text-secondary);
  white-space: pre-wrap;
}

.mono {
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
}

.last-grid {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
  padding: var(--sp-3);
  background: var(--bg-sunken);
  border-radius: var(--radius-sm);
}

.last-item {
  display: flex;
  gap: var(--sp-3);
  font-size: var(--fs-sm);
}

.last-label {
  flex: none;
  width: 36px;
  color: var(--text-tertiary);
}

.last-value {
  color: var(--text-secondary);
  white-space: pre-wrap;
}

.muted {
  color: var(--text-tertiary);
}
</style>
