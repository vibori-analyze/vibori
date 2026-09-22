import { readdir, readFile, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const root = pathToFileURL(`${resolve(process.argv[2] || 'public/data')}/`)
const directoryEntries = await readdir(root, { withFileTypes: true })
const electionIds = directoryEntries
  .filter(entry => entry.isDirectory())
  .map(entry => entry.name)
const elections = []
const routes = ['/']

async function loadFolder(electionId, folderName) {
  const folder = new URL(`${electionId}/${folderName}/`, root)
  let names
  try {
    names = (await readdir(folder)).filter(name => name.endsWith('.json'))
  } catch {
    return []
  }
  return await Promise.all(names.map(async (name) => ({
    file: `${folderName}/${name}`,
    data: JSON.parse(await readFile(new URL(name, folder), 'utf8')),
  })))
}

for (const id of electionIds) {
  const precinctFiles = await loadFolder(id, 'precincts')
  if (!precinctFiles.length) {
    continue
  }

  const officialFiles = await loadFolder(id, 'aggregates')
  const first = precinctFiles[0].data
  const grouped = (kind) => {
    const units = new Map()
    for (const { data } of precinctFiles) {
      const matches = (data.unit.administrative_path || [])
        .filter(unit => unit.kind === kind)
      for (const unit of matches) {
        const count = (units.get(unit.id)?.count || 0) + 1
        units.set(unit.id, { ...unit, count })
      }
    }
    return [...units.values()]
      .sort((left, right) => left.name.localeCompare(right.name, 'ru'))
  }
  const precincts = precinctFiles
    .map(({ file, data }) => ({
      id: data.unit.id,
      name: data.unit.name,
      number: data.unit.number,
      region: (data.unit.administrative_path || [])
        .find(unit => unit.kind === 'region')?.name || '—',
      file,
      path_ids: (data.unit.administrative_path || []).map(unit => unit.id),
    }))
    .sort((left, right) => String(left.number).localeCompare(
      String(right.number),
      'ru',
      { numeric: true },
    ))
  const regions = grouped('region')
  const districts = grouped('district')
  const tiks = grouped('territorial_commission')
  const officialResults = Object.fromEntries(officialFiles.map(({ file, data }) => [
    data.unit.id,
    { file, unit: data.unit },
  ]))
  const nationalId = officialFiles
    .find(item => item.data.unit.kind === 'national')?.data.unit.id
    || (first.unit.administrative_path || [])
      .find(unit => unit.kind === 'national')?.id
    || first.unit.id
  const units = [
    ...regions,
    ...districts,
    ...tiks,
    ...precincts,
    ...officialFiles.map(item => item.data.unit),
    { id: nationalId },
  ]
  for (const unit of units) {
    routes.push(`/result/${id}/${encodeURIComponent(unit.id)}`)
  }
  const entityIds = new Set(precinctFiles.flatMap(({ data }) => (
    data.results.map(result => result.entity.id)
  )))
  for (const entityId of entityIds) {
    routes.push(`/entity/${encodeURIComponent(entityId)}`)
  }
  elections.push({
    id,
    name: first.election.name,
    date: first.election.date,
    country: first.election.country,
    ballot_title: first.ballot.title,
    national_id: nationalId,
    files: precinctFiles.map(item => item.file),
    official_results: officialResults,
    precinct_count: precinctFiles.length,
    regions,
    districts,
    tiks,
    region_count: regions.length,
    precincts,
  })
}

const catalog = {
  standard: 'vibori-catalog/v1',
  generated_at: new Date().toISOString(),
  elections,
}
await writeFile(
  new URL('index.json', root),
  `${JSON.stringify(catalog, null, 2)}\n`,
)
await writeFile(
  new URL('routes.json', root),
  `${JSON.stringify([...new Set(routes)], null, 2)}\n`,
)
console.log(`Catalog updated: ${elections.length} elections`)
