import { readdir, readFile, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const root = pathToFileURL(`${resolve(process.argv[2] || 'public/data')}/`)
const directoryEntries = await readdir(root, { withFileTypes: true })
const electionIds = directoryEntries
  .filter(entry => entry.isDirectory())
  .map(entry => entry.name)
const elections = []

async function jsonNames(electionId, folderName) {
  try {
    const folder = new URL(`${electionId}/${folderName}/`, root)
    return (await readdir(folder)).filter(name => name.endsWith('.json'))
  } catch {
    return []
  }
}

async function readResult(electionId, folderName, name) {
  const file = new URL(`${electionId}/${folderName}/${name}`, root)
  return JSON.parse(await readFile(file, 'utf8'))
}

for (const id of electionIds) {
  const precinctNames = await jsonNames(id, 'precincts')
  if (!precinctNames.length) {
    continue
  }

  const first = await readResult(id, 'precincts', precinctNames[0])
  const grouped = new Map()
  const entities = new Map()
  const analysisPoints = []
  const addGroup = (unit) => {
    const count = (grouped.get(unit.id)?.count || 0) + 1
    grouped.set(unit.id, { ...unit, count })
  }
  const precincts = []

  for (const name of precinctNames) {
    const data = await readResult(id, 'precincts', name)
    const results = []
    for (const result of data.results) {
      entities.set(result.entity.id, result.entity)
      results.push(result.entity.id, result.votes)
    }
    analysisPoints.push([
      data.turnout.registered
        ? Math.round(data.turnout.issued / data.turnout.registered * 10000)
        : 0,
      results,
    ])
    for (const unit of data.unit.administrative_path || []) {
      if (['region', 'district', 'territorial_commission'].includes(unit.kind)) {
        addGroup(unit)
      }
    }
    precincts.push({
      id: data.unit.id,
      name: data.unit.name,
      number: data.unit.number,
      region: (data.unit.administrative_path || [])
        .find(unit => unit.kind === 'region')?.name || '—',
      file: `precincts/${name}`,
      path_ids: (data.unit.administrative_path || []).map(unit => unit.id),
      source_index: analysisPoints.length - 1,
    })
  }

  const byKind = (kind) => [...grouped.values()]
    .filter(unit => unit.kind === kind)
    .sort((left, right) => left.name.localeCompare(right.name, 'ru'))
  precincts.sort((left, right) => String(left.number).localeCompare(
    String(right.number),
    'ru',
    { numeric: true },
  ))

  const entityList = [...entities.values()]
  const entityIndexes = new Map(entityList.map((entity, index) => [entity.id, index]))
  const points = analysisPoints.map(([turnout, results]) => [
    turnout,
    results.map((value, index) => (
      index % 2 ? value : entityIndexes.get(value)
    )),
  ])
  const maxVotes = Array(entityList.length).fill(0)
  for (const [, results] of points) {
    for (let index = 0; index < results.length; index += 2) {
      maxVotes[results[index]] = Math.max(maxVotes[results[index]], results[index + 1])
    }
  }
  const nationalClusters = Array.from({ length: entityList.length }, () => new Map())
  for (const [turnout, results] of points) {
    for (let index = 0; index < results.length; index += 2) {
      const entityIndex = results[index]
      const votes = results[index + 1]
      const voteStep = Math.max(1, Math.ceil(maxVotes[entityIndex] / 120))
      const x = Math.round(turnout / 100) * 100
      const y = Math.round(votes / voteStep) * voteStep
      const key = `${x}:${y}`
      const cluster = nationalClusters[entityIndex].get(key) || [x, y, 0]
      cluster[2] += 1
      nationalClusters[entityIndex].set(key, cluster)
    }
  }
  await writeFile(
    new URL(`${id}/analysis.json`, root),
    `${JSON.stringify({
      standard: 'vibori-precinct-analysis/v1',
      entities: entityList,
      points,
      national_clusters: nationalClusters.map(clusters => [...clusters.values()]),
    })}\n`,
  )

  const officialResults = {}
  for (const name of await jsonNames(id, 'aggregates')) {
    const data = await readResult(id, 'aggregates', name)
    officialResults[data.unit.id] = {
      file: `aggregates/${name}`,
      unit: data.unit,
    }
  }
  const nationalId = Object.values(officialResults)
    .find(entry => entry.unit.kind === 'national')?.unit.id
    || (first.unit.administrative_path || [])
      .find(unit => unit.kind === 'national')?.id
    || first.unit.id
  const regions = byKind('region')
  const election = {
    id,
    name: first.election.name,
    date: first.election.date,
    country: first.election.country,
    scope: first.election.scope,
    ballot_title: first.ballot.title,
    national_id: nationalId,
    files: precinctNames.map(name => `precincts/${name}`),
    official_results: officialResults,
    precinct_count: precinctNames.length,
    regions,
    districts: byKind('district'),
    tiks: byKind('territorial_commission'),
    region_count: regions.length,
    precincts,
  }
  await writeFile(new URL(`${id}/index.json`, root), `${JSON.stringify(election)}\n`)
  elections.push({
    id: election.id,
    name: election.name,
    date: election.date,
    country: election.country,
    scope: election.scope,
    ballot_title: election.ballot_title,
    national_id: election.national_id,
    precinct_count: election.precinct_count,
    region_count: election.region_count,
  })
  global.gc?.()
}

const catalog = {
  standard: 'vibori-catalog/v1',
  generated_at: new Date().toISOString(),
  elections,
}
elections.sort((left, right) => (
  Number(right.scope === 'national') - Number(left.scope === 'national')
  || right.date.localeCompare(left.date)
  || left.name.localeCompare(right.name, 'ru')
  || left.id.localeCompare(right.id)
))
await writeFile(new URL('index.json', root), `${JSON.stringify(catalog)}\n`)
await writeFile(new URL('routes.json', root), '["/"]\n')
console.log(`Catalog updated: ${elections.length} elections`)
