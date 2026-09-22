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
</script>
<template>
  <div v-if="error" class="empty">Результаты не найдены.</div>
  <template v-else-if="files.length && unit">
    <NuxtLink class="back" to="/">← Все голосования</NuxtLink>
    <section class="result-title">
      <p class="eyebrow">
        {{ unit.kind === 'precinct' ? 'УЧАСТКОВАЯ КОМИССИЯ' : 'СВОДНЫЙ УРОВЕНЬ' }}
      </p>
      <h1>{{ unit.name }}</h1>
      <p>{{ files[0]?.election.name }} · {{ files[0]?.ballot.title }}</p>
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
    <ShareChart :files="picked" />
  </template>
  <div v-else class="empty">Загрузка результатов…</div>
</template>
