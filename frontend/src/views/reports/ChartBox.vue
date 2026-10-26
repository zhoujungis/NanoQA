<template>
  <div class="chart-box" :style="{ height }">
    <div v-if="loading" class="chart-state">
      <p class="chart-state-text">图表加载中…</p>
    </div>
    <div v-else-if="!option" class="chart-state">
      <p class="chart-state-text">{{ emptyText }}</p>
    </div>
    <div v-show="showCanvas" ref="canvasRef" class="chart-canvas" />
  </div>
</template>

<script setup lang="ts">
/**
 * ECharts 通用容器（报告页私有）
 * - 自适应尺寸（ResizeObserver），随容器宽度变化重绘
 * - loading / 空数据不渲染图表，展示优雅空态
 */
import { markRaw, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import type { ChartOption } from './chartTheme'

const props = withDefaults(
  defineProps<{
    option?: ChartOption | null
    loading?: boolean
    height?: string
    emptyText?: string
  }>(),
  {
    option: null,
    loading: false,
    height: '260px',
    emptyText: '暂无可展示的数据',
  },
)

const canvasRef = ref<HTMLDivElement | null>(null)
const showCanvas = ref(false)

let chart: ReturnType<typeof echarts.init> | null = null
let observer: ResizeObserver | null = null

/** 初始化（或复用）图表实例并应用配置 */
async function render() {
  if (!props.option) return
  showCanvas.value = true
  await nextTick()
  const el = canvasRef.value
  if (!el) return
  if (!chart) {
    chart = markRaw(echarts.init(el))
    observer = new ResizeObserver(() => chart?.resize())
    observer.observe(el)
  } else {
    chart.resize()
  }
  chart.setOption(props.option as never, true)
}

/** 无数据时销毁实例，避免挂到隐藏节点上 */
function teardown() {
  showCanvas.value = false
  observer?.disconnect()
  observer = null
  chart?.dispose()
  chart = null
}

watch(
  () => [props.option, props.loading] as const,
  ([option, loading]) => {
    if (option && !loading) render()
    else teardown()
  },
  { immediate: true },
)

onBeforeUnmount(teardown)
</script>

<style scoped>
.chart-box {
  position: relative;
  width: 100%;
}

.chart-canvas {
  width: 100%;
  height: 100%;
}

.chart-state {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-sunken);
  border-radius: var(--radius-md);
}

.chart-state-text {
  margin: 0;
  font-size: var(--fs-sm);
  color: var(--text-tertiary);
}
</style>
