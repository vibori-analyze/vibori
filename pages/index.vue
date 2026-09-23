<script setup lang="ts">
import type { CatalogPrecinct, CatalogUnit } from '~/types/election'

const route = useRoute()
const router = useRouter()
const { data, error, refresh } = await useAsyncData('catalog', catalog, { deep: false })
const electionId = computed(() => String(route.query.election || data.value?.elections.find(item => item.ballot_kind === 'party_list')?.id || data.value?.elections[0]?.id || ''))
const election = computed(() => data.value?.elections.find(item => item.id === electionId.value))
const trail = shallowRef<CatalogUnit[]>([])
const units = shallowRef<Array<CatalogUnit | CatalogPrecinct>>([])
const loading = ref(false)
const loadError = ref(false)
const retry = ref(0)
const search = ref('')
const page = ref(1)
const pageSize = 48
const current = computed(() => trail.value.at(-1))
const mapUnits = computed(() => units.value.filter((unit): unit is CatalogUnit => 'kind' in unit))
const mapRegion = computed(() => current.value?.kind === 'region' ? current.value : undefined)
const selectedResultUnit = computed(() => current.value?.id || election.value?.national_id || '')
const normalize = (value: string) => value.toLocaleLowerCase('ru').replaceAll('ё', 'е').trim()
const searchable = computed(() => units.value.map(unit => ({ unit, text: normalize([unit.name, unit.number || '', 'region' in unit ? unit.region : ''].join(' ')) })))
const matches = computed(() => {
  const terms = normalize(search.value).split(/\s+/).filter(Boolean)
  return searchable.value.filter(item => terms.every(term => item.text.includes(term))).map(item => item.unit)
})
const pages = computed(() => Math.ceil(matches.value.length / pageSize))
const visible = computed(() => matches.value.slice((page.value - 1) * pageSize, page.value * pageSize))
watch(search, () => { page.value = 1 })

watch([election, () => route.query.path, retry], async ([selected, path], _, onCleanup) => {
  let cancelled = false
  onCleanup(() => { cancelled = true })
  units.value = []
  trail.value = []
  search.value = ''
  page.value = 1
  loadError.value = false
  loading.value = false
  if (!selected) return
  loading.value = true
  try {
    let children = await treeBranch(selected.id, selected.national_id)
    const nextTrail: CatalogUnit[] = []
    for (const id of String(path || '').split('/').filter(Boolean)) {
      const node = children.find(item => item.id === id)
      if (!node) throw new Error('Unknown commission')
      nextTrail.push(node)
      if (node.kind === 'territorial_commission') {
        const precincts: CatalogPrecinct[] = []
        for (let index = 0; index < Math.ceil(node.count / 500); index += 1) {
          precincts.push(...await tikPrecinctPage(selected.id, node.id, index))
          if (cancelled) return
        }
        if (!cancelled) units.value = precincts
        break
      }
      children = await treeBranch(selected.id, node.id)
      if (cancelled) return
    }
    if (!cancelled) {
      trail.value = nextTrail
      if (nextTrail.at(-1)?.kind !== 'territorial_commission') units.value = children
    }
  } catch {
    if (!cancelled) loadError.value = true
  } finally {
    if (!cancelled) loading.value = false
  }
}, { immediate: true })

function browse(depth: number, unit?: CatalogUnit): void {
  const path = trail.value.slice(0, depth).map(item => item.id)
  if (unit) path.push(unit.id)
  void router.push({ query: { election: electionId.value, ...(path.length ? { path: path.join('/') } : {}) } })
}
function chooseElection(event: Event): void {
  void router.push({ query: { election: (event.target as HTMLSelectElement).value } })
}
function selectMapUnit(unit: CatalogUnit): void { browse(trail.value.length, unit) }
const count = (value: number) => value.toLocaleString('ru-RU')
const ballotLabel = (kind?: string) => kind === 'party_list' ? 'Партийный бюллетень' : kind === 'single_member' ? 'Кандидаты по округам' : ''
useHead({ title: 'Выборы — найти результаты своего участка' })
</script>

