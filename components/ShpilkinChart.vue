<script setup lang="ts">
import type { AnalysisPoint, ElectionEntity, NationalChartAnalysis, RegionalChartAnalysis } from '~/types/election'

const props = defineProps<{ analysis: NationalChartAnalysis | RegionalChartAnalysis, entities: ElectionEntity[], unitId: string }>()
const palette = ['#356ae6', '#d6452e', '#1b9467', '#d78418', '#8b52c7', '#bf3f79', '#138a9b', '#766f2c']
const canvas = ref<HTMLCanvasElement>(); const shareOverlay = ref<HTMLCanvasElement>(); const absoluteCanvas = ref<HTMLCanvasElement>(); const absoluteOverlay = ref<HTMLCanvasElement>(); const tooltip = ref('')
const shareHover = ref<{ x: number, y: number } | null>(null); const absoluteHover = ref<{ x: number, y: number } | null>(null)
const active = ref<string[]>([])
const legendSearch = ref('')
const legendLimit = ref(60)
const { data: partyData } = await useAsyncData('parties', parties, { deep: false })
const entities = computed(() => props.entities.map((entity, index) => {
  const party = partyFor(partyData.value || [], entity.type === 'party' ? entity.id : entity.party_id, entity.type === 'party' ? entity.name : entity.party_name)
  return { ...entity, index, color: party?.color || palette[index % palette.length] }
}).filter(entity => availableEntities.value.has(entity.index)))
const legendEntities = computed(() => entities.value.filter(entity => entity.name.toLocaleLowerCase('ru').includes(legendSearch.value.toLocaleLowerCase('ru'))))
watch(legendSearch, () => { legendLimit.value = 60 })
const activeIndexes = computed(() => new Set(active.value.map(id => entities.value.find(entity => entity.id === id)?.index ?? -1).filter(index => index >= 0)))
const national = computed(() => 'entities' in props.analysis)

