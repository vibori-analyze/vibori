<script setup lang="ts">
const props = defineProps<{ rows: any[], valid: number }>()
const sort = useState<'votes' | 'percent'>('result-sort', () => 'percent')
if (import.meta.client) sort.value = (localStorage.getItem('vibori:result-sort') as any) || sort.value
function setSort(next: 'votes' | 'percent') { sort.value = next; if (import.meta.client) localStorage.setItem('vibori:result-sort', next) }
const ordered = computed(() => [...props.rows].sort((a, b) => sort.value === 'votes' ? b.votes - a.votes : pct(b.votes, props.valid) - pct(a.votes, props.valid)))
</script>
<template>
  <div class="table-wrap"><table>
    <thead><tr><th>Кандидат / список</th><th><button @click="setSort('votes')">Голоса <span v-if="sort==='votes'">↓</span></button></th><th><button @click="setSort('percent')">Доля <span v-if="sort==='percent'">↓</span></button></th></tr></thead>
    <tbody><tr v-for="r in ordered" :key="r.id"><td><NuxtLink :to="`/entity/${encodeURIComponent(r.id)}`" class="entity">{{ r.name }}</NuxtLink><small v-if="r.type === 'candidate' && r.party_id">кандидат</small></td><td>{{ r.votes.toLocaleString('ru-RU') }}</td><td><b>{{ pct(r.votes, valid).toFixed(2) }}%</b><i :style="{width: `${pct(r.votes, valid)}%`}" /></td></tr></tbody>
  </table></div>
</template>
