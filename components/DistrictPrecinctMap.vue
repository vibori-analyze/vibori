<script setup lang="ts">
import type { CatalogPrecinct, CatalogUnit, ElectionEntity, PartyRecord } from '~/types/election'

type PrecinctMetric = { precinct: CatalogPrecinct, votes: number, winner: ElectionEntity | null, party: PartyRecord | null }
const props = defineProps<{ electionId: string, district: CatalogUnit }>()
const router = useRouter()
const metrics = shallowRef<PrecinctMetric[]>([])
const loading = ref(true)
const failed = ref(false)
const { data: partyData } = await useAsyncData('parties', parties, { deep: false })
const { data: candidates } = await useAsyncData(() => `district-map-candidates-${props.electionId}`, () => electionCandidates(props.electionId), { deep: false })

async function inBatches<T, R>(items: T[], size: number, task: (item: T) => Promise<R>): Promise<R[]> {
  const output: R[] = []
  for (let offset = 0; offset < items.length; offset += size) {
    const batch = await Promise.all(items.slice(offset, offset + size).map(task))
    output.push(...batch)
  }
  return output
}
watch([() => props.electionId, () => props.district.id, partyData, candidates], async (_, __, onCleanup) => {
  let cancelled = false
  onCleanup(() => { cancelled = true })
  metrics.value = []; loading.value = true; failed.value = false
  try {
    const commissions = await treeBranch(props.electionId, props.district.id)
    const precinctGroups = await inBatches(commissions.filter(unit => unit.kind === 'territorial_commission'), 8, async commission => {
      const pages = await inBatches(Array.from({ length: Math.ceil(commission.count / 500) }, (_, index) => index), 4, page => tikPrecinctPage(props.electionId, commission.id, page))
      return pages.flat()
    })
    const precincts = precinctGroups.flat()
    const next = await inBatches(precincts, 16, async precinct => {
      const bundle = await resultBundleFor(props.electionId, precinct.id)
      const file = bundle.official || bundle.files[0]
      if (!file) return { precinct, votes: 0, winner: null, party: null }
      const leading = [...file.results].sort((left, right) => right.votes - left.votes)[0]
      const winner = leading?.entity || null
      return { precinct, votes: file.turnout.valid, winner, party: winner ? partyForEntity(partyData.value || [], candidates.value || [], winner) || null : null }
    })
    if (!cancelled) metrics.value = next
  } catch { if (!cancelled) failed.value = true }
  finally { if (!cancelled) loading.value = false }
}, { immediate: true })
const maxVotes = computed(() => Math.max(1, ...metrics.value.map(item => item.votes)))
const circles = computed(() => metrics.value.map((item, index) => {
  const columns = Math.max(1, Math.ceil(Math.sqrt(metrics.value.length * 1.7)))
  const row = Math.floor(index / columns); const column = index % columns
  const x = 55 + (column + (row % 2) * .35) / Math.max(1, columns - .3) * 850
  const rows = Math.ceil(metrics.value.length / columns)
  const y = 55 + (row + ((column * 7) % 5) / 9) / Math.max(1, rows - .25) * 370
  return { ...item, x, y, radius: 2 + Math.sqrt(item.votes / maxVotes.value) * 10, color: item.party?.color || '#798398' }
}))
function open(precinct: CatalogPrecinct): void { void router.push(`/result/${encodeURIComponent(props.electionId)}/${encodeURIComponent(precinct.id)}`) }
</script>

<template>
  <section class="precinct-map" aria-label="Участки округа">
    <div class="map-toolbar"><div><p class="eyebrow">УЧАСТКИ ОКРУГА</p><h4>УИК: размер — число действительных голосов, цвет — победитель</h4><p>Нажмите на круг, чтобы открыть протокол УИК.</p></div></div>
    <p v-if="loading" class="map-loading" role="status">Загружаем протоколы УИК…</p>
    <p v-else-if="failed" class="map-loading" role="alert">Не удалось загрузить часть протоколов УИК.</p>
    <svg v-else viewBox="0 0 960 480" role="img" aria-label="Диаграмма участков округа">
      <rect x="20" y="20" width="920" height="440" rx="14" class="precinct-map-area" />
      <g v-for="item in circles" :key="item.precinct.id" class="precinct-marker" tabindex="0" role="button" :aria-label="`УИК №${item.precinct.number || item.precinct.name}: ${item.votes.toLocaleString('ru-RU')} действительных голосов, лидирует ${item.winner?.name || 'нет данных'}`" @click="open(item.precinct)" @keydown.enter="open(item.precinct)" @keydown.space.prevent="open(item.precinct)">
        <circle :cx="item.x" :cy="item.y" :r="item.radius" :fill="item.color"><title>УИК №{{ item.precinct.number || item.precinct.name }} · {{ item.votes.toLocaleString('ru-RU') }} голосов · {{ item.winner?.name || 'нет данных' }}</title></circle>
      </g>
    </svg>
    <p class="map-data-note">Положение кругов — схема: исходные протоколы не содержат координат УИК.</p>
  </section>
</template>
