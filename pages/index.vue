<script setup lang="ts">
import type { CatalogElection, CatalogPrecinct, CatalogUnit, ElectionCatalogDetail } from '~/types/election'

const { data, error } = await useAsyncData('catalog', catalog)
const electionId = ref('')

watchEffect(() => {
  const firstElection = data.value?.elections[0]
  if (!electionId.value && firstElection) {
    electionId.value = firstElection.id
  }
})

const selected = ref<ElectionCatalogDetail | null>(null)
const selectedError = ref<Error | null>(null)
const precinctLimit = ref(500)

watch(electionId, async (id) => {
  precinctLimit.value = 500
  selected.value = null
  selectedError.value = null
  if (!id) {
    return
  }
  try {
    selected.value = await electionCatalog(id)
  } catch (error: unknown) {
    selectedError.value = error instanceof Error ? error : new Error(String(error))
  }
})

function resultLink(
  election: CatalogElection | ElectionCatalogDetail,
  unit: CatalogUnit | CatalogPrecinct,
): string {
  return `/result/${election.id}/${encodeURIComponent(unit.id)}`
}
</script>
<template>
  <div class="home">
    <section class="hero">
      <p class="eyebrow">ОТКРЫТАЯ АРХИВНАЯ СИСТЕМА</p>
      <h1>Результаты,<br><em>которые можно проверить.</em></h1>
      <p>
        Первичные протоколы УИК, собранные в один понятный обзор. Выберите
        голосование и уровень комиссии.
      </p>
    </section>
    <p v-if="error" class="empty">Не удалось загрузить каталог данных.</p>
    <section v-else-if="data" class="catalog">
      <div class="elections">
        <label>ГОЛОСОВАНИЕ</label>
        <select v-model="electionId">
          <option
            v-for="election in data.elections"
            :key="election.id"
            :value="election.id"
          >
            {{ election.name }} · {{ election.date }}
          </option>
        </select>
      </div>
      <p v-if="selectedError" class="empty">Не удалось загрузить данные голосования.</p>
      <p v-else-if="!selected" class="empty">Загрузка данных голосования…</p>
      <template v-else>
      <div class="summary">
        <span>{{ selected.precinct_count }} УИК</span>
        <span>
          {{ selected.region_count }} регион{{ selected.region_count === 1 ? '' : 'а' }}
        </span>
        <span>{{ selected.ballot_title }}</span>
      </div>
      <div class="tree">
        <details open>
          <summary><b>По регионам</b><span>{{ selected.region_count }}</span></summary>
          <div class="branches">
            <NuxtLink
              v-for="region in selected.regions"
              :key="region.id"
              :to="resultLink(selected, region)"
            >
              {{ region.name }} <small>{{ region.count }} УИК</small>
            </NuxtLink>
          </div>
        </details>
        <details v-if="selected.districts.length">
          <summary>
            <b>Избирательные округа</b><span>{{ selected.districts.length }}</span>
          </summary>
          <div class="branches">
            <NuxtLink
              v-for="district in selected.districts"
              :key="district.id"
              :to="resultLink(selected, district)"
            >
              {{ district.name }} <small>{{ district.count }} УИК</small>
            </NuxtLink>
          </div>
        </details>
        <details>
          <summary>
            <b>Территориальные комиссии</b><span>{{ selected.tiks.length }}</span>
          </summary>
          <div class="branches">
            <NuxtLink
              v-for="tik in selected.tiks"
              :key="tik.id"
              :to="resultLink(selected, tik)"
            >
              {{ tik.name }} <small>{{ tik.count }} УИК</small>
            </NuxtLink>
          </div>
        </details>
        <details>
          <summary>
            <b>Участковые комиссии</b><span>{{ selected.precinct_count }}</span>
          </summary>
          <div class="branches precincts">
            <NuxtLink
              v-for="precinct in selected.precincts.slice(0, precinctLimit)"
              :key="precinct.id"
              :to="resultLink(selected, precinct)"
            >
              <small>УИК №{{ precinct.number }}</small>
              {{ precinct.name }}
              <small>{{ precinct.region }}</small>
            </NuxtLink>
          </div>
          <button
            v-if="precinctLimit < selected.precincts.length"
            type="button"
            @click="precinctLimit += 500"
          >
            Показать ещё {{ Math.min(500, selected.precincts.length - precinctLimit) }} УИК
          </button>
        </details>
      </div>
      </template>
    </section>
  </div>
</template>
