<script setup lang="ts">
import type { AggregatedRow, CandidateRecord, CandidateSummary, CatalogElection } from '~/types/election'

interface EntityElectionResult { election: CatalogElection, votes: number, percent: number, units: number }

const route = useRoute()
const id = computed(() => String(route.params.id))
const requestedElection = computed(() => String(route.query.election || ''))
const requestedUnit = computed(() => String(route.query.unit || ''))
const { data: catalogData, error: catalogError } = await useAsyncData('catalog', catalog, { deep: false })
const { data: partyData } = await useAsyncData('parties', parties, { deep: false })
const rows = shallowRef<EntityElectionResult[]>([])
const entity = ref<AggregatedRow>()
const candidate = ref<CandidateRecord>()
const partyCandidates = shallowRef<CandidateSummary[]>([])
const selectedElection = ref('')
const loading = ref(true)
const failed = ref(false)

watch([id, requestedElection, catalogData], async ([entityId, electionId, catalogValue], _, onCleanup) => {
  candidate.value = undefined
  if (!catalogValue) return
  let cancelled = false
  onCleanup(() => { cancelled = true })
  const electionIds = electionId ? [electionId] : catalogValue.elections.map(item => item.id)
  for (const selectedId of electionIds) {
    try {
      const value = await candidateDetails(selectedId, entityId)
      if (!cancelled) candidate.value = value
      break
    } catch { /* This election has no detail file for the entity. */ }
  }
}, { immediate: true })

watch([id, catalogData, partyData], async ([entityId, catalogValue, partiesValue], _, onCleanup) => {
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
      const ballot = (official || files[0])?.ballot.kind
      const candidates = ballot === 'single_member' ? await electionCandidates(election.id) : []
      const results = ballot === 'single_member' ? partyRows(total, candidates, partiesValue || []) : total.rows
      return { election, total, result: total.rows.find(row => row.id === entityId) || results.find(row => row.id === entityId) }
    }))
    if (cancelled) return
    for (const response of batch) {
      if (response.status === 'rejected') { failed.value = true; continue }
      const { election, total, result } = response.value
      if (!result) continue
      entity.value = result
      collected.push({ election, votes: result.votes, percent: pct(result.votes, total.turnout.valid), units: election.precinct_count })
    }
    rows.value = [...collected].sort((left, right) => right.election.date.localeCompare(left.election.date))
  }
  if (!selectedElection.value) selectedElection.value = requestedElection.value || rows.value[0]?.election.id || ''
  loading.value = false
}, { immediate: true })

watch([selectedElection, id, entity], async ([electionId, entityId, resultEntity], _, onCleanup) => {
  partyCandidates.value = []
  if (!electionId || (resultEntity?.type !== 'party' && !(partyData.value || []).some(item => item.id === entityId))) return
  let cancelled = false
  onCleanup(() => { cancelled = true })
  try {
    const values = await electionCandidates(electionId)
    if (!cancelled) partyCandidates.value = values.filter(item => item.party_id === entityId)
  } catch { if (!cancelled) failed.value = true }
}, { immediate: true })

watch(requestedElection, value => { if (value) selectedElection.value = value }, { immediate: true })
const displayedName = computed(() => candidate.value?.name || entity.value?.name || partyData.value?.find(item => item.id === id.value)?.name)
const isParty = computed(() => entity.value?.type === 'party' || Boolean(partyData.value?.some(item => item.id === id.value)))
const displayedParty = computed(() => {
  const partyId = isParty.value ? id.value : candidate.value?.party?.id
  const partyName = isParty.value ? entity.value?.name : candidate.value?.party?.name
  return partyFor(partyData.value || [], partyId, partyName)
})
const backTarget = computed(() => requestedElection.value
  ? { path: '/', query: { election: requestedElection.value } } : '/')
const formatDate = (value?: string) => value ? new Date(`${value}T00:00:00`).toLocaleDateString('ru-RU') : '—'
</script>

