<script setup lang="ts">
const route = useRoute()
const electionId = computed(() => String(route.params.election))
const unitId = computed(() => String(route.params.unit))
const { data: bundle, error } = await useAsyncData(
  () => `files-${electionId.value}-${unitId.value}`,
  () => resultBundleFor(electionId.value, unitId.value),
)
const files = computed(() => bundle.value?.files || [])
const official = computed(() => bundle.value?.official || null)
const picked = computed(() => files.value.filter(file => (
  file.unit.id === unitId.value
  || file.unit.administrative_path?.some(unit => unit.id === unitId.value)
)))
const total = computed(() => aggregate(official.value ? [official.value] : picked.value))
const unit = computed(() => (
  official.value?.unit || unitName(files.value, unitId.value)
))
const turnout = computed(() => (
  total.value.turnout.registered
    ? total.value.turnout.issued / total.value.turnout.registered * 100
    : 0
))
const isPrecinct = computed(() => unit.value?.kind === 'precinct')
const upperUnit = computed(() => {
  const path = unit.value?.administrative_path || []
  const target = unit.value?.kind === 'precinct'
    ? 'territorial_commission'
    : unit.value?.kind === 'territorial_commission'
      ? (path.some(item => item.kind === 'district') ? 'district' : 'region')
      : unit.value?.kind === 'district' || unit.value?.kind === 'region'
        ? 'national'
        : undefined
  return target ? [...path].reverse().find(item => item.kind === target) : undefined
})
const upperLabel = computed(() => unit.value?.kind === 'precinct' ? 'К результатам ТИК' : unit.value?.kind === 'territorial_commission' ? 'К результатам ОИК' : 'К результатам ЦИК')
const analysis = shallowRef()
const chartError = ref(false)
const chartRetry = ref(0)
const chartSlot = ref<HTMLElement>()
const chartVisible = ref(false)
const chartLoading = ref(false)
let chartObserver: IntersectionObserver | undefined
watch(chartSlot, element => {
  chartObserver?.disconnect()
  if (!element) return
  chartObserver = new IntersectionObserver(entries => {
    if (entries.some(entry => entry.isIntersecting)) {
      chartVisible.value = true
      chartObserver?.disconnect()
    }
  }, { rootMargin: '100px 0px' })
  chartObserver.observe(element)
}, { flush: 'post' })
onBeforeUnmount(() => chartObserver?.disconnect())
watch([unit, electionId, chartVisible, chartRetry], async ([selectedUnit, , visible], _, onCleanup) => {
  let cancelled = false
  onCleanup(() => { cancelled = true })
  analysis.value = undefined
  chartError.value = false
  chartLoading.value = false
  if (selectedUnit && selectedUnit.kind !== 'precinct' && visible) {
    chartLoading.value = true
    try {
      const result = await chartAnalysis(electionId.value, selectedUnit)
      if (!cancelled) analysis.value = result
    } catch {
      if (!cancelled) chartError.value = true
    } finally { if (!cancelled) chartLoading.value = false }
  }
}, { immediate: true })
const { data: electionDetail } = await useAsyncData(
  () => `election-${electionId.value}`,
  () => electionCatalog(electionId.value),
)
const { data: candidateData } = await useAsyncData(
  () => `candidates-${electionId.value}`,
  () => electionCandidates(electionId.value),
  { deep: false },
)
const election = computed(() => official.value?.election || files.value[0]?.election)
</script>
<template>
  <div v-if="error" class="empty">Результаты не найдены.</div>
  <template v-else-if="(files.length || official) && unit">
    <NuxtLink class="back" :to="{ path: '/', query: { election: electionId } }">← К территориям голосования</NuxtLink>
    <NuxtLink v-if="upperUnit" class="back upper-result" :to="`/result/${encodeURIComponent(electionId)}/${encodeURIComponent(upperUnit.id)}`">↑ {{ upperLabel }}</NuxtLink>
    <section class="result-title">
      <p class="eyebrow">
        {{ unit.kind === 'precinct' ? 'УЧАСТКОВАЯ КОМИССИЯ' : 'СВОДНЫЙ УРОВЕНЬ' }}
      </p>
      <h1>{{ unit.name }}</h1>
      <p>{{ election?.name }} · {{ official?.ballot.title || files[0]?.ballot.title }}</p>
      <a v-if="!isPrecinct" class="back" href="#analysis">К анализу УИК ↓</a>
    </section>
    <section class="stats">
      <div>
        <span>ЯВКА</span>
        <b>{{ turnout.toFixed(2) }}%</b>
        <small>
          {{ total.turnout.issued.toLocaleString('ru-RU') }} из
          {{ total.turnout.registered.toLocaleString('ru-RU') }}
        </small>
      </div>
      <div>
        <span>ДЕЙСТВИТЕЛЬНЫЕ</span>
        <b>{{ total.turnout.valid.toLocaleString('ru-RU') }}</b>
        <small>
          недействительных: {{ total.turnout.invalid.toLocaleString('ru-RU') }}
        </small>
      </div>
      <div>
        <span>ИСТОЧНИК ИТОГА</span>
        <b>{{ official ? 'ЦИК РФ' : isPrecinct ? 'ПРОТОКОЛ УИК' : 'РАСЧЁТ' }}</b>
        <small>
          {{
            official
              ? 'официальный сводный протокол'
              : isPrecinct ? 'исходный протокол участка' : 'сумма доступных протоколов УИК'
          }}
        </small>
      </div>
    </section>
    <p v-if="(official || files[0])?.source?.url" class="source-link"><a :href="(official || files[0])?.source?.url" target="_blank" rel="noopener noreferrer">Исходный протокол ↗</a> · Получен {{ (official || files[0])?.source?.retrieved_at?.slice(0, 10) }}</p>
    <div class="section-heading"><div><p class="eyebrow">ПРОТОКОЛ</p><h2>Результаты голосования</h2></div><span>{{ total.rows.length }} {{ total.rows.length === 1 ? 'позиция' : 'позиций' }}</span></div>
    <ResultTable :rows="total.rows" :valid="total.turnout.valid" :election-id="electionId" :unit-id="unitId" />
    <section v-if="!isPrecinct" id="analysis" ref="chartSlot" class="chart-lazy-shell">
      <div v-if="chartError" class="chart-loading" role="alert">Не удалось загрузить графики. <button @click="chartRetry++">Повторить</button></div>
      <div v-else-if="!analysis || chartLoading" class="chart-loading"><span class="loading-spinner" />Загрузка графиков…</div>
      <LazyShpilkinChart
        v-else-if="electionDetail"
        :analysis="analysis"
        :entities="electionDetail.entities"
        :candidates="candidateData || []"
        :unit-id="unitId"
      />
    </section>
  </template>
  <div v-else class="empty">Загрузка результатов…</div>
</template>
