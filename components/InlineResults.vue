<script setup lang="ts">
import type { NationalChartAnalysis, RegionalChartAnalysis, ResultFile } from '~/types/election'

const props = defineProps<{ electionId: string, unitId: string }>()
const { data: bundle, error } = await useAsyncData(
  () => `inline-results-${props.electionId}-${props.unitId}`,
  () => resultBundleFor(props.electionId, props.unitId),
)
const file = computed<ResultFile | undefined>(() => bundle.value?.official || bundle.value?.files[0])
const total = computed(() => file.value ? aggregate([file.value]) : undefined)
const turnout = computed(() => total.value?.turnout.registered
  ? total.value.turnout.issued / total.value.turnout.registered * 100 : 0)
const analysis = shallowRef<NationalChartAnalysis | RegionalChartAnalysis>()
const analysisFailed = ref(false)
const analysisLoading = ref(false)
const { data: electionDetail } = await useAsyncData(
  () => `inline-election-${props.electionId}`,
  () => electionCatalog(props.electionId),
)
const { data: candidates } = await useAsyncData(
  () => `inline-candidates-${props.electionId}`,
  () => electionCandidates(props.electionId),
  { deep: false },
)
watch(file, async (selected, _, onCleanup) => {
  let cancelled = false
  onCleanup(() => { cancelled = true })
  analysis.value = undefined; analysisFailed.value = false; analysisLoading.value = false
  if (!selected || selected.unit.kind === 'precinct') return
  analysisLoading.value = true
  try {
    const result = await chartAnalysis(props.electionId, selected.unit)
    if (!cancelled) analysis.value = result
  } catch { if (!cancelled) analysisFailed.value = true }
  finally { if (!cancelled) analysisLoading.value = false }
}, { immediate: true })
</script>

<template>
  <section v-if="total && file" class="inline-results" aria-label="Результаты территории">
    <section class="stats">
      <div><span>ЯВКА</span><b>{{ turnout.toFixed(2) }}%</b><small>{{ total.turnout.issued.toLocaleString('ru-RU') }} из {{ total.turnout.registered.toLocaleString('ru-RU') }}</small></div>
      <div><span>ДЕЙСТВИТЕЛЬНЫЕ</span><b>{{ total.turnout.valid.toLocaleString('ru-RU') }}</b><small>недействительных: {{ total.turnout.invalid.toLocaleString('ru-RU') }}</small></div>
      <div><span>ИСТОЧНИК ИТОГА</span><b>{{ bundle?.official ? 'ЦИК РФ' : 'РАСЧЁТ' }}</b><small>{{ bundle?.official ? 'официальный сводный протокол' : 'сумма доступных протоколов' }}</small></div>
    </section>
    <p v-if="file.source?.url" class="source-link"><a :href="file.source.url" target="_blank" rel="noopener noreferrer">Исходный протокол ↗</a> · Получен {{ file.source.retrieved_at?.slice(0, 10) }}</p>
    <div class="section-heading"><div><p class="eyebrow">ПРОТОКОЛ</p><h2>Результаты голосования</h2></div><span>{{ total.rows.length }} позиций</span></div>
    <ResultTable :rows="total.rows" :valid="total.turnout.valid" :election-id="electionId" :unit-id="unitId" />
    <section v-if="file.unit.kind !== 'precinct'" class="inline-analysis">
      <p v-if="analysisLoading" class="chart-loading"><span class="loading-spinner" />Загрузка графиков…</p>
      <p v-else-if="analysisFailed" class="chart-loading">Не удалось загрузить графики.</p>
      <LazyShpilkinChart v-else-if="analysis && electionDetail" :analysis="analysis" :entities="electionDetail.entities" :candidates="candidates || []" :unit-id="unitId" />
    </section>
  </section>
  <p v-else-if="error" class="status">Итоги для этой территории пока не опубликованы.</p>
  <p v-else class="status">Загружаем результаты…</p>
</template>
