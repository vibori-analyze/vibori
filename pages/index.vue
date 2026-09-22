<script setup lang="ts">
import type { CatalogElection, CatalogPrecinct, CatalogUnit, ElectionCatalogDetail } from '~/types/election'

const { data, error } = await useAsyncData('catalog', catalog)
const electionId = ref('')
const selected = ref<ElectionCatalogDetail | null>(null)
const selectedError = ref<Error | null>(null)
const root = ref<CatalogUnit[]>([])
const branches = reactive<Record<string, CatalogUnit[]>>({})
const precincts = reactive<Record<string, CatalogPrecinct[]>>({})
const loading = reactive<Record<string, boolean>>({})

watchEffect(() => {
  if (!electionId.value && data.value?.elections[0]) electionId.value = data.value.elections[0].id
})
watch(electionId, async (id) => {
  selected.value = null
  root.value = []
  Object.keys(branches).forEach(key => delete branches[key])
  Object.keys(precincts).forEach(key => delete precincts[key])
  if (!id) return
  try {
    selected.value = await electionCatalog(id)
  } catch (cause: unknown) {
    selectedError.value = cause instanceof Error ? cause : new Error(String(cause))
  }
})
async function loadBranch(id: string): Promise<void> {
  if (!selected.value || branches[id] || loading[id]) return
  loading[id] = true
  try { branches[id] = await treeBranch(selected.value.id, id) } finally { loading[id] = false }
}
async function loadRoot(): Promise<void> {
  if (!selected.value || root.value.length || loading.root) return
  loading.root = true
  try { root.value = await treeBranch(selected.value.id, selected.value.tree_root) } finally { loading.root = false }
}
async function loadPrecincts(id: string): Promise<void> {
  if (!selected.value || precincts[id] || loading[id]) return
  loading[id] = true
  try { precincts[id] = await tikPrecinctPage(selected.value.id, id, 0) } finally { loading[id] = false }
}
function resultLink(election: CatalogElection | ElectionCatalogDetail, unit: CatalogUnit | CatalogPrecinct): string {
  return `/result/${election.id}/${encodeURIComponent(unit.id)}`
}
</script>
<template>
  <div class="home">
    <section class="hero"><p class="eyebrow">ОТКРЫТАЯ АРХИВНАЯ СИСТЕМА</p><h1>Результаты,<br><em>которые можно проверить.</em></h1><p>Первичные протоколы УИК, собранные в один понятный обзор.</p></section>
    <p v-if="error || selectedError" class="empty">Не удалось загрузить каталог данных.</p>
    <section v-else-if="data" class="catalog">
      <div class="elections"><label>ГОЛОСОВАНИЕ</label><select v-model="electionId"><option v-for="election in data.elections" :key="election.id" :value="election.id">{{ election.name }} · {{ election.date }}</option></select></div>
      <p v-if="!selected" class="empty">Загрузка данных голосования…</p>
      <template v-else>
        <div class="summary"><span>{{ selected.precinct_count }} УИК</span><span>{{ selected.ballot_title }}</span></div>
        <div class="tree">
          <details @toggle="event => (event.target as HTMLDetailsElement).open && loadRoot()"><summary><NuxtLink :to="resultLink(selected, { id: selected.tree_root, name: 'ЦИК России', kind: 'national', count: selected.precinct_count })" @click.stop>ЦИК России</NuxtLink><span>{{ selected.precinct_count }} УИК</span></summary>
            <p v-if="loading.root" class="chart-note">Загрузка…</p>
            <div class="branches" v-else>
              <details v-for="district in root" :key="district.id" @toggle="event => (event.target as HTMLDetailsElement).open && loadBranch(district.id)"><summary><NuxtLink :to="resultLink(selected, district)" @click.stop>{{ district.kind === 'district' && district.number ? `Округ №${district.number}` : district.name }}</NuxtLink><span v-if="district.kind !== 'district'">{{ district.count }} УИК</span></summary>
                <p v-if="loading[district.id]" class="chart-note">Загрузка…</p>
                <div v-else class="branches">
                  <details v-for="tik in branches[district.id]" :key="tik.id" @toggle="event => (event.target as HTMLDetailsElement).open && loadPrecincts(tik.id)"><summary><NuxtLink :to="resultLink(selected, tik)" @click.stop>{{ tik.name }}</NuxtLink><span>{{ tik.count }} УИК</span></summary>
                    <p v-if="loading[tik.id]" class="chart-note">Загрузка…</p>
                    <div v-else class="branches precincts"><NuxtLink v-for="precinct in precincts[tik.id]" :key="precinct.id" :to="resultLink(selected, precinct)"><small>УИК №{{ precinct.number }}</small>{{ precinct.name }}</NuxtLink></div>
                  </details>
                </div>
              </details>
            </div>
          </details>
        </div>
      </template>
    </section>
  </div>
</template>
