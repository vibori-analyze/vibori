import type {
  AggregateResult,
  AggregatedRow,
  ElectionCatalogDetail,
  ElectionCatalog,
  ElectionUnit,
  PrecinctAnalysis,
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

export async function resultsFor(electionId: string): Promise<ResultFile[]> {
  const election = await electionCatalog(electionId)
  return await fetchResultFiles(electionId, election.files)
}

export async function electionCatalog(electionId: string): Promise<ElectionCatalogDetail> {
  return await $fetch<ElectionCatalogDetail>(`/data/${electionId}/index.json`)
}

export async function precinctAnalysis(electionId: string): Promise<PrecinctAnalysis> {
  return await $fetch<PrecinctAnalysis>(`/data/${electionId}/analysis.json`)
}

export async function resultBundleFor(
  electionId: string,
  unitId: string,
): Promise<{ files: ResultFile[], official: ResultFile | null }> {
  const election = await electionCatalog(electionId)
  const entry = election.official_results?.[unitId]
  const precinctFiles = election.precincts
    .filter(precinct => precinct.id === unitId || precinct.path_ids.includes(unitId))
    .map(precinct => precinct.file)
  if (entry) {
    return {
      files: [],
      official: await $fetch<ResultFile>(`/data/${electionId}/${entry.file}`),
    }
  }
  return { files: await fetchResultFiles(electionId, precinctFiles), official: null }
}

export async function topLevelResultsFor(
  election: ElectionCatalogDetail,
): Promise<ResultFile[]> {
  const official = election.official_results?.[election.national_id]
  if (official) {
    return [await $fetch<ResultFile>(`/data/${election.id}/${official.file}`)]
  }
  return await fetchResultFiles(election.id, election.files)
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
