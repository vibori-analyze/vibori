<script setup lang="ts">
import type { ElectionEntity, ResultFile } from '~/types/election'

const props = defineProps<{
  files: ResultFile[]
  initial?: string
}>()
const selected = ref(props.initial ?? '')
const { data: partyData } = await useAsyncData('parties', parties, { deep: false })
const candidates = computed<ElectionEntity[]>(() => {
  const entities = new Map<string, ElectionEntity>()
  for (const file of props.files) {
    for (const result of file.results) {
      entities.set(result.entity.id, result.entity)
    }
  }
  return [...entities.values()]
})

watchEffect(() => {
  const firstCandidate = candidates.value[0]
  if (!selected.value && firstCandidate) {
    selected.value = firstCandidate.id
  }
})

const selectedEntity = computed(() => candidates.value.find(candidate => candidate.id === selected.value))
const selectedParty = computed(() => {
  const entity = selectedEntity.value
  if (!entity) return undefined
  return partyFor(
    partyData.value || [],
    entity.type === 'party' ? entity.id : entity.party_id,
    entity.type === 'party' ? entity.name : entity.party_name,
  )
})

const points = computed(() => props.files.map((file, index) => {
  const result = file.results.find(item => item.entity.id === selected.value)
  const value = result ? pct(result.votes, file.turnout.valid) : 0
  return {
    x: props.files.length === 1 ? 50 : index / (props.files.length - 1) * 100,
    y: 100 - value,
    label: file.unit.number || file.unit.name,
    value,
  }
}))
const line = computed(() => points.value.map(point => `${point.x},${point.y}`).join(' '))
</script>
<template>
  <section class="chart">
    <div class="chart-head">
      <div>
        <span class="eyebrow">ДИНАМИКА ПО УЧАСТКАМ</span>
        <h3>Доля голосов</h3>
      </div>
      <span class="chart-choice">
        <select v-model="selected" aria-label="Партия или кандидат для графика">
          <option v-for="candidate in candidates" :key="candidate.id" :value="candidate.id">
            {{ candidate.name }}
          </option>
        </select>
        <PartyLogo :party="selectedParty" />
      </span>
    </div>
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img">
      <line x1="0" y1="75" x2="100" y2="75" />
      <line x1="0" y1="50" x2="100" y2="50" />
      <line x1="0" y1="25" x2="100" y2="25" />
      <polyline :points="line" :style="{ stroke: selectedParty?.color }" />
      <circle
        v-for="point in points"
        :key="`${point.label}-${point.x}`"
        :cx="point.x"
        :cy="point.y"
        r="1.7"
        :style="{ stroke: selectedParty?.color }"
      >
        <title>{{ point.label }}: {{ point.value.toFixed(2) }}%</title>
      </circle>
    </svg>
    <div class="chart-note">
      Наведите на точку, чтобы увидеть участок и долю голосов.
    </div>
  </section>
</template>
