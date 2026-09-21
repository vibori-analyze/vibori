<script setup lang="ts">
const { data: data, error } = await useAsyncData('catalog', catalog)
const electionId = ref('')
watchEffect(() => { if (!electionId.value && data.value?.elections?.[0]) electionId.value = data.value.elections[0].id })
const selected = computed(() => data.value?.elections?.find((e:any) => e.id === electionId.value))
function link(e: any, u: any) { return `/result/${e.id}/${encodeURIComponent(u.id)}` }
</script>
<template><div class="home">
  <section class="hero"><p class="eyebrow">ОТКРЫТАЯ АРХИВНАЯ СИСТЕМА</p><h1>Результаты,<br><em>которые можно проверить.</em></h1><p>Первичные протоколы УИК, собранные в один понятный обзор. Выберите голосование и уровень комиссии.</p></section>
  <p v-if="error" class="empty">Не удалось загрузить каталог данных.</p>
  <section v-else-if="selected" class="catalog"><div class="elections"><label>ГОЛОСОВАНИЕ</label><select v-model="electionId"><option v-for="e in data.elections" :value="e.id" :key="e.id">{{e.name}} · {{e.date}}</option></select></div>
    <div class="summary"><span>{{selected.precinct_count}} УИК</span><span>{{selected.region_count}} регион{{ selected.region_count === 1 ? '' : 'а' }}</span><span>{{selected.ballot_title}}</span></div>
    <div class="tree"><details open><summary><b>По регионам</b><span>{{selected.region_count}}</span></summary><div class="branches"><NuxtLink v-for="r in selected.regions" :to="link(selected,r)" :key="r.id">{{r.name}} <small>{{r.count}} УИК</small></NuxtLink></div></details>
      <details><summary><b>Территориальные комиссии</b><span>{{selected.tiks.length}}</span></summary><div class="branches"><NuxtLink v-for="t in selected.tiks" :to="link(selected,t)" :key="t.id">{{t.name}} <small>{{t.count}} УИК</small></NuxtLink></div></details>
      <details><summary><b>Участковые комиссии</b><span>{{selected.precinct_count}}</span></summary><div class="branches precincts"><NuxtLink v-for="p in selected.precincts" :to="link(selected,p)" :key="p.id"><small>УИК №{{p.number}}</small>{{p.name}}<small>{{p.region}}</small></NuxtLink></div></details></div>
  </section>
</div></template>