type Point = { turnout: number, share: number, count: number, entity: number }
const selectedPoints = computed<AnalysisPoint[]>(() => {
  const source = props.analysis.points || []
  if (national.value) return source
  const indexes = (props.analysis as RegionalChartAnalysis).units[props.unitId]
  return indexes ? indexes.map(index => source[index]) : source
})
const availableEntities = computed(() => {
  const present = new Set<number>()
  if (props.analysis.points) {
    for (const [, , results] of selectedPoints.value) for (let index = 0; index < results.length; index += 2) present.add(results[index])
  } else {
    props.analysis.clusters?.forEach((cluster, index) => { if (cluster.length) present.add(index) })
  }
  return present
})
watch(entities, list => { active.value = active.value.filter(id => list.some(entity => entity.id === id)); if (!active.value.length && list[0]) active.value = [list[0].id] }, { immediate: true })
const points = computed<Point[]>(() => {
  const output: Point[] = []
  if (!props.analysis.points) {
    for (const entity of activeIndexes.value) {
      for (const [turnout, share, count] of props.analysis.clusters?.[entity] || []) {
        output.push({ turnout: turnout / 100, share: share / 100, count, entity })
      }
    }
    return output
  }
  for (const [turnout, valid, results] of selectedPoints.value) {
    for (let index = 0; index < results.length; index += 2) {
      const entity = results[index]
      if (activeIndexes.value.has(entity)) output.push({ turnout: turnout / 100, share: valid ? results[index + 1] / valid * 100 : 0, count: 1, entity })
    }
  }
  return output
})
const pointRadius = computed(() => Math.max(1, Math.min(4.5, 18 / Math.sqrt(Math.max(1, points.value.length)))))
type AbsoluteMode = 'raw' | 'tenth' | 'one'
type AbsoluteTuple = [number, number, number]
const absoluteMode = ref<AbsoluteMode>('tenth')
const absoluteSeries = computed(() => {
  const buckets = new Map<number, Map<number, AbsoluteTuple>>()
  const raw = new Map<number, AbsoluteTuple[]>()
  for (const entity of activeIndexes.value) { buckets.set(entity, new Map()); raw.set(entity, []) }
  if (props.analysis.points) {
    const step = absoluteMode.value === 'one' ? 100 : 10
    for (const [turnout, , results] of selectedPoints.value) {
      for (let index = 0; index < results.length; index += 2) {
        const entity = results[index]
        if (!activeIndexes.value.has(entity)) continue
        if (absoluteMode.value === 'raw') { raw.get(entity)!.push([turnout, results[index + 1], 1]); continue }
        const bin = Math.round(turnout / step) * step
        const bucket = buckets.get(entity)!
        const point = bucket.get(bin) || [bin, 0, 0]
        point[1] += results[index + 1]
        point[2] += 1
        bucket.set(bin, point)
      }
    }
  }
  return [...activeIndexes.value].map(entity => {
    const legacy = props.analysis as NationalChartAnalysis
    const tuples = !props.analysis.points
      ? (absoluteMode.value === 'raw' ? legacy.absoluteRaw : absoluteMode.value === 'one' ? legacy.absolute1 : legacy.absolute)?.[entity] || []
      : absoluteMode.value === 'raw' ? raw.get(entity)! : [...buckets.get(entity)!.values()]
    return { entity, points: tuples.map(([turnout, votes, count]) => ({ turnout: turnout / 100, votes, count })).sort((a, b) => a.turnout - b.turnout) }
  })
})
const maxVotes = computed(() => {
  let maximum = 1
  for (const series of absoluteSeries.value) for (const point of series.points) maximum = Math.max(maximum, point.votes)
  return maximum
})
// Hit testing visits only neighboring screen cells, even for national datasets.
const hitGrid = computed(() => {
  const grid = new Map<string, Point[]>()
  for (const point of points.value) {
    const key = Math.floor((48 + point.turnout / 100 * 576) / 30) + ':' + Math.floor((606 - point.share / 100 * 592) / 30)
    const cell = grid.get(key) || []
    cell.push(point)
    grid.set(key, cell)
  }
  return grid
})
function colorFor(index: number): string { return entities.value.find(entity => entity.index === index)?.color || palette[index % palette.length] || palette[0] }
function draw(): void {
  const element = canvas.value; const context = element?.getContext('2d'); if (!element || !context) return
  const { width, height } = element; const left = 48; const right = 16; const top = 14; const bottom = 34; const maxShare = 100
  context.clearRect(0, 0, width, height); context.font = '11px Arial, sans-serif'; context.strokeStyle = '#eef2f7'; context.fillStyle = '#697586'
  for (let step = 0; step <= 4; step += 1) { const y = top + (height - top - bottom) * step / 4; context.beginPath(); context.moveTo(left, y); context.lineTo(width - right, y); context.stroke(); context.fillText(`${(maxShare * (4 - step) / 4).toFixed(0)}%`, 0, y + 4) }
  for (let step = 0; step <= 5; step += 1) context.fillText(`${step * 20}%`, left + (width - left - right) * step / 5 - 10, height - 12)
  for (const point of points.value) { const x = left + Math.min(100, Math.max(0, point.turnout)) / 100 * (width - left - right); const y = height - bottom - point.share / maxShare * (height - top - bottom); context.fillStyle = colorFor(point.entity); context.globalAlpha = Math.max(.45, 1 - Math.pow(1 - .2, point.count)); context.beginPath(); context.arc(x, y, pointRadius.value + Math.min(2, Math.log2(point.count) * .35), 0, Math.PI * 2); context.fill() }
  context.globalAlpha = 1
}
function nearest(event: MouseEvent): void {
  const element = canvas.value; if (!element) return
  const box = element.getBoundingClientRect(); const x = (event.clientX - box.left) / box.width * element.width; const y = (event.clientY - box.top) / box.height * element.height; const left = 48; const right = 16; const top = 14; const bottom = 34
  let hit: Point | undefined; let distance = Infinity; let hitX = x; let hitY = y
  const nearby: Point[] = []
  for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) {
    const cell = hitGrid.value.get((Math.floor(x / 30) + dx) + ':' + (Math.floor(y / 30) + dy))
    if (cell) for (const point of cell) nearby.push(point)
  }
  for (const point of nearby) { const px = left + point.turnout / 100 * (element.width - left - right); const py = element.height - bottom - point.share / 100 * (element.height - top - bottom); const next = (px - x) ** 2 + (py - y) ** 2; if (next < distance) { hit = point; distance = next; hitX = px; hitY = py } }
  shareHover.value = distance < 900 ? { x: hitX, y: hitY } : { x, y }
  tooltip.value = hit && distance < 900 ? `${props.entities[hit.entity]?.name} · явка ${hit.turnout.toFixed(2)}% · доля ${hit.share.toFixed(2)}%${hit.count > 1 ? ` · ${hit.count} УИК` : ''}` : ''
  drawCrosshair(shareOverlay.value, shareHover.value, 100, value => `${value.toFixed(2)}%`)
}
function drawAbsolute(): void {
  const element = absoluteCanvas.value; const context = element?.getContext('2d'); if (!element || !context) return
  const { width, height } = element; const left = 48; const right = 16; const top = 14; const bottom = 34; const maxVotesValue = maxVotes.value
  context.clearRect(0, 0, width, height); context.font = '11px Arial, sans-serif'; context.strokeStyle = '#eef2f7'; context.fillStyle = '#697586'
  for (let step = 0; step <= 4; step += 1) { const y = top + (height - top - bottom) * step / 4; context.beginPath(); context.moveTo(left, y); context.lineTo(width - right, y); context.stroke(); context.fillText(Math.round(maxVotesValue * (4 - step) / 4).toLocaleString('ru-RU'), 0, y + 4) }
  for (let step = 0; step <= 5; step += 1) context.fillText(`${step * 20}%`, left + (width - left - right) * step / 5 - 10, height - 12)
  for (const series of absoluteSeries.value) { context.strokeStyle = colorFor(series.entity); context.lineWidth = 1.5; context.globalAlpha = .9; context.beginPath(); series.points.forEach((point, index) => { const x = left + point.turnout / 100 * (width - left - right); const y = height - bottom - point.votes / maxVotesValue * (height - top - bottom); if (index === 0) context.moveTo(x, y); else context.lineTo(x, y) }); context.stroke() }
  context.globalAlpha = 1
}
function drawCrosshair(element: HTMLCanvasElement | undefined, hover: { x: number, y: number } | null, maxY: number, yFormatter: (value: number) => string): void {
  const overlay = element; const context = overlay?.getContext('2d'); if (!overlay || !context) return
  const { width, height } = overlay; const left = 48; const right = 16; const top = 14; const bottom = 34; context.clearRect(0, 0, width, height); if (!hover) return
  const plotWidth = width - left - right; const plotHeight = height - top - bottom; const xValue = (hover.x - left) / plotWidth * 100; const yValue = (height - bottom - hover.y) / plotHeight * maxY
  context.save(); context.strokeStyle = '#94a3b8'; context.lineWidth = 1; context.setLineDash([3, 3]); context.beginPath(); context.moveTo(hover.x, top); context.lineTo(hover.x, height - bottom); context.moveTo(left, hover.y); context.lineTo(width - right, hover.y); context.stroke(); context.setLineDash([]); context.fillStyle = '#334155'; context.font = '11px Arial, sans-serif'; context.fillText(`${xValue.toFixed(2)}%`, Math.min(width - 42, Math.max(left, hover.x - 16)), height - 12); context.fillText(yFormatter(yValue), 0, Math.max(top + 11, hover.y - 5)); context.restore()
}
function absoluteMove(event: MouseEvent): void {
  const element = absoluteCanvas.value; if (!element) return
  const box = element.getBoundingClientRect(); const x = (event.clientX - box.left) / box.width * element.width; const y = (event.clientY - box.top) / box.height * element.height; const left = 48; const right = 16; const top = 14; const bottom = 34
  let snapX = x; let snapY = y; let distance = Infinity
  for (const series of absoluteSeries.value) for (const point of series.points) { const px = left + point.turnout / 100 * (element.width - left - right); const py = element.height - bottom - point.votes / maxVotes.value * (element.height - top - bottom); const next = (px - x) ** 2 + (py - y) ** 2; if (next < distance) { distance = next; snapX = px; snapY = py } }
  absoluteHover.value = distance < 900 ? { x: snapX, y: snapY } : { x, y }; drawCrosshair(absoluteOverlay.value, absoluteHover.value, maxVotes.value, value => Math.round(value).toLocaleString('ru-RU'))
}
function clearShareHover(): void { shareHover.value = null; tooltip.value = ''; drawCrosshair(shareOverlay.value, null, 100, value => `${value.toFixed(2)}%`) }
function clearAbsoluteHover(): void { absoluteHover.value = null; drawCrosshair(absoluteOverlay.value, null, 1, value => Math.round(value).toLocaleString('ru-RU')) }
function toggle(id: string): void { active.value = active.value.includes(id) ? active.value.filter(value => value !== id) : [...active.value, id] }
function showAll(): void { active.value = entities.value.map(entity => entity.id) }
function hideAll(): void { active.value = [] }
function setAbsoluteMode(mode: string): void { if (mode === 'raw' || mode === 'tenth' || mode === 'one') absoluteMode.value = mode }
watch([points, absoluteSeries], () => nextTick(() => { draw(); drawAbsolute() }), { flush: 'post' }); onMounted(() => { draw(); drawAbsolute() })
</script>
<template><section class="shpilkin-chart"><div class="chart-head"><div><span class="eyebrow">АНАЛИЗ УИК</span><h3>Метод Шпилькина</h3></div><div class="chart-actions"><button class="chart-reset" type="button" @click="showAll">Показать всех</button><button class="chart-reset" type="button" @click="hideAll">Убрать всех</button></div></div><div class="chart-layout"><div class="chart-main"><p class="chart-title">Явка (%) / доля голосов (%) — облако УИК</p><div class="chart-canvas"><canvas ref="canvas" width="640" height="640" /><canvas ref="shareOverlay" class="chart-overlay" width="640" height="640" @mousemove="nearest" @mouseleave="clearShareHover" /></div><p class="chart-note">{{ tooltip || 'Точки совпадающих протоколов становятся плотнее.' }}</p><div class="absolute-title"><p class="chart-title">Явка (%) / абсолютное число голосов</p><div class="absolute-switch" role="group" aria-label="Агрегация абсолютного графика"><button v-for="mode in [{ id: 'raw', label: 'Без агрегации' }, { id: 'tenth', label: 'Шаг 0,1%' }, { id: 'one', label: 'Шаг 1%' }]" :key="mode.id" type="button" :class="{ active: absoluteMode === mode.id }" @click="setAbsoluteMode(mode.id)">{{ mode.label }}</button></div></div><div class="chart-canvas"><canvas ref="absoluteCanvas" width="640" height="640" /><canvas ref="absoluteOverlay" class="chart-overlay" width="640" height="640" @mousemove="absoluteMove" @mouseleave="clearAbsoluteHover" /></div></div><aside class="chart-legend"><span class="legend-title">Показывать</span><input v-if="entities.length > 12" v-model="legendSearch" type="search" aria-label="Найти партию или кандидата" placeholder="Найти кандидата"><button v-for="entity in legendEntities.slice(0, legendLimit)" :key="entity.id" type="button" :class="{ active: active.includes(entity.id) }" @click="toggle(entity.id)"><i :style="{ background: entity.color }" /><span>{{ entity.name }}</span></button><button v-if="legendEntities.length > legendLimit" @click="legendLimit += 60">Показать ещё</button></aside></div></section></template>
