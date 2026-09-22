<script setup lang="ts">
import type { ElectionEntity, NationalChartAnalysis, RegionalChartAnalysis } from '~/types/election'

const props = defineProps<{ analysis: NationalChartAnalysis | RegionalChartAnalysis, entities: ElectionEntity[], unitId: string }>()
const palette = ['#356ae6', '#d6452e', '#1b9467', '#d78418', '#8b52c7', '#bf3f79', '#138a9b', '#766f2c']
const canvas = ref<HTMLCanvasElement>(); const absoluteCanvas = ref<HTMLCanvasElement>(); const tooltip = ref('')
const shareHover = ref<{ x: number, y: number } | null>(null); const absoluteHover = ref<{ x: number, y: number } | null>(null)
const active = ref<string[]>([])
const entities = computed(() => props.entities.map((entity, index) => ({ ...entity, color: palette[index % palette.length] })))
const activeIndexes = computed(() => new Set(active.value.map(id => entities.value.findIndex(entity => entity.id === id)).filter(index => index >= 0)))
const national = computed(() => 'entities' in props.analysis)
watch(entities, list => { active.value = active.value.filter(id => list.some(entity => entity.id === id)); if (!active.value.length && list[0]) active.value = [list[0].id] }, { immediate: true })
type Point = { turnout: number, share: number, count: number, entity: number }
const pointsByEntity = computed<Point[][]>(() => {
  const output = entities.value.map(() => [] as Point[])
  if (national.value) {
    for (let entity = 0; entity < output.length; entity += 1) for (const [turnout, share, count] of props.analysis.clusters[entity] || []) output[entity].push({ turnout: turnout / 100, share: share / 100, count, entity })
    return output
  }
  const analysis = props.analysis as RegionalChartAnalysis
  const indexes = analysis.units[props.unitId]
  if (!indexes) {
    for (let entity = 0; entity < output.length; entity += 1) for (const [turnout, share, count] of analysis.clusters[entity] || []) output[entity].push({ turnout: turnout / 100, share: share / 100, count, entity })
    return output
  }
  for (const sourceIndex of indexes) {
    const [turnout, valid, results] = analysis.points[sourceIndex]
    for (let index = 0; index < results.length; index += 2) output[results[index]]?.push({ turnout: turnout / 100, share: valid ? results[index + 1] / valid * 100 : 0, count: 1, entity: results[index] })
  }
  return output
})
const points = computed<Point[]>(() => [...activeIndexes.value].flatMap((entity: number) => pointsByEntity.value[entity] || []))
const absoluteSeries = computed(() => [...activeIndexes.value].map(entity => ({ entity, points: (props.analysis.absolute[entity] || []).map(([turnout, votes, count]) => ({ turnout: turnout / 100, votes, count })) })))
function draw(): void {
  const element = canvas.value; const context = element?.getContext('2d'); if (!element || !context) return
  const { width, height } = element; const left = 48; const right = 16; const top = 14; const bottom = 34; const maxShare = 100
  context.clearRect(0, 0, width, height); context.font = '11px Manrope, sans-serif'; context.strokeStyle = '#d9dfe8'; context.fillStyle = '#697586'
  for (let step = 0; step <= 4; step += 1) { const y = top + (height - top - bottom) * step / 4; context.beginPath(); context.moveTo(left, y); context.lineTo(width - right, y); context.stroke(); context.fillText(`${(maxShare * (4 - step) / 4).toFixed(0)}%`, 0, y + 4) }
  for (let step = 0; step <= 5; step += 1) context.fillText(`${step * 20}%`, left + (width - left - right) * step / 5 - 10, height - 12)
  for (const point of points.value) { const x = left + Math.min(100, Math.max(0, point.turnout)) / 100 * (width - left - right); const y = height - bottom - point.share / maxShare * (height - top - bottom); context.fillStyle = entities.value[point.entity]?.color || palette[0]; context.globalAlpha = 1 - Math.pow(1 - .08, point.count); context.beginPath(); context.arc(x, y, 1.5, 0, Math.PI * 2); context.fill() }
  context.globalAlpha = 1
  if (shareHover.value) {
    const { x, y } = shareHover.value; const plotWidth = width - left - right; const plotHeight = height - top - bottom
    context.save(); context.strokeStyle = '#64748b'; context.lineWidth = 1; context.setLineDash([4, 4]); context.beginPath(); context.moveTo(x, top); context.lineTo(x, height - bottom); context.moveTo(left, y); context.lineTo(width - right, y); context.stroke(); context.setLineDash([]); context.fillStyle = '#334155'; context.font = '11px Manrope, sans-serif'; context.fillText(`${((x - left) / plotWidth * 100).toFixed(2)}%`, Math.min(width - 42, Math.max(left, x - 16)), height - 12); context.fillText(`${((height - bottom - y) / plotHeight * 100).toFixed(2)}%`, 0, Math.max(top + 11, y - 5)); context.restore()
  }
}
function nearest(event: MouseEvent): void {
  const element = canvas.value; if (!element) return
  const box = element.getBoundingClientRect(); const x = (event.clientX - box.left) / box.width * element.width; const y = (event.clientY - box.top) / box.height * element.height; shareHover.value = { x, y }; const left = 48; const right = 16; const top = 14; const bottom = 34
  let hit: Point | undefined; let distance = Infinity
  for (const point of points.value) { const px = left + point.turnout / 100 * (element.width - left - right); const py = element.height - bottom - point.share / 100 * (element.height - top - bottom); const next = (px - x) ** 2 + (py - y) ** 2; if (next < distance) { hit = point; distance = next } }
  tooltip.value = hit && distance < 900 ? `${entities.value[hit.entity]?.name} · явка ${hit.turnout.toFixed(2)}% · доля ${hit.share.toFixed(2)}%${hit.count > 1 ? ` · ${hit.count} УИК` : ''}` : ''
  draw()
}
function drawAbsolute(): void {
  const element = absoluteCanvas.value; const context = element?.getContext('2d'); if (!element || !context) return
  const { width, height } = element; const left = 48; const right = 16; const top = 14; const bottom = 34; const maxVotes = Math.max(...absoluteSeries.value.flatMap(series => series.points.map(point => point.votes)), 1)
  context.clearRect(0, 0, width, height); context.font = '11px Manrope, sans-serif'; context.strokeStyle = '#d9dfe8'; context.fillStyle = '#697586'
  for (let step = 0; step <= 4; step += 1) { const y = top + (height - top - bottom) * step / 4; context.beginPath(); context.moveTo(left, y); context.lineTo(width - right, y); context.stroke(); context.fillText(Math.round(maxVotes * (4 - step) / 4).toLocaleString('ru-RU'), 0, y + 4) }
  for (let step = 0; step <= 5; step += 1) context.fillText(`${step * 20}%`, left + (width - left - right) * step / 5 - 10, height - 12)
  for (const series of absoluteSeries.value) { context.strokeStyle = entities.value[series.entity]?.color || palette[0]; context.lineWidth = 1.5; context.globalAlpha = .9; context.beginPath(); series.points.forEach((point, index) => { const x = left + point.turnout / 100 * (width - left - right); const y = height - bottom - point.votes / maxVotes * (height - top - bottom); if (index === 0) context.moveTo(x, y); else context.lineTo(x, y) }); context.stroke() }
  context.globalAlpha = 1
  if (absoluteHover.value) {
    const { x, y } = absoluteHover.value; const plotWidth = width - left - right; const plotHeight = height - top - bottom
    context.save(); context.strokeStyle = '#64748b'; context.lineWidth = 1; context.setLineDash([4, 4]); context.beginPath(); context.moveTo(x, top); context.lineTo(x, height - bottom); context.moveTo(left, y); context.lineTo(width - right, y); context.stroke(); context.setLineDash([]); context.fillStyle = '#334155'; context.font = '11px Manrope, sans-serif'; context.fillText(`${((x - left) / plotWidth * 100).toFixed(2)}%`, Math.min(width - 42, Math.max(left, x - 16)), height - 12); context.fillText(Math.round((height - bottom - y) / plotHeight * maxVotes).toLocaleString('ru-RU'), 0, Math.max(top + 11, y - 5)); context.restore()
  }
}
function absoluteMove(event: MouseEvent): void { const element = absoluteCanvas.value; if (!element) return; const box = element.getBoundingClientRect(); absoluteHover.value = { x: (event.clientX - box.left) / box.width * element.width, y: (event.clientY - box.top) / box.height * element.height }; drawAbsolute() }
function clearShareHover(): void { shareHover.value = null; tooltip.value = ''; draw() }
function clearAbsoluteHover(): void { absoluteHover.value = null; drawAbsolute() }
function toggle(id: string): void { active.value = active.value.includes(id) ? active.value.filter(value => value !== id) : [...active.value, id] }
watch([points, absoluteSeries], () => nextTick(() => { draw(); drawAbsolute() }), { flush: 'post' }); onMounted(() => { draw(); drawAbsolute() })
</script>
<template><section class="shpilkin-chart"><div class="chart-head"><div><span class="eyebrow">АНАЛИЗ УИК</span><h3>Метод Шпилькина</h3></div></div><div class="chart-layout"><div class="chart-main"><p class="chart-title">Явка (%) / доля голосов (%) — облако УИК</p><canvas ref="canvas" width="640" height="640" @mousemove="nearest" @mouseleave="clearShareHover" /><p class="chart-note">{{ tooltip || 'Точки совпадающих протоколов становятся плотнее.' }}</p><p class="chart-title">Явка (%) / абсолютное число голосов</p><canvas ref="absoluteCanvas" width="640" height="640" @mousemove="absoluteMove" @mouseleave="clearAbsoluteHover" /></div><aside class="chart-legend"><span class="legend-title">Показывать</span><button v-for="entity in entities" :key="entity.id" type="button" :class="{ active: active.includes(entity.id) }" @click="toggle(entity.id)"><i :style="{ background: entity.color }" /><span>{{ entity.name }}</span></button></aside></div></section></template>
