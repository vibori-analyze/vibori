import type {
  AggregateResult,
  AggregatedRow,
  CatalogPrecinct,
  CatalogUnit,
  CandidateRecord,
  CandidateSummary,
  PartyRecord,
  ElectionCatalogDetail,
  ElectionCatalog,
  ElectionUnit,
  NationalChartAnalysis,
  RegionalChartAnalysis,
  ResultFile,
  Turnout,
} from '~/types/election'

// Reuse immutable catalogs and concurrent requests without retaining large charts.
const cache = new Map<string, Promise<unknown>>()
function staticData<T>(path: string): Promise<T> {
  const base = useRuntimeConfig().app.baseURL
  const url = `${base.replace(/\/$/, '')}/data/${path}`
  const existing = cache.get(url)
  if (existing) return existing as Promise<T>
  const request = $fetch<T>(url).catch(error => { cache.delete(url); throw error })
  cache.set(url, request)
  if (cache.size > 32) cache.delete(cache.keys().next().value!)
  return request
}

export async function catalog(): Promise<ElectionCatalog> {
  return staticData<ElectionCatalog>('index.json')
}

export async function parties(): Promise<PartyRecord[]> {
  return staticData<PartyRecord[]>('parties.json').catch(() => [])
}

export function partyFor(
  list: PartyRecord[],
  id?: string,
  name?: string,
): PartyRecord | undefined {
  const byId = list.find(party => party.id === id)
  if (byId || !name) return byId
  const normalized = name.toLocaleUpperCase('ru').replaceAll('Ё', 'Е')
  return list.find(party => party.aliases?.some(alias => normalized.includes(alias.toLocaleUpperCase('ru').replaceAll('Ё', 'Е'))))
}

export async function electionCatalog(electionId: string): Promise<ElectionCatalogDetail> {
  return staticData<ElectionCatalogDetail>(`${electionId}/index.json`)
}

export async function precinctPage(electionId: string, page: number): Promise<CatalogPrecinct[]> {
  return staticData<CatalogPrecinct[]>(`${electionId}/precinct-pages/${page}.json`)
}

export async function treeBranch(electionId: string, unitId: string): Promise<CatalogUnit[]> {
  return staticData<CatalogUnit[]>(`${electionId}/tree/${unitId}.json`)
}

export async function electionCandidates(electionId: string): Promise<CandidateSummary[]> {
  const election = await electionCatalog(electionId)
  if (!election.candidates_file) return []
  return staticData<CandidateSummary[]>(`${electionId}/${election.candidates_file}`)
}

export async function candidateDetails(electionId: string, candidateId: string): Promise<CandidateRecord> {
  return staticData<CandidateRecord>(`${electionId}/candidates/${encodeURIComponent(candidateId)}.json`)
}

export async function tikPrecinctPage(electionId: string, tikId: string, page: number): Promise<CatalogPrecinct[]> {
  return staticData<CatalogPrecinct[]>(`${electionId}/tree/${tikId}-${page}.json`)
}

export async function resultBundleFor(electionId: string, unitId: string): Promise<{ files: ResultFile[], official: ResultFile | null }> {
  const election = await electionCatalog(electionId)
  const officialFile = election.official_results[unitId]
  if (officialFile) {
    return { files: [], official: await staticData<ResultFile>(`${electionId}/${officialFile}`) }
  }
  const computedFile = election.computed_results[unitId]
  if (computedFile) {
    return { files: [await staticData<ResultFile>(`${electionId}/${computedFile}`)], official: null }
  }
  return { files: [await staticData<ResultFile>(`${electionId}/precincts/${unitId}.json`)], official: null }
}

export async function chartAnalysis(
  electionId: string,
  unit: ElectionUnit,
): Promise<NationalChartAnalysis | RegionalChartAnalysis> {
  const base = useRuntimeConfig().app.baseURL.replace(/\/$/, '')
  if (unit.kind === 'national') {
    return await $fetch<NationalChartAnalysis>(`${base}/data/${electionId}/analysis/national.json`)
  }
  const regionId = unit.kind === 'region'
    ? unit.id
    : unit.administrative_path?.find(entry => entry.kind === 'region')?.id
  if (!regionId) throw new Error('The unit has no region analysis segment')
  return await $fetch<RegionalChartAnalysis>(`${base}/data/${electionId}/analysis/${regionId}.json`)
}

export function pct(votes: number, valid: number): number {
  return valid ? votes / valid * 100 : 0
}

export function aggregate(files: ResultFile[]): AggregateResult {
  const turnout: Turnout = { registered: 0, issued: 0, valid: 0, invalid: 0 }
  const entities = new Map<string, AggregatedRow>()

  for (const file of files) {
    turnout.registered += file.turnout.registered
    turnout.issued += file.turnout.issued
    turnout.valid += file.turnout.valid
    turnout.invalid += file.turnout.invalid

    for (const result of file.results) {
      const current = entities.get(result.entity.id) ?? {
        ...result.entity,
        votes: 0,
      }
      current.votes += result.votes
      entities.set(result.entity.id, current)
    }
  }

  return { turnout, rows: [...entities.values()] }
}

export function unitName(files: ResultFile[], id: string): ElectionUnit | undefined {
  const root = files.find(f => f.unit.id === id)?.unit
  if (root) {
    return root
  }
  return files
    .flatMap(file => file.unit.administrative_path ?? [])
    .find(unit => unit.id === id)
}
