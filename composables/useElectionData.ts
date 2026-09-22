import type {
  AggregateResult,
  AggregatedRow,
  ElectionCatalogDetail,
  ElectionCatalog,
  ElectionUnit,
  NationalChartAnalysis,
  RegionalChartAnalysis,
  ResultFile,
  Turnout,
} from '~/types/election'

export async function catalog(): Promise<ElectionCatalog> {
  return await $fetch<ElectionCatalog>('/data/index.json')
}

async function fetchResultFiles(
  electionId: string,
  files: string[],
): Promise<ResultFile[]> {
  return await Promise.all(
    files.map(file => $fetch<ResultFile>(`/data/${electionId}/${file}`)),
  )
}

export async function electionCatalog(electionId: string): Promise<ElectionCatalogDetail> {
  return await $fetch<ElectionCatalogDetail>(`/data/${electionId}/index.json`)
}

export async function precinctPage(electionId: string, page: number): Promise<CatalogPrecinct[]> {
  return await $fetch<CatalogPrecinct[]>(`/data/${electionId}/precinct-pages/${page}.json`)
}

export async function resultBundleFor(electionId: string, unitId: string): Promise<{ files: ResultFile[], official: ResultFile | null }> {
  const election = await electionCatalog(electionId)
  const officialFile = election.official_results[unitId]
  if (officialFile) {
    return { files: [], official: await $fetch<ResultFile>(`/data/${electionId}/${officialFile}`) }
  }
  const computedFile = election.computed_results[unitId]
  if (computedFile) {
    return { files: [await $fetch<ResultFile>(`/data/${electionId}/${computedFile}`)], official: null }
  }
  return { files: [await $fetch<ResultFile>(`/data/${electionId}/precincts/${unitId}.json`)], official: null }
}

export async function chartAnalysis(
  electionId: string,
  unit: ElectionUnit,
): Promise<NationalChartAnalysis | RegionalChartAnalysis> {
  if (unit.kind === 'national') {
    return await $fetch<NationalChartAnalysis>(`/data/${electionId}/analysis/national.json`)
  }
  const regionId = unit.kind === 'region'
    ? unit.id
    : unit.administrative_path?.find(entry => entry.kind === 'region')?.id
  if (!regionId) throw new Error('The unit has no region analysis segment')
  return await $fetch<RegionalChartAnalysis>(`/data/${electionId}/analysis/${regionId}.json`)
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
