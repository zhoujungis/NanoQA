<template>
  <span class="status-tag" :class="`tone-${tone}`">
    <span class="status-dot" />
    <slot>{{ label }}</slot>
  </span>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    tone?: 'pass' | 'fail' | 'block' | 'skip' | 'warn' | 'info' | 'neutral' | 'accent'
    label?: string
  }>(),
  { tone: 'neutral', label: '' },
)
</script>

<style scoped>
.status-tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 1px 8px 1px 6px;
  border-radius: var(--radius-sm);
  font-size: var(--fs-sm);
  font-weight: 500;
  line-height: 18px;
  white-space: nowrap;
}

.status-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
  flex: none;
}

.tone-pass {
  color: var(--status-pass);
  background: var(--success-50);
}
.tone-fail {
  color: var(--status-fail);
  background: var(--danger-50);
}
.tone-block {
  color: var(--status-block);
  background: var(--warning-50);
}
.tone-warn {
  color: var(--warning-600);
  background: var(--warning-50);
}
.tone-skip,
.tone-neutral {
  color: var(--text-tertiary);
  background: var(--bg-sunken);
}
.tone-info {
  color: var(--info-600);
  background: var(--info-50);
}
.tone-accent {
  color: var(--accent-600);
  background: var(--accent-50);
}
</style>
