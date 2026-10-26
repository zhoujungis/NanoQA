/**
 * 图表主题与图表封装（报告页私有）
 * - 颜色全部从 tokens.css 的 CSS 变量读取，图表与界面共用同一套配色语言
 * - ECharts 按需注册，控制打包体积
 */
import { BarChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'

// 按需注册：报告页只用到饼图（结果分布）与条形图（模块通过率）
use([PieChart, BarChart, GridComponent, TooltipComponent, CanvasRenderer])

export type ChartOption = Record<string, unknown>

/** 读取 :root 上的设计令牌（tokens.css） */
export function cssVar(name: string, fallback = ''): string {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return value || fallback
}

/** 执行结果状态 → 语义色变量（与 StatusTag 的状态色一致） */
const RESULT_COLOR_VARS: Record<string, string> = {
  passed: '--status-pass',
  failed: '--status-fail',
  blocked: '--status-block',
  skipped: '--status-skip',
  not_run: '--ink-300',
}

export function resultColor(status: string): string {
  return cssVar(RESULT_COLOR_VARS[status] || '--ink-400') || cssVar('--text-tertiary')
}

/** 通用 tooltip：白底、细描边、低对比阴影、圆角小 */
function tooltipBase(trigger: 'item' | 'axis'): ChartOption {
  return {
    trigger,
    confine: true,
    backgroundColor: cssVar('--bg-surface'),
    borderColor: cssVar('--border-default'),
    borderWidth: 1,
    padding: [8, 12],
    textStyle: { color: cssVar('--text-primary'), fontSize: 12 },
    extraCssText: 'box-shadow: var(--shadow-md); border-radius: var(--radius-md);',
  }
}

export interface DonutSlice {
  name: string
  value: number
  /** 语义色（来自 tokens.css） */
  color: string
}

/** 环形图（结果分布）：不渲染图例，由页面侧用 HTML 图例承载数字排版 */
export function donutOption(slices: DonutSlice[]): ChartOption {
  return {
    tooltip: {
      ...tooltipBase('item'),
      formatter: (params: unknown) => {
        const p = params as { name: string; value: number; percent?: number }
        return `${p.name}　${p.value} 条（${(p.percent ?? 0).toFixed(1)}%）`
      },
    },
    series: [
      {
        type: 'pie',
        radius: ['62%', '84%'],
        center: ['50%', '50%'],
        avoidLabelOverlap: true,
        label: { show: false },
        labelLine: { show: false },
        itemStyle: {
          borderColor: cssVar('--bg-surface'),
          borderWidth: 2,
          borderRadius: 3,
        },
        emphasis: { scaleSize: 4 },
        data: slices
          .filter((s) => s.value > 0)
          .map((s) => ({ name: s.name, value: s.value, itemStyle: { color: s.color } })),
      },
    ],
  }
}

export interface ModuleRateRow {
  module_name: string
  pass_rate: number
  passed: number
  total: number
}

/** 模块通过率横向条形图：单色克制，右侧直接标百分比 */
export function moduleBarOption(rows: ModuleRateRow[]): ChartOption {
  return {
    tooltip: {
      ...tooltipBase('axis'),
      formatter: (params: unknown) => {
        const list = params as { name: string; value: number }[]
        const row = rows.find((r) => r.module_name === list[0]?.name)
        if (!row) return ''
        return `${row.module_name}　通过 ${row.passed} / ${row.total}（${(row.pass_rate * 100).toFixed(1)}%）`
      },
    },
    // ECharts 6 移除了 grid.containLabel（每次 setOption 都会告警），
    // 按官方等价式：containLabel:true ≡ { outerBoundsMode: 'same', outerBoundsContain: 'axisLabel' }
    grid: {
      left: 4,
      right: 44,
      top: 10,
      bottom: 4,
      outerBoundsMode: 'same',
      outerBoundsContain: 'axisLabel',
    },
    xAxis: {
      type: 'value',
      max: 1,
      axisLabel: {
        color: cssVar('--text-tertiary'),
        fontSize: 11,
        formatter: (value: number) => `${Math.round(value * 100)}%`,
      },
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: cssVar('--border-light') } },
    },
    yAxis: {
      type: 'category',
      inverse: true,
      data: rows.map((r) => r.module_name),
      axisLabel: { color: cssVar('--text-secondary'), fontSize: 12 },
      axisLine: { lineStyle: { color: cssVar('--border-default') } },
      axisTick: { show: false },
    },
    series: [
      {
        type: 'bar',
        barWidth: 12,
        data: rows.map((r) => r.pass_rate),
        itemStyle: { color: cssVar('--accent-600'), borderRadius: [0, 3, 3, 0] },
        label: {
          show: true,
          position: 'right',
          color: cssVar('--text-tertiary'),
          fontSize: 11,
          formatter: (params: { value?: unknown }) => {
            const value = Number(params.value ?? 0)
            return `${(value * 100).toFixed(0)}%`
          },
        },
      },
    ],
  }
}
