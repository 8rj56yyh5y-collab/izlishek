<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'
import type { TimelinePoint } from '@/api'
import { dateUa, devKg, devMoney } from '@/format'
import { t } from '@/i18n'
import { theme } from '@/theme'

echarts.use([BarChart, GridComponent, TooltipComponent, SVGRenderer])

const props = defineProps<{ points: TimelinePoint[] }>()
const emit = defineEmits<{ pick: [id: number] }>()
const el = ref<HTMLDivElement>()
let chart: echarts.ECharts | null = null

const css = (n: string) => getComputedStyle(document.documentElement).getPropertyValue(n).trim()

function render() {
  if (!chart) return
  const pos = css('--mg-positive'), neg = css('--mg-negative'), muted = css('--mg-fg-3'), border = css('--mg-border')
  chart.setOption({
    grid: { left: 8, right: 8, top: 16, bottom: 8, containLabel: true },
    tooltip: {
      trigger: 'axis', axisPointer: { type: 'shadow' },
      formatter: (ps: { dataIndex: number }[]) => {
        const p = props.points[ps[0].dataIndex]
        return `<b>${dateUa(p.ship_date)}</b> · ${p.point_name}<br/>${p.receiver_name}<br/>` +
          `${devKg(p.deviation_kg)} ${t('common.kg')} · <b>${devMoney(p.deviation_amount)}</b>`
      },
    },
    xAxis: {
      type: 'category', data: props.points.map((p) => dateUa(p.ship_date).slice(0, 5)),
      axisLine: { lineStyle: { color: border } }, axisTick: { show: false }, axisLabel: { color: muted },
    },
    yAxis: {
      type: 'value', splitLine: { lineStyle: { color: border } },
      axisLabel: { color: muted, formatter: (v: number) => `${v} ₴` },
    },
    series: [{
      type: 'bar', barMaxWidth: 28,
      data: props.points.map((p) => ({
        value: Math.round(p.deviation_amount),
        itemStyle: { color: p.deviation_amount >= 0 ? pos : neg, borderRadius: p.deviation_amount >= 0 ? [4, 4, 0, 0] : [0, 0, 4, 4] },
      })),
    }],
  }, true)
}

const onResize = () => chart?.resize()
onMounted(() => {
  chart = echarts.init(el.value!, undefined, { renderer: 'svg' })
  chart.on('click', (e) => emit('pick', props.points[e.dataIndex as number].shipment_id))
  render()
  window.addEventListener('resize', onResize)
})
onBeforeUnmount(() => { window.removeEventListener('resize', onResize); chart?.dispose() })
watch(() => props.points, render, { deep: true })
// Кольори беруться з CSS-токенів — після зміни теми перемальовуємо.
watch(theme, () => requestAnimationFrame(render))
</script>

<template>
  <div ref="el" style="height: 240px; width: 100%" />
</template>
