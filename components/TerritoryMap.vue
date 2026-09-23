<script setup lang="ts">
import type { CatalogUnit } from '~/types/election'

type Position = { id: string, x: number, y: number }
type Geometry = { type: 'Polygon' | 'MultiPolygon', coordinates: number[][][] | number[][][][] }
type Feature = { properties: { name: string }, geometry: Geometry }
type FeatureCollection = { features: Feature[] }
type DistrictCatalog = { districts: Array<{ region: string, number: number, name: string }> }

const props = defineProps<{ units: CatalogUnit[], selectedRegion?: CatalogUnit }>()
const emit = defineEmits<{ select: [unit: CatalogUnit] }>()
const { data } = await useAsyncData('territory-map', () => $fetch<FeatureCollection>(`${useRuntimeConfig().app.baseURL.replace(/\/$/, '')}/data/maps/russia-regions.geojson`))
const { data: districtCatalog } = await useAsyncData('district-map-numbers', () => $fetch<DistrictCatalog>(`${useRuntimeConfig().app.baseURL.replace(/\/$/, '')}/data/maps/districts-2026.json`))
const normalize = (value: string) => value.toLocaleLowerCase('ru').replaceAll('ё', 'е').replace(/\s*\([^)]*\)/g, '').replace(/\s+-\s+кузбасс$/, '').replace(/^(город федерального значения|город|республика)\s+/, '').replace(/\s+(область|край|республика|автономная область|автономный округ)$/g, '').trim()
const unitByName = computed(() => new Map(props.units.map(unit => [normalize(unit.name), unit])))
const selectedFeature = computed(() => data.value?.features.find(feature => normalize(feature.properties.name) === normalize(props.selectedRegion?.name || '')))
const districtNumbers = computed(() => new Map((districtCatalog.value?.districts || []).map(item => [`${normalize(item.region)}|${normalize(item.name)}`, item.number])))
function districtNumber(unit: CatalogUnit, index: number): string | number {
  const shortName = unit.name.split(/\s+[–-]\s+/).at(-1) || unit.name
  return unit.number || districtNumbers.value.get(`${normalize(props.selectedRegion?.name || '')}|${normalize(shortName)}`) || index + 1
}

function rings(geometry: Geometry): number[][][] {
  return geometry.type === 'Polygon' ? geometry.coordinates as number[][][] : (geometry.coordinates as number[][][][]).flat()
}
function projectedPath(feature: Feature, regional = false): string {
  const all = rings(feature.geometry)
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
  const scale = Math.min(900 / width, 430 / height)
  const offsetX = (960 - width * scale) / 2; const offsetY = (480 - height * scale) / 2
  return projected.map(ring => ring.map((point, index) => `${index ? 'L' : 'M'}${(offsetX + (point[0] - minX) * scale).toFixed(1)},${(offsetY + (maxY - point[1]) * scale).toFixed(1)}`).join(' ') + 'Z').join(' ')
}
const regions = computed(() => (data.value?.features || []).map(feature => ({ feature, unit: unitByName.value.get(normalize(feature.properties.name)) })).filter(item => item.unit))
const positions = computed<Position[]>(() => props.units.map((unit, index) => {
  const columns = Math.ceil(Math.sqrt(props.units.length * 1.7))
  const rows = Math.ceil(props.units.length / columns)
  return { id: unit.id, x: 170 + (index % columns) * (620 / Math.max(1, columns - 1)), y: 120 + Math.floor(index / columns) * (260 / Math.max(1, rows - 1)) }
}))
</script>

<template>
  <section v-if="data" class="territory-map" :aria-label="selectedRegion ? 'Карта округов региона' : 'Карта регионов России'">
    <svg v-if="!selectedRegion" viewBox="0 0 960 480" role="img" aria-labelledby="russia-map-title">
      <title id="russia-map-title">Выберите регион России</title>
      <path v-for="item in regions" :key="item.unit!.id" :d="projectedPath(item.feature)" fill-rule="evenodd" tabindex="0" role="button" :aria-label="item.unit!.name" @click="emit('select', item.unit!)" @keydown.enter="emit('select', item.unit!)" @keydown.space.prevent="emit('select', item.unit!)"><title>{{ item.unit!.name }}</title></path>
    </svg>
    <div v-else class="regional-map">
      <svg viewBox="0 0 960 480" role="img" :aria-label="`Округа: ${selectedRegion.name}`">
        <path v-if="selectedFeature" class="region-outline" :d="projectedPath(selectedFeature, true)" fill-rule="evenodd" />
        <g v-for="(unit, index) in units" :key="unit.id" class="district-marker" tabindex="0" role="button" :aria-label="unit.name" @click="emit('select', unit)" @keydown.enter="emit('select', unit)" @keydown.space.prevent="emit('select', unit)">
          <circle :cx="positions[index]?.x" :cy="positions[index]?.y" r="25" />
          <text :x="positions[index]?.x" :y="positions[index]?.y + 5">{{ districtNumber(unit, index) }}</text>
          <title>{{ unit.name }}</title>
        </g>
      </svg>
      <p>Маркеры показывают доступные округа; контур — границу субъекта.</p>
    </div>
    <p class="map-attribution">Границы субъектов: OpenStreetMap contributors, GADM.</p>
  </section>
</template>