<template>
  <div class="home">
    <section class="home-hero">
      <div class="hero-content"><p class="eyebrow">ОТКРЫТЫЙ АРХИВ РЕЗУЛЬТАТОВ</p>
      <h1>Результаты выборов.<br><span>До каждого участка.</span></h1>
      <p>Исследуйте голосование на карте, найдите свою комиссию и откройте протокол с источником данных.</p>
      <a class="primary-link" href="#catalog">Исследовать результаты <span aria-hidden="true">↗</span></a></div>
      <div class="hero-panel" aria-hidden="true"><span>01 / 03</span><div class="hero-panel-art">◎<span>●</span>◎<span>●</span>◎</div><p>Выборы → территория → протокол</p></div>
    </section>
    <section id="catalog" class="browser" aria-label="Каталог результатов">
      <div v-if="error" class="status" role="alert">Не удалось загрузить каталог. <button @click="refresh()">Повторить</button></div>
      <template v-else-if="data">
        <div class="browser-heading">
          <div><p class="eyebrow">ИССЛЕДОВАТЬ АРХИВ</p><h2>Выберите голосование и территорию</h2></div>
          <span class="archive-badge">{{ data.elections.length }} голосования в архиве</span>
        </div>
        <label for="election">1. Голосование</label>
        <select id="election" class="election-select" :value="electionId" @change="chooseElection">
          <option v-for="item in data.elections" :key="item.id" :value="item.id">{{ ballotLabel(item.ballot_kind) || item.ballot_title }} · {{ item.date }} · {{ item.name }}</option>
        </select>
        <template v-if="election">
          <div class="archive-summary"><span><strong>{{ count(election.precinct_count) }}</strong> УИК в архиве</span><span><strong>{{ election.region_count }}</strong> регионов</span><a href="#results">Итоги по стране ↓</a></div>
          <p class="step-label">2. Территория</p>
          <nav class="breadcrumbs" aria-label="Путь к комиссии">
            <button :aria-current="!trail.length ? 'location' : undefined" @click="browse(0)">Все территории</button>
            <template v-for="(unit, index) in trail" :key="unit.id"><span aria-hidden="true">/</span><button :aria-current="index === trail.length - 1 ? 'location' : undefined" @click="browse(index + 1)">{{ unit.name }}</button></template>
          </nav>
          <div class="territory-heading"><h3>{{ current?.name || 'Территории голосования' }}</h3></div>
          <TerritoryMap v-if="!loading && !loadError && (!current || current.kind === 'region') && mapUnits.length" :units="mapUnits" :selected-region="mapRegion" :election-id="electionId" @select="selectMapUnit" />
          <InlineResults v-if="!loading && selectedResultUnit" id="results" :key="`${electionId}-${selectedResultUnit}`" :election-id="electionId" :unit-id="selectedResultUnit" />
          <DistrictPrecinctMap v-if="!loading && current?.kind === 'district'" :election-id="electionId" :district="current" />
          <label class="search-label" for="territory-search">{{ current?.kind === 'territorial_commission' ? '3. Найдите участок' : 'Найдите территорию в списке' }}</label>
          <div class="search-field"><span aria-hidden="true">⌕</span><input id="territory-search" v-model="search" type="search" :placeholder="current?.kind === 'territorial_commission' ? 'Номер или название УИК' : 'Название территории или номер округа'" :disabled="loading" autocomplete="off"><kbd aria-hidden="true">{{ matches.length }}</kbd></div>
          <p v-if="loading" class="status" role="status">Загружаем комиссии…</p>
          <p v-else-if="loadError" class="status" role="alert">Не удалось загрузить комиссии. <button @click="retry++">Повторить</button><button @click="browse(0)">Все территории</button></p>
          <template v-else>
            <p class="list-caption" aria-live="polite">{{ search ? 'Найдено' : 'В этом списке' }}: {{ count(matches.length) }} · Выберите территорию или откройте её результаты</p>
            <div v-if="visible.length" class="territory-grid">
              <article v-for="unit in visible" :key="unit.id" class="territory-card">
                <template v-if="'kind' in unit">
                  <button class="territory-name" @click="browse(trail.length, unit)"><span>{{ unit.name }}</span><span aria-hidden="true">→</span></button>
                  <div class="territory-meta"><span>{{ count(unit.count) }} УИК</span></div>
                </template>
                <NuxtLink v-else class="precinct-link" :to="`/result/${encodeURIComponent(electionId)}/${encodeURIComponent(unit.id)}`"><span><strong>УИК №{{ unit.number || unit.name }}</strong><small>{{ unit.name }} · {{ unit.region }}</small></span><span aria-hidden="true">↗</span></NuxtLink>
              </article>
            </div>
            <p v-else class="status">{{ search ? 'Ничего не найдено. Попробуйте другое название или номер.' : 'В архиве пока нет нижестоящих комиссий.' }}</p>
            <nav v-if="pages > 1" class="pagination" aria-label="Страницы комиссий"><button :disabled="page === 1" @click="page--">← Назад</button><span aria-live="polite"> {{ page }} / {{ pages }} </span><button :disabled="page === pages" @click="page++">Далее →</button></nav>
          </template>
        </template>
        <p v-else class="status">Голосование не найдено. Выберите голосование из списка.</p>
      </template>
      <p v-else class="status" role="status">Загружаем архив…</p>
    </section>
    <aside class="archive-note"><strong>Откуда эти цифры?</strong><p>Официальные сводные протоколы имеют приоритет. Если сводного протокола нет, показываем сумму доступных участков с пометкой «Расчёт». Число УИК в архиве не означает полноту официальных итогов.</p></aside>
  </div>
</template>
