<script setup lang="ts">
import type { CatalogUnit, ElectionEntity, PartyRecord } from '~/types/election'

type Position = { id: string, x: number, y: number }
type Geometry = { type: 'Polygon' | 'MultiPolygon', coordinates: number[][][] | number[][][][] }
type Feature = { properties: { name: string }, geometry: Geometry }
type FeatureCollection = { features: Feature[] }

type MapMetric = { turnout: number | null, winner: ElectionEntity | null, party: PartyRecord | null, official: boolean }
type LegendItem = { name: string, color: string }
type Layer = {
  id: string
  label: string
  description: (regional: boolean) => string
  color: (metric?: MapMetric) => string
  value: (metric: MapMetric) => string
  legend: (metrics: Record<string, MapMetric>) => LegendItem[]
  note: (ballotKind: string) => string
}
const missingColor = '#dce2e7'
const turnoutStops = ['#eff4ea', '#d5e7d3', '#a6cfb7', '#65a99b', '#2a777b', '#174b63']
const turnoutColor = (value: number) => {
  return turnoutStops[Math.min(turnoutStops.length - 1, Math.floor(Math.max(0, Math.min(99.99, value)) / 20))]!
}
function winnerLegend(metrics: Record<string, MapMetric>): LegendItem[] {
  const values = new Map<string, LegendItem>()
  for (const metric of Object.values(metrics)) {
    if (!metric.winner) continue
    const name = metric.party?.name || (metric.winner.type === 'candidate' ? 'Самовыдвижение' : metric.winner.name)
    values.set(name, { name, color: metric.party?.color || '#798398' })
  }
  return [...values.values()].sort((a, b) => a.name.localeCompare(b.name, 'ru'))
}
const layers: Layer[] = [
  {
    id: 'winner', label: 'Победитель',
    description: regional => regional ? 'Цвет партии победителя' : 'Партия с наибольшим числом голосов в регионе',
    color: metric => metric?.winner ? metric.party?.color || '#798398' : missingColor,
    value: metric => `лидирует ${metric.winner?.name || 'нет данных'}`,
    legend: winnerLegend,
    note: kind => kind === 'single_member'
      ? 'В регионах голоса кандидатов одной партии суммируются. Для кандидата без определённой партии используется нейтральный цвет.'
      : 'Цвет соответствует партии, получившей больше всего голосов в территории.',
  },
  {
    id: 'turnout', label: 'Явка', description: () => 'Доля получивших бюллетени',
    color: metric => metric?.turnout == null ? missingColor : turnoutColor(metric.turnout),
    value: metric => `явка ${metric.turnout == null ? 'нет данных' : `${metric.turnout.toFixed(1)}%`}`,
    legend: () => turnoutStops.map((color, index) => ({ name: `${index * 20}${index === 5 ? '%+' : `–${(index + 1) * 20}%`}`, color })),
    note: () => 'Явка рассчитана как отношение выданных бюллетеней к числу зарегистрированных избирателей.',
  },
]
const props = defineProps<{ units: CatalogUnit[], selectedRegion?: CatalogUnit, electionId: string }>()
const emit = defineEmits<{ select: [unit: CatalogUnit] }>()
const mapSection = ref<HTMLElement>()
const hoveredRegionId = ref<string | null>(null)
const layerId = ref('winner')
const layer = computed(() => layers.find(item => item.id === layerId.value) || layers[0]!)
const ballotKind = ref('')
const metrics = shallowRef<Record<string, MapMetric>>({})
const metricsLoading = ref(false)
const legend = computed(() => layer.value.legend(metrics.value))
const { data: partyData } = await useAsyncData('parties', parties, { deep: false })
const { data: candidates } = await useAsyncData(() => `map-candidates-${props.electionId}`, () => electionCandidates(props.electionId), { deep: false })
const unitIds = computed(() => props.units.map(unit => unit.id).join(','))
watch([() => props.electionId, unitIds, partyData, candidates], async (_, __, onCleanup) => {
  let cancelled = false
  onCleanup(() => { cancelled = true })
  metrics.value = {}
  ballotKind.value = ''
  if (!props.units.length) return
  metricsLoading.value = true
  try {
    const detail = await electionCatalog(props.electionId)
    if (cancelled) return
    ballotKind.value = detail.ballot_kind || ''
    const next: Record<string, MapMetric> = {}
    for (let offset = 0; offset < props.units.length; offset += 12) {
      const batch = await Promise.allSettled(props.units.slice(offset, offset + 12).map(async unit => {
        const bundle = await resultBundleFor(props.electionId, unit.id, detail)
        const file = bundle.official || bundle.files[0]
        if (!file) return null
        const rows = file.ballot.kind === 'single_member' && unit.kind === 'region'
          ? partyRows(aggregate([file]), candidates.value || [], partyData.value || [])
          : file.results.map(row => ({ ...row.entity, votes: row.votes }))
        const leading = [...rows].sort((a, b) => b.votes - a.votes)[0]
        return { id: unit.id, metric: {
          turnout: file.turnout.registered ? file.turnout.issued / file.turnout.registered * 100 : null,
          winner: leading || null,
          party: leading ? partyForEntity(partyData.value || [], candidates.value || [], leading) || null : null,
          official: Boolean(bundle.official),
        } }
      }))
      if (cancelled) return
      for (const item of batch) if (item.status === 'fulfilled' && item.value) next[item.value.id] = item.value.metric
      metrics.value = { ...next }
    }
  } catch { /* The map keeps neutral colors when summary data is unavailable. */ }
  finally { if (!cancelled) metricsLoading.value = false }
}, { immediate: true })
const mapColor = (unit: CatalogUnit) => layer.value.color(metrics.value[unit.id])
function mapDescription(unit: CatalogUnit): string {
  const metric = metrics.value[unit.id]
  const count = props.selectedRegion && unit.kind === 'district' ? ` · ${unit.count.toLocaleString('ru-RU')} УИК` : ''
  if (!metric) return `${unit.name}${count} · нет данных`
  return `${unit.name}${count} · ${layer.value.value(metric)}`
}
const { data } = await useAsyncData('territory-map', () => $fetch<FeatureCollection>(`${useRuntimeConfig().app.baseURL.replace(/\/$/, '')}/data/maps/russia-regions.geojson`))
watch([() => props.selectedRegion?.id, data], async ([id, features]) => {
  if (!id || !features || !import.meta.client) return
  await nextTick()
  mapSection.value?.scrollIntoView({ block: 'center', behavior: 'smooth' })
}, { immediate: true })
const normalize = (value: string) => value.toLocaleLowerCase('ru').replaceAll('ё', 'е').replace(/\s*\([^)]*\)/g, '').replace(/\s+-\s+кузбасс$/, '').replace(/^(город федерального значения|город|республика)\s+/, '').replace(/\s+(область|край|республика|автономная область|автономный округ)$/g, '').trim()
const unitByName = computed(() => new Map(props.units.map(unit => [normalize(unit.name), unit])))
const selectedFeature = computed(() => data.value?.features.find(feature => normalize(feature.properties.name) === normalize(props.selectedRegion?.name || '')))
function rings(geometry: Geometry): number[][][] {
  return geometry.type === 'Polygon' ? geometry.coordinates as number[][][] : (geometry.coordinates as number[][][][]).flat()
}
function projectedPath(feature: Feature, regional = false): string {
  // Preserve Polygon boundaries. Flattening MultiPolygon rings into one path is
  // valid only when every ring is an independent subpath; explicitly closing
  // each ring also avoids accidental joins across the Chukotka dateline.
  const all = rings(feature.geometry).filter(ring => ring.length >= 4)
  const project = (point: number[]) => {
    const longitude = (point[0] < 0 ? point[0] + 360 : point[0]) * Math.PI / 180
    const latitude = Math.max(-85, Math.min(85, point[1])) * Math.PI / 180
    return [longitude, Math.log(Math.tan(Math.PI / 4 + latitude / 2))]
  }
  const projected = all.map(ring => ring.map(project))
  const points = projected.flat()
  if (!points.length) return ''
  const globalWest = project([18, 40])[0]
  const globalEast = project([190, 40])[0]
  const minX = regional ? Math.min(...points.map(point => point[0])) : globalWest
  const maxX = regional ? Math.max(...points.map(point => point[0])) : globalEast
  const globalSouth = project([18, 40])[1]
  const globalNorth = project([18, 82])[1]
  const minY = regional ? Math.min(...points.map(point => point[1])) : globalSouth
  const maxY = regional ? Math.max(...points.map(point => point[1])) : globalNorth
  const width = Math.max(1, maxX - minX); const height = Math.max(1, maxY - minY)
  const padding = regional ? 18 : 30
  const scale = Math.min((960 - padding * 2) / width, (480 - padding * 2) / height)
  const offsetX = (960 - width * scale) / 2; const offsetY = (480 - height * scale) / 2
  return projected.map(ring => ring.map((point, index) => `${index ? 'L' : 'M'}${(offsetX + (point[0] - minX) * scale).toFixed(1)},${(offsetY + (maxY - point[1]) * scale).toFixed(1)}`).join(' ') + 'Z').join(' ')
}
const isDatelineRegion = (feature: Feature) => normalize(feature.properties.name) === 'чукотский'
const regions = computed(() => (data.value?.features || []).map(feature => ({ feature, unit: unitByName.value.get(normalize(feature.properties.name)) })).filter(item => item.unit))
const hoveredRegion = computed(() => regions.value.find(item => item.unit?.id === hoveredRegionId.value))
const positions = computed<Position[]>(() => props.units.map((unit, index) => {
  const columns = Math.ceil(Math.sqrt(props.units.length * 1.7))
  const rows = Math.ceil(props.units.length / columns)
  return { id: unit.id, x: 170 + (index % columns) * (620 / Math.max(1, columns - 1)), y: 120 + Math.floor(index / columns) * (260 / Math.max(1, rows - 1)) }
}))
</script>

