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
const analysis = ref()
watch(unit, async (selectedUnit) => {
  if (selectedUnit && selectedUnit.kind !== 'precinct' && !analysis.value) {
    analysis.value = await chartAnalysis(electionId.value, selectedUnit)
  }
}, { immediate: true })
const { data: electionDetail } = await useAsyncData(
  () => `election-${electionId.value}`,
  () => electionCatalog(electionId.value),
)
const election = computed(() => official.value?.election || files.value[0]?.election)
</script>
<template>
  <div v-if="error" class="empty">Результаты не найдены.</div>
  <template v-else-if="(files.length || official) && unit">
    <NuxtLink class="back" to="/">← Все голосования</NuxtLink>
    <section class="result-title">
      <p class="eyebrow">
        {{ unit.kind === 'precinct' ? 'УЧАСТКОВАЯ КОМИССИЯ' : 'СВОДНЫЙ УРОВЕНЬ' }}
      </p>
      <h1>{{ unit.name }}</h1>
      <p>{{ election?.name }} · {{ official?.ballot.title || files[0]?.ballot.title }}</p>
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
        <b>{{ official ? 'ЦИК РФ' : 'РАСЧЁТ' }}</b>
        <small>
          {{
            official
              ? 'официальный сводный протокол'
              : `сумма ${picked.length} нижестоящих протоколов`
          }}
        </small>
      </div>
    </section>
    <ResultTable :rows="total.rows" :valid="total.turnout.valid" />
    <ShpilkinChart
      v-if="!isPrecinct && analysis && electionDetail"
      :analysis="analysis"
      :entities="electionDetail.entities"
      :unit-id="unitId"
    />
  </template>
  <div v-else class="empty">Загрузка результатов…</div>
</template>
