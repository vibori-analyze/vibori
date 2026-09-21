<script setup lang="ts">
const props = defineProps<{ files: any[], initial?: string }>()
const selected = ref(props.initial || '')
const candidates = computed(() => { const map = new Map(); props.files.forEach(f => f.results.forEach((r:any) => map.set(r.entity.id, r.entity))); return [...map.values()] as any[] })
watchEffect(() => { if (!selected.value && candidates.value[0]) selected.value = candidates.value[0].id })
const points = computed(() => props.files.map((f, i) => { const r = f.results.find((x:any) => x.entity.id === selected.value); return { x: props.files.length === 1 ? 50 : i / (props.files.length - 1) * 100, y: 100 - (r ? pct(r.votes, f.turnout.valid) : 0), label: f.unit.number || f.unit.name, val: r ? pct(r.votes, f.turnout.valid) : 0 } }))
const line = computed(() => points.value.map(p => `${p.x},${p.y}`).join(' '))
</script>
<template><section class="chart"><div class="chart-head"><div><span class="eyebrow">ДИНАМИКА ПО УЧАСТКАМ</span><h3>Доля голосов</h3></div><select v-model="selected"><option v-for="x in candidates" :value="x.id" :key="x.id">{{x.name}}</option></select></div><svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img"><line x1="0" y1="75" x2="100" y2="75"/><line x1="0" y1="50" x2="100" y2="50"/><line x1="0" y1="25" x2="100" y2="25"/><polyline :points="line"/><circle v-for="p in points" :cx="p.x" :cy="p.y" r="1.7"><title>{{p.label}}: {{p.val.toFixed(2)}}%</title></circle></svg><div class="chart-note">Наведите на точку, чтобы увидеть участок и долю голосов.</div></section></template>
