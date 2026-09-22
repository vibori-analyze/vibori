<script setup lang="ts">
import type { AggregatedRow } from '~/types/election'

type SortColumn = 'votes' | 'percent'

const props = defineProps<{
  rows: AggregatedRow[]
  valid: number
}>()
const sort = useState<SortColumn>('result-sort', () => 'percent')

if (import.meta.client) {
  const savedSort = localStorage.getItem('vibori:result-sort')
  if (savedSort === 'votes' || savedSort === 'percent') {
    sort.value = savedSort
  }
}

function setSort(next: SortColumn): void {
  sort.value = next
  if (import.meta.client) {
    localStorage.setItem('vibori:result-sort', next)
  }
}

const ordered = computed(() => [...props.rows].sort((left, right) => {
  if (sort.value === 'votes') {
    return right.votes - left.votes
  }
  return pct(right.votes, props.valid) - pct(left.votes, props.valid)
}))
</script>
<template>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Кандидат / список</th>
          <th>
            <button @click="setSort('votes')">
              Голоса <span v-if="sort === 'votes'">↓</span>
            </button>
          </th>
          <th>
            <button @click="setSort('percent')">
              Доля <span v-if="sort === 'percent'">↓</span>
            </button>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="result in ordered" :key="result.id">
          <td>
            <NuxtLink
              :to="`/entity/${encodeURIComponent(result.id)}`"
              class="entity"
            >
              {{ result.name }}
            </NuxtLink>
            <small v-if="result.type === 'candidate' && result.party_id">кандидат</small>
          </td>
          <td>{{ result.votes.toLocaleString('ru-RU') }}</td>
          <td>
            <b>{{ pct(result.votes, valid).toFixed(2) }}%</b>
            <i :style="{ width: `${pct(result.votes, valid)}%` }" />
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
