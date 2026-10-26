<template>
  <header class="page-header">
    <div class="page-header-main">
      <h1 class="page-header-title">{{ title }}</h1>
      <p v-if="subtitle || $slots.subtitle" class="page-header-subtitle">
        <slot name="subtitle">{{ subtitle }}</slot>
      </p>
    </div>
    <div v-if="$slots.actions" class="page-header-actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  subtitle?: string
}>()
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--sp-4);
  margin-bottom: var(--sp-5);
}

.page-header-title {
  margin: 0;
  font-size: var(--fs-xl);
  font-weight: 600;
  line-height: var(--lh-tight);
  letter-spacing: 0.01em;
}

.page-header-subtitle {
  margin: var(--sp-1) 0 0;
  color: var(--text-tertiary);
  font-size: var(--fs-base);
}

.page-header-actions {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex: none;
  padding-top: 2px;
}
</style>
