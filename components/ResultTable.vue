<script setup lang="ts">
import type { AggregatedRow } from '~/types/election'

const props = defineProps<{ rows: AggregatedRow[], valid: number, electionId: string, unitId: string, partyOnly?: boolean }>()
const { data: partyData } = await useAsyncData('parties', parties, { deep: false })
const { data: candidateData } = await useAsyncData(
  () => `candidates-${props.electionId}`,
  () => electionCandidates(props.electionId),
  { deep: false },
)
const logoFor = (result: AggregatedRow) => partyForEntity(
  partyData.value || [],
  candidateData.value || [],
  result,
)
const colorFor = (result: AggregatedRow) => logoFor(result)?.color
const partyNameFor = (result: AggregatedRow) => partyNameForEntity(candidateData.value || [], result) || logoFor(result)?.name
const partyForResult = (result: AggregatedRow) => logoFor(result)
const partyIdFor = (result: AggregatedRow) => partyForResult(result)?.id
const partyLinkFor = (result: AggregatedRow) => '/entity/' + encodeURIComponent(partyIdFor(result) || '')
const search = ref('')
const page = ref(1)
const pageSize = 25
const normalize = (value: string) => value.toLocaleLowerCase('ru').replaceAll('ё', 'е')
const ordered = computed(() => [...props.rows].sort((left, right) => right.votes - left.votes))
const filtered = computed(() => {
  const query = normalize(search.value.trim())
  return query ? ordered.value.filter(row => normalize(row.name).includes(query)) : ordered.value
})
const pages = computed(() => Math.ceil(filtered.value.length / pageSize))
const visible = computed(() => filtered.value.slice((page.value - 1) * pageSize, page.value * pageSize))
watch([search, () => props.rows], () => { page.value = 1 })
</script>

<template>
  <section aria-label="Результаты голосования">
    <label v-if="rows.length > pageSize" class="search-field" for="result-search">
      <span aria-hidden="true">⌕</span>
      <input id="result-search" v-model="search" type="search" :placeholder="partyOnly ? 'Найти партию' : 'Найти кандидата или партию'">
      <span class="sr-only">Поиск по результатам</span>
      <kbd>{{ filtered.length }}</kbd>
    </label>
    <div class="table-wrap">
      <table>
        <thead><tr><th>{{ partyOnly ? 'Партия' : 'Кандидат / список' }}</th><th aria-sort="descending">Голоса ↓</th><th>Доля</th></tr></thead>
        <tbody>
          <tr v-for="result in visible" :key="result.id">
            <td>
              <span class="result-entity">
                <PartyLogo :party="logoFor(result)" />
                <NuxtLink v-if="result.type !== 'other'" :to="{ path: '/entity/' + encodeURIComponent(result.id), query: { election: electionId, unit: unitId } }" class="entity">{{ result.name }}</NuxtLink><span v-else>{{ result.name }}</span>
              </span>
              <small v-if="result.type === 'candidate' && partyNameFor(result)">
                <NuxtLink
                  v-if="partyIdFor(result)"
                  :to="{ path: partyLinkFor(result), query: { election: electionId, unit: unitId } }"
                >{{ partyNameFor(result) }}</NuxtLink>
                <template v-else>{{ partyNameFor(result) }}</template>
              </small>
            </td>
            <td>{{ result.votes.toLocaleString('ru-RU') }}</td>
            <td><b>{{ pct(result.votes, valid).toFixed(2) }}%</b><i :style="{ width: pct(result.votes, valid) + '%', background: colorFor(result) }" /></td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-if="!filtered.length" class="status">Ничего не найдено.</p>
    <nav v-if="pages > 1" class="pagination" aria-label="Страницы результатов">
      <button :disabled="page === 1" @click="page--">← Назад</button>
      <span aria-live="polite">{{ page }} / {{ pages }}</span>
      <button :disabled="page === pages" @click="page++">Далее →</button>
    </nav>
  </section>
</template>
