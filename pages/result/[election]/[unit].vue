<script setup lang="ts">
const route = useRoute()
const eid = computed(() => String(route.params.election)); const uid = computed(() => String(route.params.unit))
const { data: files, error } = await useAsyncData(() => `files-${eid.value}`, () => resultsFor(eid.value))
const picked = computed(() => files.value?.filter(f => f.unit.id === uid.value || f.unit.administrative_path?.some((p:any) => p.id === uid.value)) || [])
const total = computed(() => aggregate(picked.value)); const unit = computed(() => files.value && unitName(files.value, uid.value))
const turnout = computed(() => total.value.turnout.registered ? total.value.turnout.issued / total.value.turnout.registered * 100 : 0)
</script>
<template><div v-if="error" class="empty">Результаты не найдены.</div><template v-else-if="files && unit"><NuxtLink class="back" to="/">← Все голосования</NuxtLink><section class="result-title"><p class="eyebrow">{{unit.kind === 'precinct' ? 'УЧАСТКОВАЯ КОМИССИЯ' : 'СВОДНЫЙ УРОВЕНЬ'}}</p><h1>{{unit.name}}</h1><p>{{files[0].election.name}} · {{files[0].ballot.title}}</p></section><section class="stats"><div><span>ЯВКА</span><b>{{turnout.toFixed(2)}}%</b><small>{{total.turnout.issued.toLocaleString('ru-RU')}} из {{total.turnout.registered.toLocaleString('ru-RU')}}</small></div><div><span>ДЕЙСТВИТЕЛЬНЫЕ</span><b>{{total.turnout.valid.toLocaleString('ru-RU')}}</b><small>недействительных: {{total.turnout.invalid.toLocaleString('ru-RU')}}</small></div><div><span>ПРОТОКОЛОВ</span><b>{{picked.length}}</b><small>низовой уровень данных</small></div></section><ResultTable :rows="total.rows" :valid="total.turnout.valid"/><ShareChart :files="picked"/></template><div v-else class="empty">Загрузка результатов…</div></template>