<template>
  <NuxtLink class="back" :to="backTarget">← {{ requestedUnit ? 'К результатам' : 'Все голосования' }}</NuxtLink>
  <section class="result-title">
    <p class="eyebrow">{{ isParty ? 'ПАРТИЯ / ИЗБИРАТЕЛЬНОЕ ОБЪЕДИНЕНИЕ' : 'КАНДИДАТ' }}</p>
    <div class="entity-heading"><PartyLogo :party="displayedParty" size="large" /><h1>{{ displayedName || (loading && !catalogError ? 'Загрузка…' : 'Данные не найдены') }}</h1></div>
    <p v-if="candidate?.party">Выдвинут(а): <NuxtLink class="entity" :to="{ path: `/entity/${encodeURIComponent(candidate.party.id)}`, query: { election: candidate.election_id, unit: requestedUnit || undefined } }">{{ candidate.party.name }}</NuxtLink></p>
    <p v-else>Итоги на наиболее высоком доступном уровне каждого голосования.</p>
  </section>

  <dl v-if="candidate" class="candidate-facts">
    <div><dt>Дата рождения</dt><dd>{{ formatDate(candidate.birth_date) }}</dd></div>
    <div v-if="candidate.birth_place"><dt>Место рождения</dt><dd>{{ candidate.birth_place }}</dd></div>
    <div v-if="candidate.address"><dt>Место жительства</dt><dd>{{ candidate.address }}</dd></div>
    <div v-if="candidate.education"><dt>Образование</dt><dd>{{ candidate.education }}</dd></div>
    <div v-if="candidate.work || candidate.position"><dt>Работа и должность</dt><dd>{{ [candidate.work, candidate.position].filter(Boolean).join(', ') }}</dd></div>
    <div v-if="candidate.status"><dt>Статус</dt><dd>{{ candidate.status }}</dd></div>
    <div v-if="candidate.regional_group"><dt>Список</dt><dd>{{ candidate.regional_group }}<template v-if="candidate.number_in_list">, № {{ candidate.number_in_list }}</template></dd></div>
  </dl>
  <p v-if="candidate?.source.url" class="source-link"><a :href="candidate.source.url" target="_blank" rel="noopener noreferrer">Источник данных о кандидате ↗</a> · Получено {{ candidate.source.retrieved_at.slice(0, 10) }}</p>
  <p v-if="failed || catalogError" role="alert">Часть данных не удалось загрузить. Обновите страницу, чтобы повторить.</p>

  <section v-if="isParty && rows.length" class="candidate-section">
    <div class="entity-tabs" role="tablist" aria-label="Выборы">
      <button v-for="result in rows" :key="result.election.id" type="button" role="tab" :aria-selected="selectedElection === result.election.id" @click="selectedElection = result.election.id">{{ result.election.name }} · {{ result.election.date.slice(0, 4) }}</button>
    </div>
    <h2>Кандидаты на этих выборах</h2>
    <div v-if="partyCandidates.length" class="table-wrap">
      <table>
        <thead><tr><th>Кандидат</th><th>Округ / группа</th><th>Статус</th></tr></thead>
        <tbody><tr v-for="item in partyCandidates" :key="item.id">
          <td><NuxtLink class="entity" :to="{ path: `/entity/${encodeURIComponent(item.id)}`, query: { election: selectedElection, unit: requestedUnit || undefined } }">{{ item.name }}</NuxtLink></td>
          <td>{{ item.district_number ? `Округ № ${item.district_number}` : item.regional_group || '—' }}</td><td>{{ item.status || '—' }}</td>
        </tr></tbody>
      </table>
    </div>
    <p v-else class="status">Список кандидатов для этих выборов не опубликован в импортированных данных.</p>
  </section>

  <div class="section-heading entity-results-heading"><div><p class="eyebrow">АРХИВ</p><h2>Результаты по голосованиям</h2></div></div>
  <div v-if="rows.length" class="table-wrap entity-results"><table>
    <thead><tr><th>Голосование</th><th>Голоса</th><th>Доля</th><th>УИК</th></tr></thead>
    <tbody><tr v-for="result in rows" :key="result.election.id">
      <td><NuxtLink :to="{ path: '/', query: { election: result.election.id } }" class="entity">{{ result.election.name }}</NuxtLink></td>
      <td>{{ result.votes.toLocaleString('ru-RU') }}</td><td><b>{{ result.percent.toFixed(2) }}%</b></td><td>{{ result.units }}</td>
    </tr></tbody>
  </table></div>
  <p v-else-if="!loading" class="status">Результаты для этого участника пока не найдены.</p>
</template>
