<script setup lang="ts">
import type { ElectionEntity, NationalChartAnalysis, RegionalChartAnalysis } from '~/types/election'

const props = defineProps<{ analysis: NationalChartAnalysis | RegionalChartAnalysis, entities: ElectionEntity[], unitId: string }>()
const palette = ['#d6452e', '#356ae6', '#1b9467', '#d78418', '#8b52c7', '#bf3f79', '#138a9b', '#766f2c']
const selected = ref('')
const canvas = ref<HTMLCanvasElement>(); const tooltip = ref('')
const entities = computed(() => props.entities.map((entity, index) => ({ ...entity, color: palette[index % palette.length] })))
const entityIndex = computed(() => entities.value.findIndex(entity => entity.id === selected.value))
const national = computed(() => 'entities' in props.analysis)
watch(entities, list => { if (!list.some(entity => entity.id === selected.value)) selected.value = list[0]?.id || '' }, { immediate: true })
type Point = { turnout: number, share: number, count: number }
const points = computed<Point[]>(() => {
  const entity = entityIndex.value
  if (entity < 0) return []
  if (national.value) return props.analysis.clusters[entity].map(([turnout, share, count]) => ({ turnout: turnout / 100, share: share / 100, count }))
  const analysis = props.analysis as RegionalChartAnalysis
  const indexes = analysis.units[props.unitId]
  if (!indexes) return analysis.clusters[entity].map(([turnout, share, count]) => ({ turnout: turnout / 100, share: share / 100, count }))
  return indexes.flatMap(index => {
    const [turnout, valid, results] = analysis.points[index]
    for (let result = 0; result < results.length; result += 2) if (results[result] === entity) return [{ turnout: turnout / 100, share: valid ? results[result + 1] / valid * 100 : 0, count: 1 }]
    return []
  })
})
function draw(): void {
  const element = canvas.value; const context = element?.getContext('2d'); if (!element || !context) return
  const { width, height } = element; const left = 48; const right = 16; const top = 14; const bottom = 34
  const maxShare = Math.max(...points.value.map(point => point.share), 1); const color = entities.value[entityIndex.value]?.color || palette[0]
  context.clearRect(0, 0, width, height); context.font = '11px Manrope, sans-serif'; context.strokeStyle = '#51524c'; context.fillStyle = '#aaa69e'
  for (let step = 0; step <= 4; step += 1) { const y = top + (height - top - bottom) * step / 4; context.beginPath(); context.moveTo(left, y); context.lineTo(width - right, y); context.stroke(); context.fillText(`${(maxShare * (4 - step) / 4).toFixed(1)}%`, 0, y + 4) }
  for (let step = 0; step <= 5; step += 1) context.fillText(`${step * 20}%`, left + (width - left - right) * step / 5 - 10, height - 12)
  context.fillStyle = color
  for (const point of points.value) { const x = left + Math.min(100, Math.max(0, point.turnout)) / 100 * (width - left - right); const y = height - bottom - point.share / maxShare * (height - top - bottom); context.globalAlpha = Math.min(.82, .16 + Math.log2(point.count + 1) / 7); context.beginPath(); context.arc(x, y, Math.min(6, 1 + Math.sqrt(point.count)), 0, Math.PI * 2); context.fill() }
  context.globalAlpha = 1
}
function nearest(event: MouseEvent): void {
  const element = canvas.value; if (!element || !points.value.length) return
  const box = element.getBoundingClientRect(); const x = (event.clientX - box.left) / box.width * element.width; const y = (event.clientY - box.top) / box.height * element.height; const maxShare = Math.max(...points.value.map(point => point.share), 1); const left = 48; const right = 16; const top = 14; const bottom = 34
  let hit: Point | undefined; let distance = Infinity
  for (const point of points.value) { const px = left + point.turnout / 100 * (element.width - left - right); const py = element.height - bottom - point.share / maxShare * (element.height - top - bottom); const next = (px - x) ** 2 + (py - y) ** 2; if (next < distance) { hit = point; distance = next } }
  tooltip.value = hit && distance < 900 ? `Явка ${hit.turnout.toFixed(1)}% · доля ${hit.share.toFixed(2)}%${hit.count > 1 ? ` · ${hit.count} УИК` : ''}` : ''
}
watch(points, () => nextTick(draw), { flush: 'post' }); onMounted(draw)
</script>
<template><section class="shpilkin-chart"><div class="chart-head"><div><span class="eyebrow">АНАЛИЗ УИК</span><h3>Метод Шпилькина</h3></div><select v-model="selected"><option v-for="entity in entities" :key="entity.id" :value="entity.id">{{ entity.name }}</option></select></div><p class="chart-subtitle">X — явка, Y — доля действительных голосов выбранного кандидата или списка.</p><canvas ref="canvas" width="960" height="420" @mousemove="nearest" @mouseleave="tooltip = ''" /><p class="chart-note">{{ tooltip || 'Каждая точка — УИК; близкие точки на крупных выборках сгруппированы сервером.' }}</p><div class="chart-legend"><span v-for="entity in entities" :key="entity.id"><i :style="{ background: entity.color }" />{{ entity.name }}</span></div></section></template>
