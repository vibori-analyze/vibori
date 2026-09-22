<script setup lang="ts">
import type { AggregatedRow, CatalogElection } from '~/types/election'

interface EntityElectionResult {
  election: CatalogElection
  votes: number
  percent: number
  units: number
}

const route = useRoute()
const id = computed(() => String(route.params.id))
const { data: catalogData, error: catalogError } = await useAsyncData('catalog', catalog, { deep: false })
const rows = shallowRef<EntityElectionResult[]>([])
const entity = ref<AggregatedRow>()
const loading = ref(true)
const failed = ref(false)

watch([id, catalogData], async ([entityId, catalogValue], _, onCleanup) => {
  let cancelled = false
  onCleanup(() => { cancelled = true })
  rows.value = []
  entity.value = undefined
  failed.value = false
  if (!catalogValue) return
  loading.value = true
  const collected: EntityElectionResult[] = []
  for (let offset = 0; offset < catalogValue.elections.length; offset += 4) {
    const batch = await Promise.allSettled(catalogValue.elections.slice(offset, offset + 4).map(async election => {
      const { official, files } = await resultBundleFor(election.id, election.national_id)
      const total = aggregate(official ? [official] : files)
      const result = total.rows.find(row => row.id === entityId)
      return { election, total, result }
    }))
    if (cancelled) return
    for (const response of batch) {
      if (response.status === 'rejected') { failed.value = true; continue }
      const { election, total, result } = response.value
      if (!result) continue
      entity.value = result
      collected.push({ election, votes: result.votes, percent: pct(result.votes, total.turnout.valid), units: election.precinct_count })
    }
    rows.value = [...collected].sort((left, right) => right.percent - left.percent)
  }
  loading.value = false
}, { immediate: true })
</script>
<template>
  <NuxtLink class="back" to="/">← Все голосования</NuxtLink>
  <section class="result-title">
    <p class="eyebrow">
      {{ entity?.type === 'party' ? 'ПАРТИЯ / ИЗБИРАТЕЛЬНОЕ ОБЪЕДИНЕНИЕ' : 'КАНДИДАТ' }}
    </p>
    <h1>{{ entity?.name || (loading && !catalogError ? 'Загрузка…' : 'Данные не найдены') }}</h1>
    <p>Итоги на наиболее высоком доступном уровне каждого голосования.</p>
  </section>
  <p v-if="failed || catalogError" role="alert">Часть данных не удалось загрузить. Обновите страницу, чтобы повторить.</p>
  <div class="table-wrap">
    <table>
      <thead>
        <tr><th>Голосование</th><th>Голоса</th><th>Доля</th><th>УИК</th></tr>
      </thead>
      <tbody>
        <tr v-for="result in rows" :key="result.election.id">
          <td>
            <NuxtLink
              :to="`/result/${result.election.id}/${result.election.national_id}`"
              class="entity"
            >
              {{ result.election.name }}
            </NuxtLink>
          </td>
          <td>{{ result.votes.toLocaleString('ru-RU') }}</td>
          <td><b>{{ result.percent.toFixed(2) }}%</b></td>
          <td>{{ result.units }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