<template>
  <section v-if="data" ref="mapSection" class="territory-map" :aria-label="selectedRegion ? 'Карта округов региона' : 'Карта регионов России'">
    <div class="map-toolbar">
      <div><p class="eyebrow">ИНТЕРАКТИВНАЯ КАРТА</p><h4>{{ selectedRegion ? 'Округа региона' : 'Регионы России' }}</h4><p>Выберите территорию на карте, чтобы перейти к комиссиям.</p></div>
      <label class="map-layer-control" for="map-layer">Окраска карты<select id="map-layer" v-model="layerId"><option v-for="item in layers" :key="item.id" :value="item.id">{{ item.label }}</option></select></label>
    </div>
    <p v-if="metricsLoading" class="map-loading" role="status">Загружаем показатели карты…</p>
    <svg v-if="!selectedRegion" viewBox="0 0 960 480" role="img" aria-labelledby="russia-map-title">
      <title id="russia-map-title">Выберите регион России</title>
      <path v-for="item in regions" :key="item.unit!.id" :d="projectedPath(item.feature)" :style="{ fill: mapColor(item.unit!) }" :class="{ 'dateline-region': isDatelineRegion(item.feature) }" fill-rule="evenodd" tabindex="0" role="button" :aria-label="mapDescription(item.unit!)" @mouseenter="hoveredRegionId = item.unit!.id" @mouseleave="hoveredRegionId = null" @focus="hoveredRegionId = item.unit!.id" @blur="hoveredRegionId = null" @click="emit('select', item.unit!)" @keydown.enter="emit('select', item.unit!)" @keydown.space.prevent="emit('select', item.unit!)"><title>{{ mapDescription(item.unit!) }}</title></path>
      <path v-if="hoveredRegion?.unit" class="region-hover-overlay" :class="{ 'dateline-region': isDatelineRegion(hoveredRegion.feature) }" :d="projectedPath(hoveredRegion.feature)" fill-rule="evenodd" pointer-events="none" />
    </svg>
    <div v-else class="regional-map">
      <svg viewBox="0 0 960 480" role="img" :aria-label="`Округа: ${selectedRegion.name}`">
        <path v-if="selectedFeature" class="region-outline" :class="{ 'dateline-region': isDatelineRegion(selectedFeature) }" :d="projectedPath(selectedFeature, true)" :style="{ fill: mapColor(selectedRegion) }" fill-rule="evenodd" pointer-events="none" />
        <g v-for="(unit, index) in units" :key="unit.id" class="district-marker" tabindex="0" role="button" :aria-label="mapDescription(unit)" @click="emit('select', unit)" @keydown.enter="emit('select', unit)" @keydown.space.prevent="emit('select', unit)">
          <circle :cx="positions[index]?.x" :cy="positions[index]?.y" r="34" :style="{ fill: mapColor(unit) }" />
          <text :x="positions[index]?.x" :y="positions[index]?.y + 5">{{ unit.kind === 'district' ? unit.count.toLocaleString('ru-RU') : index + 1 }}</text>
          <title>{{ mapDescription(unit) }}</title>
        </g>
      </svg>
      <p>Округа показаны схематично: положение маркеров не соответствует их географическим границам. Контур — граница субъекта.</p>
    </div>
    <div class="map-legend" aria-label="Легенда карты">
      <span class="map-legend-label">{{ layer.description(Boolean(selectedRegion)) }}</span>
      <span v-for="item in legend" :key="item.name" class="legend-item"><i :style="{ background: item.color }" />{{ item.name }}</span>
      <span class="legend-item"><i :style="{ background: missingColor }" />Нет данных</span>
    </div>
    <p class="map-data-note">{{ layer.note(ballotKind) }} Официальные сводки имеют приоритет.</p>
    <p class="map-attribution">Границы субъектов: OpenStreetMap contributors, GADM.</p>
  </section>
</template>
