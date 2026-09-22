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
const { data: catalogData } = await useAsyncData('catalog', catalog)
const rows = ref<EntityElectionResult[]>([])
const entity = ref<AggregatedRow>()

watchEffect(async () => {
  if (!catalogData.value) {
    return
  }

  const collected: EntityElectionResult[] = []
  for (const election of catalogData.value.elections) {
    const files = await topLevelResultsFor(await electionCatalog(election.id))
    const total = aggregate(files)
    const result = total.rows.find(row => row.id === id.value)
    if (result) {
      entity.value = result
      collected.push({
        election,
        votes: result.votes,
        percent: pct(result.votes, total.turnout.valid),
        units: election.precinct_count,
      })
    }
  }
  rows.value = collected.sort((left, right) => right.percent - left.percent)
})
</script>
<template>
  <NuxtLink class="back" to="/">← Все голосования</NuxtLink>
  <section class="result-title">
    <p class="eyebrow">
      {{ entity?.type === 'party' ? 'ПАРТИЯ / ИЗБИРАТЕЛЬНОЕ ОБЪЕДИНЕНИЕ' : 'КАНДИДАТ' }}
    </p>
    <h1>{{ entity?.name || 'Загрузка…' }}</h1>
    <p>Итоги на наиболее высоком доступном уровне каждого голосования.</p>
  </section>
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
