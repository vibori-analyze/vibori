<script setup lang="ts">
import type { ElectionEntity, NationalChartAnalysis, RegionalChartAnalysis } from '~/types/election'

const props = defineProps<{
  analysis: NationalChartAnalysis | RegionalChartAnalysis
  entities: ElectionEntity[]
  unitId: string
}>()

const palette = ['#d6452e', '#356ae6', '#1b9467', '#d78418', '#8b52c7', '#bf3f79', '#138a9b', '#766f2c']
const selected = ref('')
const canvas = ref<HTMLCanvasElement>()
const tooltip = ref('')

const chartEntities = computed(() => props.entities.map((entity, index) => ({
  ...entity,
  color: palette[index % palette.length],
})))
const entityIndex = computed(() => chartEntities.value.findIndex(entity => entity.id === selected.value))
const isNational = computed(() => 'entities' in props.analysis)

watchEffect(() => {
  if (!selected.value && chartEntities.value[0]) {
    selected.value = chartEntities.value[0].id
  }
})

type Point = { turnout: number, votes: number, count: number }

function cluster(points: Point[]): Point[] {
  if (points.length <= 5000) {
    return points
  }
  const maxVotes = Math.max(...points.map(point => point.votes), 1)
  const voteStep = Math.max(1, Math.ceil(maxVotes / 120))
  const clusters = new Map<string, Point>()
  for (const point of points) {
    const turnout = Math.round(point.turnout)
    const votes = Math.round(point.votes / voteStep) * voteStep
    const key = `${turnout}:${votes}`
    const current = clusters.get(key) || { turnout, votes, count: 0 }
    current.count += point.count
    clusters.set(key, current)
  }
  return [...clusters.values()]
}

const points = computed<Point[]>(() => {
  const index = entityIndex.value
  if (index < 0) {
    return []
  }
  if (isNational.value) {
    return props.analysis.clusters[index].map(([turnout, votes, count]) => ({
      turnout: turnout / 100,
      votes,
      count,
    }))
  }
  const analysis = props.analysis as RegionalChartAnalysis
  if (props.unitId === '') return []
  if (!analysis.units[props.unitId]) {
    return analysis.clusters[index].map(([turnout, votes, count]) => ({ turnout: turnout / 100, votes, count }))
  }
  const raw: Point[] = []
  for (const sourceIndex of analysis.units[props.unitId]) {
    const point = analysis.points[sourceIndex]
    for (let resultIndex = 0; resultIndex < point[1].length; resultIndex += 2) {
      if (point[1][resultIndex] === index) {
        raw.push({ turnout: point[0] / 100, votes: point[1][resultIndex + 1], count: 1 })
        break
      }
    }
  }
  return cluster(raw)
})

function draw(): void {
  const element = canvas.value
  if (!element) {
    return
  }
  const context = element.getContext('2d')
  if (!context) {
    return
  }
  const width = element.width
  const height = element.height
  const left = 48
  const right = 16
  const top = 14
  const bottom = 34
  const maxVotes = Math.max(...points.value.map(point => point.votes), 1)
  const color = chartEntities.value[entityIndex.value]?.color || palette[0]
  context.clearRect(0, 0, width, height)
  context.font = '11px Manrope, sans-serif'
  context.fillStyle = '#aaa69e'
  context.strokeStyle = '#51524c'
  context.lineWidth = 1
  for (let step = 0; step <= 4; step += 1) {
    const y = top + (height - top - bottom) * step / 4
    context.beginPath()
    context.moveTo(left, y)
    context.lineTo(width - right, y)
    context.stroke()
    context.fillText(Math.round(maxVotes * (4 - step) / 4).toLocaleString('ru-RU'), 0, y + 4)
  }
  for (let step = 0; step <= 5; step += 1) {
    const x = left + (width - left - right) * step / 5
    context.fillText(`${step * 20}%`, x - 10, height - 12)
  }
  context.fillStyle = color
  for (const point of points.value) {
    const x = left + Math.min(100, Math.max(0, point.turnout)) / 100 * (width - left - right)
    const y = height - bottom - point.votes / maxVotes * (height - top - bottom)
    context.globalAlpha = Math.min(0.85, 0.22 + Math.log2(point.count + 1) / 7)
    context.beginPath()
    context.arc(x, y, Math.min(7, 1.3 + Math.sqrt(point.count)), 0, Math.PI * 2)
    context.fill()
  }
  context.globalAlpha = 1
}

function showNearest(event: MouseEvent): void {
  const element = canvas.value
  if (!element || !points.value.length) {
    return
  }
  const bounds = element.getBoundingClientRect()
  const x = (event.clientX - bounds.left) / bounds.width * element.width
  const y = (event.clientY - bounds.top) / bounds.height * element.height
  const maxVotes = Math.max(...points.value.map(point => point.votes), 1)
  const left = 48
  const right = 16
  const top = 14
  const bottom = 34
  let nearest: Point | undefined
  let distance = Infinity
  for (const point of points.value) {
    const px = left + point.turnout / 100 * (element.width - left - right)
    const py = element.height - bottom - point.votes / maxVotes * (element.height - top - bottom)
    const next = (px - x) ** 2 + (py - y) ** 2
    if (next < distance) {
      nearest = point
      distance = next
    }
  }
  tooltip.value = nearest && distance < 900
    ? `Явка ${nearest.turnout.toFixed(1)}% · ${nearest.votes.toLocaleString('ru-RU')} голосов${nearest.count > 1 ? ` · ${nearest.count} УИК` : ''}`
    : ''
}

watch([points, selected], () => nextTick(draw), { flush: 'post' })
onMounted(draw)
</script>

<template>
  <section class="shpilkin-chart">
    <div class="chart-head">
      <div>
        <span class="eyebrow">АНАЛИЗ УИК</span>
        <h3>Метод Шпилькина</h3>
      </div>
      <select v-model="selected">
        <option v-for="entity in entities" :key="entity.id" :value="entity.id">
          {{ entity.name }}
        </option>
      </select>
    </div>
    <p class="chart-subtitle">X — явка, Y — число голосов. Каждая точка — УИК.</p>
    <canvas ref="canvas" width="960" height="420" @mousemove="showNearest" @mouseleave="tooltip = ''" />
    <p class="chart-note">
      {{ tooltip || (isNational ? 'На общероссийском уровне близкие УИК сгруппированы в кластеры.' : 'Крупные выборки автоматически сгруппированы для быстрой отрисовки.') }}
    </p>
    <div class="chart-legend">
      <button
        v-for="entity in chartEntities"
        :key="entity.id"
        type="button"
        :class="{ active: entity.id === selected }"
        @click="selected = entity.id"
      >
        <i :style="{ background: entity.color }" />{{ entity.name }}
      </button>
    </div>
  </section>
</template>
