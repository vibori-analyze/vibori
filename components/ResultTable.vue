<script setup lang="ts">
import type { AggregatedRow } from '~/types/election'

const props = defineProps<{ rows: AggregatedRow[], valid: number }>()
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
      <input id="result-search" v-model="search" type="search" placeholder="Найти кандидата или партию">
      <span class="sr-only">Поиск по результатам</span>
      <kbd>{{ filtered.length }}</kbd>
    </label>
    <div class="table-wrap">
      <table>
        <thead><tr><th>Кандидат / список</th><th aria-sort="descending">Голоса ↓</th><th>Доля</th></tr></thead>
        <tbody>
          <tr v-for="result in visible" :key="result.id">
            <td>
              <NuxtLink :to="'/entity/' + encodeURIComponent(result.id)" class="entity">{{ result.name }}</NuxtLink>
              <small v-if="result.type === 'candidate' && result.party_id">кандидат</small>
            </td>
            <td>{{ result.votes.toLocaleString('ru-RU') }}</td>
            <td><b>{{ pct(result.votes, valid).toFixed(2) }}%</b><i :style="{ width: pct(result.votes, valid) + '%' }" /></td>
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
